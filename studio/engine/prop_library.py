"""The shared prop library: props you pick by name instead of asking the AI to draw them.

Three kinds, all of them real props in `registry.PROPS` once loaded (so the scene writer, the composer, the repair, the layout
check and the renderer treat them exactly like the props drawn in code):

  * shipped designs   `studio/knowledge/prop_library.json`, hand-authored vector props (scripts/build_prop_library.py);
  * your designs      `data/prop_library/<name>.json`, every prop the AI ever designed for a video, kept for good, so the
                      next video that needs a Rosetta Stone just uses it (the AI is not asked again);
  * variants          a built-in prop with fixed settings ("tea_chest" = the crate labelled TEA, "white_flag" = a white flag).

A design carries `tags` (words that mean it), `frm`/`to` (the years it fits) and `cat`. The word -> prop lookup that uses them
is `studio/knowledge/propindex.py`. A scene stores only the prop's name, so the render cache key gets the design's fingerprint
(`fingerprint`) and a redrawn library prop re-renders the scenes that use it, nothing else.
"""
import hashlib
import json
import os
import re
import tempfile

from .custom_props import clean_design, draw_custom, custom_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED = os.path.join(os.path.dirname(HERE), "knowledge", "prop_library.json")
USER_GROUP = "Props drawn for earlier videos"
SHIPPED_GROUP = "Extra props (hand-drawn)"

LIBRARY = {}          # name -> design {name, anchor, desc, parts, tags, frm, to, cat, source}
VARIANTS = {}         # name -> {prop, params, color, words, desc}
ERRORS = []           # files that could not be read (shown by `python -m studio doctor`)
_state = {"loaded": False}

STOP = set("the a an of and or for with on in to from is it its this that old big small simple drawn made like very".split())


def user_dir():
    from ..config import DATA_DIR
    return os.path.join(DATA_DIR, "prop_library")


def _registry():
    from . import registry
    return registry


def _tags(d, extra=()):
    out = []
    for t in list(d.get("tags") or []) + list(extra):
        t = re.sub(r"[^a-z0-9' -]+", "", str(t).lower()).strip()
        if len(t) >= 3 and t not in STOP and t not in out:
            out.append(t)
    return out[:24]


def _year(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _drawer(design):
    parts, anchor = design["parts"], design["anchor"]

    def fn(p, x, y, s, c, k):
        draw_custom(p, x, y, s, c, dict(k or {}, parts=parts, anchor=anchor))
    return fn


def _enum(name):
    """The scene schema validates prop names against this list; keep it in step with the registry."""
    enum = getattr(_registry(), "PROP_ENUM", None)
    if enum is not None and name not in enum:
        enum.append(name)
        enum.sort()


def _group(label):
    R = _registry()
    for lab, names in R.PROP_GROUPS:
        if lab == label:
            return names
    names = []
    R.PROP_GROUPS.append((label, names))
    return names


def register(d, source="shipped"):
    """Make one design a prop. Returns the stored design, or None when it is invalid or would shadow a built-in drawing."""
    R = _registry()
    c = clean_design(d)
    if not c:
        return None
    name = c["name"]
    if name in R.PROPS and name not in LIBRARY:
        return None                                       # never replace a prop drawn in code
    if name in R.PROP_ALIASES and name not in R.PROPS:
        R.PROP_ALIASES.pop(name)                          # an exact library prop beats a looser alias ("bread" -> baguette)
    c.update(tags=_tags(d, name.split("_")), frm=_year(d.get("frm"), -3000), to=_year(d.get("to"), 3000),
             cat=str(d.get("cat") or "other")[:20], source=source)
    LIBRARY[name] = c
    R.PROPS[name] = (c["anchor"], _drawer(c), c["desc"])
    _enum(name)
    names = _group(SHIPPED_GROUP if source == "shipped" else USER_GROUP)
    if name not in names:
        names.append(name)
    return c


def register_variant(name, spec):
    R = _registry()
    base = spec.get("prop")
    name = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    if not name or base not in R.PROPS or (name in R.PROPS and name not in VARIANTS):
        return None
    params, color = dict(spec.get("params") or {}), spec.get("color")
    anchor, basefn, _ = R.PROPS[base]

    def fn(p, x, y, s, c, k):
        return R.PROPS[base][1](p, x, y, s, c if c is not None else color, dict(params, **(k or {})))
    desc = spec.get("desc") or f"{name.replace('_', ' ')} (a {base.replace('_', ' ')} with fixed settings)"
    VARIANTS[name] = dict(prop=base, params=params, color=color, desc=desc,
                          words=[str(w).lower() for w in spec.get("words") or []])
    R.PROPS[name] = (anchor, fn, desc)
    _enum(name)
    if base in R.ANIMATED:
        R.ANIMATED[name] = R.ANIMATED[base]
    names = _group(SHIPPED_GROUP)
    if name not in names:
        names.append(name)
    return VARIANTS[name]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(force=False):
    """Read the shipped library and the user's designs into the registry. Safe to call again."""
    if _state["loaded"] and not force:
        return
    _state["loaded"] = True
    del ERRORS[:]
    try:
        data = _read(SHIPPED)
    except (OSError, ValueError) as e:
        data = {}
        ERRORS.append(f"prop_library.json: {e}")
    for d in data.get("props") or []:
        register(d, "shipped")
    for name, spec in (data.get("aliases") or {}).items():
        register_variant(name, spec)
    folder = user_dir()
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".json"):
                continue
            try:
                d = _read(os.path.join(folder, fn))
            except (OSError, ValueError) as e:
                ERRORS.append(f"{fn}: {e}")
                continue
            if not register(d, "user"):
                ERRORS.append(f"{fn}: not a usable prop design (or its name is a built-in prop)")


def add_user_design(d):
    """Keep a prop the AI designed for good: it is written to data/prop_library/ and is a prop from now on.
    Returns the stored design, or None when it is not usable or already exists (an existing one is never overwritten)."""
    R = _registry()
    load()
    c = clean_design(d)
    if not c or c["name"] in R.PROPS:
        return None
    words = [w for w in re.findall(r"[a-z]{3,}", f"{c['name'].replace('_', ' ')} {c['desc']}".lower()) if w not in STOP]
    c.update(tags=words[:12], frm=_year(d.get("frm"), -3000), to=_year(d.get("to"), 3000), cat="drawn")
    folder = user_dir()
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(folder, c["name"] + ".json"))
    return register(c, "user")


def bounds(name):
    """(x0, y0, x1, y1) at scale 1 for a library prop or variant, else None."""
    if name in LIBRARY:
        return custom_bounds(LIBRARY[name])
    if name in VARIANTS:
        return _registry().prop_bounds(VARIANTS[name]["prop"], VARIANTS[name]["params"])
    return None


def fingerprint(scene):
    """Short hash of the library designs a scene (or a list of scenes) uses; '' when it uses none. Part of the render key."""
    if not LIBRARY and not VARIANTS:
        return ""
    blob = json.dumps(scene, sort_keys=True, default=str)
    used = [n for n in sorted(LIBRARY) if f'"{n}"' in blob]
    used_v = [n for n in sorted(VARIANTS) if f'"{n}"' in blob]
    if not used and not used_v:
        return ""
    body = json.dumps([[LIBRARY[n]["anchor"], LIBRARY[n]["parts"]] for n in used]
                      + [[n, VARIANTS[n]["prop"], VARIANTS[n]["params"], VARIANTS[n]["color"]] for n in used_v],
                      sort_keys=True, default=str)
    return hashlib.sha1(body.encode()).hexdigest()[:8]
