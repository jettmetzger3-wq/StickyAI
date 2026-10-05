"""Runs stages in order with checkpoints (autopilot off), cost approvals and progress events."""
import collections
import threading
import time
import traceback

from . import costs
from .events import bus
from .project import Project, STAGES, CHECKPOINTS, STAGE_LABELS
from .stages import STAGE_FUNCS, Cancelled
from .. import providers as P
from ..config import hosted, load_settings
from ..providers.llm import using_model

_running = {}          # slug -> thread
_cancel = {}           # slug -> Event
_queue = collections.deque()   # hosted mode: (slug, kwargs) waiting for a free slot
_guard = threading.Lock()


class Ctx:
    def __init__(self, project, stage, echo=None):
        self.project, self.stage, self.echo = project, stage, echo
        self._last = 0.0
        self.cancel_event = _cancel.setdefault(project.slug, threading.Event())

    def progress(self, frac, msg=""):
        frac = max(0.0, min(1.0, float(frac)))
        now = time.time()
        if now - self._last > 0.4 or frac >= 1.0 or frac <= 0.02:
            self._last = now
            self.project.set_stage(self.stage, progress=round(frac, 3), message=msg)
        bus.publish(self.project.slug, dict(type="progress", stage=self.stage, progress=frac, message=msg))
        if self.echo:
            self.echo(f"  [{self.stage}] {int(frac * 100):3d}% {msg}", end=True)

    def log(self, msg):
        bus.publish(self.project.slug, dict(type="log", stage=self.stage, message=msg))
        try:
            with open(self.project.p("run.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"[{self.stage}] {msg}\n")
        except OSError:
            pass
        if self.echo:
            self.echo(f"  [{self.stage}] {msg}")

    def warn(self, msg):
        self.project.update(lambda m: m.setdefault("warnings", []).append(dict(stage=self.stage, message=msg, at=time.time())))
        self.log("WARNING: " + msg)

    def check_cancel(self):
        if self.cancel_event.is_set():
            raise Cancelled()


def _status(project, status, **fields):
    m = project.update(status=status, **fields)
    bus.publish(project.slug, dict(type="status", status=status, pending=m.get("pending"), error=m.get("error")))
    return m


def next_stage(meta):
    for st in STAGES:
        s = meta.get("stages", {}).get(st, {}).get("status")
        if s not in ("done", "skipped"):
            return st
    return None


def mark_stale(project, from_stage):
    """After an edit, everything from `from_stage` on must be re-run (stages only redo what changed)."""
    def f(m):
        on = False
        for st in STAGES:
            if st == from_stage:
                on = True
            if on and m["stages"].get(st, {}).get("status") not in ("skipped",):
                cur = m["stages"].setdefault(st, {})
                cur["status"] = "pending" if cur.get("status") != "running" else "running"
                cur["progress"] = 0.0
        if m.get("status") == "done":
            m["status"] = "paused"
    project.update(f)


def auto_approver(meta):
    """Hosted mode: the plan already paid for the video, so steps are approved automatically while the video's
    total tool spending stays under the server's cap. Above it the run pauses for the admin."""
    cap = float((meta.get("auto_approve") or {}).get("cap_usd") or 0)

    def ok(na):
        if na.cost.credits and not na.cost.usd:
            return False          # credits with no known dollar value: the admin decides
        return costs.spent(meta) + na.cost.usd <= cap
    return ok


def check_length(project, stage):
    """Hosted mode: a video can't come out much longer than the minutes it reserved."""
    meta = project.meta()
    bill = meta.get("billing")
    if not bill or bill.get("admin") or stage != "render":
        return
    total = float((project.voice() or {}).get("total") or 0)
    limit = float(bill.get("minutes") or 0) * 1.25 + 0.5
    if total / 60 > limit:
        raise P.ProviderError(f"the narration is {total / 60:.1f} minutes but this video reserved "
                              f"{bill['minutes']:g}; shorten the script and run the voice again")


def after_stage(project, stage):
    """Hosted mode: once the final video exists, give back the unused part of the Pro minutes it reserved."""
    meta = project.meta()
    bill = meta.get("billing")
    if stage == "mix" and bill and not bill.get("settled"):
        from ..hosted import plans
        rec = plans.settle(dict(bill), float(project.render_info().get("total") or 0) / 60, project.slug)
        project.update(billing=rec)


def _approved(project, st, na, approve_cb, echo):
    """Ask (CLI), auto-approve (hosted plans) or pause the run for the dashboard. True = go ahead."""
    meta = project.meta()
    cb = approve_cb or (auto_approver(meta) if meta.get("auto_approve") else None)
    if cb and cb(na):
        costs.approve(project, {st: na.cost.to_dict()})
        return True
    pend = dict(type="approval", stage=st, estimate=na.cost.to_dict(),
                lines=[dict(provider=l, cost=c.to_dict()) for l, c in na.lines],
                balances=costs.balances(meta), over_budget=na.over_budget,
                admin_only=bool(meta.get("auto_approve")))
    _status(project, "awaiting_approval", pending=pend)
    bus.publish(project.slug, dict(type="stage", stage=st, status="pending"))
    if echo:
        echo(f"Paused: {STAGE_LABELS[st]} needs your OK to spend {costs.describe(na.cost.to_dict())}.")
    return False


def run(project, start=None, stop_after=None, approve_cb=None, echo=None, stage_kwargs=None):
    """Run stages from `start` (default: first unfinished) to the end, or until `stop_after`.
    approve_cb(NeedsApproval) -> bool lets the CLI ask interactively; the web UI leaves it None and the run pauses."""
    if isinstance(project, str):
        project = Project(project)
    with using_model(project.meta().get("llm_model")):
        return _run(project, start, stop_after, approve_cb, echo, stage_kwargs)


def _run(project, start, stop_after, approve_cb, echo, stage_kwargs):
    _cancel.setdefault(project.slug, threading.Event()).clear()
    meta = project.meta()
    start = start or next_stage(meta)
    if start is None:
        _status(project, "done")
        return "done"
    order = STAGES[STAGES.index(start):]
    if stop_after:
        order = order[:order.index(stop_after) + 1]
    _status(project, "running", error=None, pending=None, queue_position=None)
    for st in order:
        meta = project.meta()
        if meta["stages"].get(st, {}).get("status") == "skipped":
            continue
        try:
            costs.check(project, st, only=((stage_kwargs or {}).get(st) or {}).get("only"))
        except costs.NeedsApproval as na:
            if not _approved(project, st, na, approve_cb, echo):
                return "awaiting_approval"
        project.set_stage(st, status="running", progress=0.0, message="starting", started=time.time(), error=None)
        bus.publish(project.slug, dict(type="stage", stage=st, status="running"))
        if echo:
            echo(f"== {STAGE_LABELS[st]}")
        ctx = Ctx(project, st, echo)
        try:
            check_length(project, st)
            for _attempt in range(3):
                try:
                    STAGE_FUNCS[st](ctx, **((stage_kwargs or {}).get(st, {})))
                    break
                except costs.NeedsApproval as na:
                    # the step found out its exact price while running (e.g. Calliope's own quote)
                    if not _approved(project, st, na, approve_cb, echo):
                        project.set_stage(st, status="pending", message="waiting for your OK")
                        return "awaiting_approval"
            after_stage(project, st)
        except Cancelled:
            project.set_stage(st, status="pending", message="cancelled")
            _status(project, "paused")
            bus.publish(project.slug, dict(type="stage", stage=st, status="pending"))
            return "cancelled"
        except P.NeedsSetup as e:
            project.set_stage(st, status="error", message=str(e), error=str(e))
            _status(project, "error", error=str(e))
            return "error"
        except Exception as e:
            tb = traceback.format_exc()
            ctx.log("ERROR: " + tb[-2000:])
            msg = str(e) or e.__class__.__name__
            project.set_stage(st, status="error", message=msg[:500], error=msg[:2000])
            _status(project, "error", error=f"{STAGE_LABELS[st]}: {msg[:500]}")
            bus.publish(project.slug, dict(type="stage", stage=st, status="error", message=msg[:500]))
            if echo:
                echo(f"ERROR in {st}: {msg}")
            return "error"
        project.set_stage(st, status="done", progress=1.0, finished=time.time())
        bus.publish(project.slug, dict(type="stage", stage=st, status="done"))
        meta = project.meta()
        opts = meta.get("options") or {}
        if st in CHECKPOINTS and not opts.get("autopilot", True) and st not in (meta.get("reviewed") or []):
            if st != order[-1]:
                _status(project, "awaiting_review", pending=dict(type="review", stage=st))
                if echo:
                    echo(f"Checkpoint: review the {STAGE_LABELS[st].lower()}, then continue.")
                return "awaiting_review"
    final = "done" if next_stage(project.meta()) is None else "paused"
    _status(project, final, pending=None)
    return final


def mark_reviewed(project, stage):
    project.update(lambda m: m.setdefault("reviewed", []).append(stage) if stage not in (m.get("reviewed") or []) else None)


# ------------------------------------------------------------------ background jobs (web UI)
def _alive(slug):
    t = _running.get(slug)
    return bool(t and t.is_alive())


def is_queued(slug):
    return any(s == slug for s, _ in _queue)


def is_running(slug):
    """True while a run is going or waiting in the queue (both mean: don't edit right now)."""
    return _alive(slug) or is_queued(slug)


def max_runs():
    """Hosted mode limits how many videos are made at once (rendering uses every CPU core)."""
    if not hosted():
        return 0
    return max(1, int(load_settings()["hosted"].get("max_concurrent_runs") or 1))


def _active():
    return sum(1 for s in list(_running) if _alive(s))


def _launch(slug, kw):
    t = threading.Thread(target=_bg, args=(slug,), kwargs=kw, daemon=True, name=f"run-{slug}")
    _running[slug] = t
    t.start()


def start_background(slug, **kw):
    with _guard:
        if is_running(slug):
            return False
        limit = max_runs()
        if limit and _active() >= limit:
            _queue.append((slug, kw))
            pos = len(_queue)
            Project(slug).update(status="queued", queue_position=pos)
            bus.publish(slug, dict(type="status", status="queued", position=pos))
            return True
        _launch(slug, kw)
        return True


def queue_position(slug):
    for i, (s, _) in enumerate(_queue, 1):
        if s == slug:
            return i
    return 0


def _drain():
    with _guard:
        limit = max_runs()
        while _queue and (not limit or _active() < limit):
            slug, kw = _queue.popleft()
            _launch(slug, kw)
        for i, (s, _) in enumerate(_queue, 1):
            bus.publish(s, dict(type="status", status="queued", position=i))


def _bg(slug, **kw):
    try:
        run(Project(slug), **kw)
    except Exception as e:  # never let a job thread die silently
        Project(slug).update(status="error", error=str(e)[:500])
        bus.publish(slug, dict(type="status", status="error", error=str(e)[:500]))
    finally:
        threading.Thread(target=_drain_soon, daemon=True).start()


def _drain_soon():
    # wait until the finishing thread is really gone, then start the next queued run
    for _ in range(50):
        if _active() < (max_runs() or 1 << 30):
            break
        time.sleep(0.1)
    _drain()


def cancel(slug):
    with _guard:
        for item in list(_queue):
            if item[0] == slug:
                _queue.remove(item)
                Project(slug).update(status="paused", queue_position=None)
                bus.publish(slug, dict(type="status", status="paused"))
                return
    _cancel.setdefault(slug, threading.Event()).set()
