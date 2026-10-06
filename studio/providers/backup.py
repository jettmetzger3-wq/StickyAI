"""Automatic backup writer: Claude Code (your plan) writes first; if the plan's usage limit is reached in the
middle of a video, a free writer (Gemini, else Groq) takes over for the rest of the run instead of stopping.

Claude is tried again on the next step after LIMIT_PAUSE (or the reset time Claude Code reports), so your plan is
used again as soon as it's available.
"""
import re
import threading
import time

from .base import ProviderError
from ..config import load_settings

LIMIT_PAUSE = 45 * 60          # how long to leave Claude alone after it said the plan's limit is reached
_lock = threading.Lock()
_limited_until = [0.0]


class PlanLimit(ProviderError):
    """Claude Code says your plan's usage limit is reached."""


PLAN_LIMIT_RE = re.compile(r"usage limit|limit reached|hit your (usage )?limit|out of (extra )?usage|"
                           r"rate[ _-]?limit|too many requests|resets? (at|in|on)\b|weekly limit|session limit|"
                           r"quota", re.I)


def is_plan_limit(text):
    return bool(PLAN_LIMIT_RE.search(str(text or "")))


def reset_time(text):
    """Claude Code's old format ends with '|<unix time>'; otherwise None."""
    m = re.search(r"\|(\d{10})\b", str(text or ""))
    return float(m.group(1)) if m else None


def mark_limited(text=""):
    until = reset_time(text) or (time.time() + LIMIT_PAUSE)
    with _lock:
        _limited_until[0] = max(_limited_until[0], min(until, time.time() + 6 * 3600))


def limited():
    return time.time() < _limited_until[0]


def clear():
    with _lock:
        _limited_until[0] = 0.0


def backup_for(primary_id):
    """The free writer to fall back on, or None. Settings > Writer > backup_writer: auto | gemini | groq | off."""
    if primary_id != "claude_cli":
        return None
    from . import REGISTRY
    want = str(load_settings().get("backup_writer") or "auto").lower()
    if want == "off":
        return None
    order = ("gemini", "groq") if want == "auto" else (want,)
    for pid in order:
        p = next((x for x in REGISTRY["llm"] if x.id == pid), None)
        if p is not None and p.available()[0]:
            return p
    return None


class WithBackup:
    """Looks and acts like the writer that is currently active (Claude first, the backup after a limit)."""

    def __init__(self, primary, backup, on_switch=None):
        self._primary, self._backup = primary, backup
        self.on_switch = on_switch
        # Claude is resting after a limit, or Claude Code isn't installed on this PC: start with the backup
        self.active = backup if limited() or not primary.available()[0] else primary
        self.switched = self.active is backup

    def __getattr__(self, k):
        return getattr(self.active, k)

    def complete(self, *a, **kw):
        if self.active is self._primary:
            try:
                return self._primary.complete(*a, **kw)
            except PlanLimit as e:
                mark_limited(str(e))
                self.active = self._backup
                self.switched = True
                if self.on_switch:
                    self.on_switch(self._primary, self._backup, str(e))
        if not getattr(self._backup, "supports_web", False):
            kw.pop("web", None)
        return self._backup.complete(*a, **kw)
