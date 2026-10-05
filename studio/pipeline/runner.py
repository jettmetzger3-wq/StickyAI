"""Runs stages in order with checkpoints (autopilot off), cost approvals and progress events."""
import threading
import time
import traceback

from . import costs
from .events import bus
from .project import Project, STAGES, CHECKPOINTS, STAGE_LABELS
from .stages import STAGE_FUNCS, Cancelled
from .. import providers as P

_running = {}          # slug -> thread
_cancel = {}           # slug -> Event
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
                m["stages"][st]["status"] = "pending" if m["stages"][st].get("status") != "running" else "running"
                m["stages"][st]["progress"] = 0.0
        if m.get("status") == "done":
            m["status"] = "paused"
    project.update(f)


def run(project, start=None, stop_after=None, approve_cb=None, echo=None, stage_kwargs=None):
    """Run stages from `start` (default: first unfinished) to the end, or until `stop_after`.
    approve_cb(NeedsApproval) -> bool lets the CLI ask interactively; the web UI leaves it None and the run pauses."""
    if isinstance(project, str):
        project = Project(project)
    _cancel.setdefault(project.slug, threading.Event()).clear()
    meta = project.meta()
    start = start or next_stage(meta)
    if start is None:
        _status(project, "done")
        return "done"
    order = STAGES[STAGES.index(start):]
    if stop_after:
        order = order[:order.index(stop_after) + 1]
    _status(project, "running", error=None, pending=None)
    for st in order:
        meta = project.meta()
        if meta["stages"].get(st, {}).get("status") == "skipped":
            continue
        try:
            costs.check(project, st, only=((stage_kwargs or {}).get(st) or {}).get("only"))
        except costs.NeedsApproval as na:
            if approve_cb and approve_cb(na):
                costs.approve(project, {st: na.cost.to_dict()})
            else:
                pend = dict(type="approval", stage=st, estimate=na.cost.to_dict(),
                            lines=[dict(provider=l, cost=c.to_dict()) for l, c in na.lines],
                            balances=costs.balances(meta))
                _status(project, "awaiting_approval", pending=pend)
                if echo:
                    echo(f"Paused: {STAGE_LABELS[st]} needs your OK to spend {costs.describe(na.cost.to_dict())}.")
                return "awaiting_approval"
        project.set_stage(st, status="running", progress=0.0, message="starting", started=time.time(), error=None)
        bus.publish(project.slug, dict(type="stage", stage=st, status="running"))
        if echo:
            echo(f"== {STAGE_LABELS[st]}")
        ctx = Ctx(project, st, echo)
        try:
            STAGE_FUNCS[st](ctx, **((stage_kwargs or {}).get(st, {})))
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
def is_running(slug):
    t = _running.get(slug)
    return bool(t and t.is_alive())


def start_background(slug, **kw):
    with _guard:
        if is_running(slug):
            return False
        t = threading.Thread(target=_bg, args=(slug,), kwargs=kw, daemon=True, name=f"run-{slug}")
        _running[slug] = t
        t.start()
        return True


def _bg(slug, **kw):
    try:
        run(Project(slug), **kw)
    except Exception as e:  # never let a job thread die silently
        Project(slug).update(status="error", error=str(e)[:500])
        bus.publish(slug, dict(type="status", status="error", error=str(e)[:500]))


def cancel(slug):
    _cancel.setdefault(slug, threading.Event()).set()
