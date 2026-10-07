"""The AI usage ledger: every AI call a video makes, whether it was answered from the cache, and a pre-run estimate.

Per video: projects/<slug>/usage.json = {"calls": [...]}. One entry per call:
  stage, task, label, provider, model, in_tok, out_tok (estimates unless the writer reported real numbers),
  cached (answered from the cache, so it used no Claude), secs, at.
"""
import threading
import time

from .pipeline.project import read_json, write_json

_lock = threading.Lock()
CHARS_PER_TOKEN = 3.6


def tokens(chars):
    return int(round(float(chars or 0) / CHARS_PER_TOKEN))


def record(project, entry):
    """Append one call to the video's ledger (never raises: a ledger problem must not stop a video)."""
    try:
        path = project.p("usage.json")
        with _lock:
            data = read_json(path, {}) or {}
            calls = data.setdefault("calls", [])
            calls.append(dict(entry, at=round(time.time(), 1)))
            if len(calls) > 2000:
                del calls[:len(calls) - 2000]
            write_json(path, data)
    except Exception:
        pass


def calls(project):
    return (read_json(project.p("usage.json"), {}) or {}).get("calls") or []


def summary(project):
    """Totals for one video: real calls vs cached ones, tokens, and the same per stage and per task."""
    cs = calls(project)
    return summarize(cs)


def summarize(cs):
    def blank():
        return dict(calls=0, cached=0, in_tok=0, out_tok=0, secs=0.0)

    total, by_stage, by_task = blank(), {}, {}
    for c in cs:
        for bucket in (total, by_stage.setdefault(c.get("stage") or "?", blank()),
                       by_task.setdefault(c.get("task") or c.get("label") or "?", blank())):
            if c.get("cached"):
                bucket["cached"] += 1
            else:
                bucket["calls"] += 1
                bucket["in_tok"] += int(c.get("in_tok") or 0)
                bucket["out_tok"] += int(c.get("out_tok") or 0)
                bucket["secs"] += float(c.get("secs") or 0)
    for b in [total, *by_stage.values(), *by_task.values()]:
        b["secs"] = round(b["secs"], 1)
        b["tokens"] = b["in_tok"] + b["out_tok"]
    return dict(total=total, by_stage=by_stage, by_task=by_task)
