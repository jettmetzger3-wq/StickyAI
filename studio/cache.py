"""One cache for everything the AI already made, so we never pay for the same thing twice.

Layout (under data/cache/): llm/ research/ props/ plans/ people/, one small JSON file per entry, named by a
content hash. An entry is {"v": value, "at": time, "meta": {...}}. Failures are never stored.

  llm       the raw text of an AI reply, keyed by (writer, model, system, prompt, schema, images)
  research  a topic brief (deep mode), keyed by the normalised topic
  props     one custom prop drawing, keyed by its name (reused by later videos)
  plans     one beat's director plan, keyed by (beat text, mood, cast signature, pattern library version)
  people    the look of a historical person the first time a video used them (see knowledge/people.py)

Turn it off with Settings > cache_enabled = false, or clear it with clear().
"""
import hashlib
import json
import os
import threading
import time

from .config import CACHE_DIR, load_settings

NAMESPACES = ("llm", "research", "props", "plans", "people")
_lock = threading.Lock()
COUNTS = {"hit": 0, "miss": 0, "put": 0}          # this process only; the per-video ledger is in usage.py


def enabled():
    return load_settings().get("cache_enabled", True) is not False


def key(*parts):
    """A stable short hash of anything JSON-like."""
    raw = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def file_key(path):
    """A hash of a file's bytes (for images sent to the AI)."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return "missing:" + str(path)
    return h.hexdigest()[:24]


def _path(ns, k):
    return os.path.join(CACHE_DIR, ns, k[:2], k + ".json")


def get(ns, k, max_age=None):
    """The cached value or None."""
    if not enabled():
        return None
    try:
        with open(_path(ns, k), encoding="utf-8") as f:
            e = json.load(f)
    except (OSError, ValueError):
        COUNTS["miss"] += 1
        return None
    if max_age and time.time() - float(e.get("at") or 0) > max_age:
        COUNTS["miss"] += 1
        return None
    COUNTS["hit"] += 1
    return e.get("v")


def has(ns, k):
    return enabled() and os.path.exists(_path(ns, k))


def put(ns, k, value, meta=None):
    if not enabled() or value is None:
        return False
    p = _path(ns, k)
    with _lock:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + f".{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"v": value, "at": time.time(), "meta": meta or {}}, f, ensure_ascii=False)
        os.replace(tmp, p)
    COUNTS["put"] += 1
    return True


def stats():
    """{namespace: {"entries": n, "kb": size}} plus the totals."""
    out, total_n, total_b = {}, 0, 0
    for ns in NAMESPACES:
        n = b = 0
        for root, _, files in os.walk(os.path.join(CACHE_DIR, ns)):
            for fn in files:
                if fn.endswith(".json"):
                    n += 1
                    try:
                        b += os.path.getsize(os.path.join(root, fn))
                    except OSError:
                        pass
        out[ns] = {"entries": n, "kb": round(b / 1024, 1)}
        total_n += n
        total_b += b
    out["total"] = {"entries": total_n, "kb": round(total_b / 1024, 1)}
    return out


def clear(ns=None):
    """Delete one namespace (or all). Returns how many entries were removed."""
    import shutil
    n = 0
    for name in ([ns] if ns else NAMESPACES):
        d = os.path.join(CACHE_DIR, name)
        for _, _, files in os.walk(d):
            n += sum(1 for f in files if f.endswith(".json"))
        shutil.rmtree(d, ignore_errors=True)
    return n
