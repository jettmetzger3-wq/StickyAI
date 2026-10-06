"""Props the AI designs for one video, drawn from simple shapes.

The library has a couple of hundred props, but every story has its own objects (the Rosetta Stone, a Spitfire,
Napoleon's hat on a pillow...). Before the storyboard, the writer designs a few of those as lists of shapes on a
100 x 100 grid. They are checked and clamped here, saved with the project, and scenes use them like any other
prop. A scene stores the shapes inline ({"type": "prop", "name": "custom", "params": {"parts": [...]}}), so a
saved scene always renders the same, with or without the project's prop kit.
"""
import re

from .palette import color as C, INK, WHITE
from .props_kit import Sk

UNIT = 3.0                      # px per grid unit at scale 1 (the 100-unit grid is 300 px)
SHAPES = ("rect", "circle", "ellipse", "poly", "line", "text")
MAX_PARTS = 40
MAX_DESIGNS = 10


def _n(v, default=0.0, lo=-30.0, hi=130.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return max(lo, min(hi, f))


def _col(v, default):
    if v in (None, "", "none", "transparent"):
        return None if default is None else default
    return list(C(v, default if default is not None else INK))


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_")
    return s[:40]


def clean_part(q):
    if not isinstance(q, dict):
        return None
    shape = str(q.get("shape") or q.get("type") or "").lower()
    shape = {"square": "rect", "rectangle": "rect", "box": "rect", "oval": "ellipse", "polygon": "poly",
             "triangle": "poly", "path": "line", "polyline": "line", "label": "text"}.get(shape, shape)
    if shape not in SHAPES:
        return None
    out = {"shape": shape}
    if shape in ("rect", "circle", "ellipse", "text"):
        out["x"], out["y"] = _n(q.get("x"), 50), _n(q.get("y"), 50)
    if shape == "rect":
        out["w"], out["h"] = _n(q.get("w"), 20, 0.5, 130), _n(q.get("h"), 20, 0.5, 130)
        if q.get("r"):
            out["r"] = _n(q.get("r"), 0, 0, 50)
    elif shape == "circle":
        out["r"] = _n(q.get("r"), 10, 0.5, 70)
    elif shape == "ellipse":
        out["rx"], out["ry"] = _n(q.get("rx"), 15, 0.5, 70), _n(q.get("ry"), 10, 0.5, 70)
    elif shape in ("poly", "line"):
        pts = []
        for pt in (q.get("points") or [])[:24]:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                pts.append([_n(pt[0], 50), _n(pt[1], 50)])
            elif isinstance(pt, dict):
                pts.append([_n(pt.get("x"), 50), _n(pt.get("y"), 50)])
        if len(pts) < (3 if shape == "poly" else 2):
            return None
        out["points"] = pts
    elif shape == "text":
        t = str(q.get("text") or "").strip()[:14]
        if not t:
            return None
        out["text"] = t
        out["size"] = _n(q.get("size"), 12, 4, 40)
    if shape == "line":
        out["color"] = _col(q.get("color") or q.get("stroke") or q.get("fill"), INK)
        out["width"] = _n(q.get("width"), 2, 0.5, 12)
    elif shape == "text":
        out["color"] = _col(q.get("color") or q.get("fill"), INK)
    else:
        out["fill"] = _col(q.get("fill") or q.get("color"), None)
        if q.get("outline") is False:
            out["outline"] = False
        if q.get("stroke"):
            out["stroke"] = _col(q.get("stroke"), INK)
        if out["fill"] is None and out.get("outline") is False:
            return None
    return out


def clean_parts(parts):
    out = []
    for q in (parts or [])[:MAX_PARTS]:
        c = clean_part(q)
        if c:
            out.append(c)
    return out


def clean_design(d, taken=()):
    """One designed prop -> {"name", "anchor", "desc", "parts"} or None."""
    if not isinstance(d, dict):
        return None
    name = slug(d.get("name"))
    parts = clean_parts(d.get("parts"))
    if not name or len(parts) < 2 or name in taken:
        return None
    anchor = "center" if str(d.get("anchor", "")).lower() == "center" else "bottom"
    desc = re.sub(r"\s+", " ", str(d.get("description") or d.get("desc") or name.replace("_", " ")))[:120]
    return {"name": name, "anchor": anchor, "desc": desc, "parts": parts}


def clean_kit(data, library=()):
    """The writer's answer -> list of designs (unique names, never shadowing a library prop)."""
    items = data.get("props") if isinstance(data, dict) else data
    out, taken = [], set(library)
    for d in items or []:
        c = clean_design(d, taken)
        if c:
            out.append(c)
            taken.add(c["name"])
        if len(out) >= MAX_DESIGNS:
            break
    return out


# ------------------------------------------------------------------ drawing
def _origin(anchor):
    return (50.0, 100.0) if anchor == "bottom" else (50.0, 50.0)


def draw_custom(p, x, y, s, c, k):
    parts = k.get("parts") or []
    ox, oy = _origin(k.get("anchor", "bottom"))
    g = Sk(p, x, y, s * UNIT, wob=0.25)
    lw = 5 / UNIT
    tint = C(c, None) if c else None
    for i, q in enumerate(parts):
        shape = q.get("shape")
        fill = tuple(q["fill"]) if q.get("fill") else None
        if tint and i == 0 and fill:
            fill = tint
        w = 0 if q.get("outline") is False else lw
        stroke = tuple(q["stroke"]) if q.get("stroke") else INK
        if shape == "rect":
            x0, y0 = q["x"] - ox, q["y"] - oy
            g.rect(x0, y0, x0 + q["w"], y0 + q["h"], fill, w, stroke, r=q.get("r", 0))
        elif shape == "circle":
            g.circ(q["x"] - ox, q["y"] - oy, q["r"], fill, w, stroke)
        elif shape == "ellipse":
            g.ell(q["x"] - ox, q["y"] - oy, q["rx"], q["ry"], fill, w, stroke)
        elif shape == "poly":
            g.poly([(a - ox, b - oy) for a, b in q["points"]], fill, w, stroke)
        elif shape == "line":
            g.line([(a - ox, b - oy) for a, b in q["points"]], q.get("width", 2), tuple(q.get("color") or INK))
        elif shape == "text":
            g.text(q["text"], q["x"] - ox, q["y"] - oy, q.get("size", 12), tuple(q.get("color") or INK),
                   stroke=1.2, scol=WHITE)


def custom_bounds(params):
    """(x0, y0, x1, y1) in px at scale 1, relative to the anchor point."""
    parts = (params or {}).get("parts") or []
    ox, oy = _origin((params or {}).get("anchor", "bottom"))
    xs, ys = [], []
    for q in parts:
        sh = q.get("shape")
        if sh == "rect":
            xs += [q["x"], q["x"] + q["w"]]
            ys += [q["y"], q["y"] + q["h"]]
        elif sh == "circle":
            xs += [q["x"] - q["r"], q["x"] + q["r"]]
            ys += [q["y"] - q["r"], q["y"] + q["r"]]
        elif sh == "ellipse":
            xs += [q["x"] - q["rx"], q["x"] + q["rx"]]
            ys += [q["y"] - q["ry"], q["y"] + q["ry"]]
        elif sh in ("poly", "line"):
            xs += [a for a, _ in q["points"]]
            ys += [b for _, b in q["points"]]
        elif sh == "text":
            hw = len(q["text"]) * q.get("size", 12) * 0.3
            xs += [q["x"] - hw, q["x"] + hw]
            ys += [q["y"] - q.get("size", 12) * 0.6, q["y"] + q.get("size", 12) * 0.6]
    if not xs:
        return (-150, -300, 150, 0)
    pad = 2
    return ((min(xs) - ox - pad) * UNIT, (min(ys) - oy - pad) * UNIT, (max(xs) - ox + pad) * UNIT,
            (max(ys) - oy + pad) * UNIT)


def to_element_params(design, params=None):
    out = dict(params or {})
    out.update(parts=design["parts"], anchor=design["anchor"], design=design["name"])
    return out


def kit_lookup(kit):
    """name -> design, with a few spellings."""
    out = {}
    for d in kit or []:
        out[d["name"]] = d
        out[d["name"].replace("_", "")] = d
    return out


def kit_sheet(kit, path, cell=260):
    """A small picture of the designed props (shown on the Storyboard tab)."""
    import math
    from PIL import Image, ImageDraw
    from .doodle import SS
    from .fonts import font
    from .pen import Pen
    if not kit:
        return None
    cols = min(4, len(kit))
    rows = math.ceil(len(kit) / cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 30)), (250, 245, 232))
    d = ImageDraw.Draw(sheet)
    for i, des in enumerate(kit):
        params = to_element_params(des)
        x0, y0, x1, y1 = custom_bounds(params)
        s = min((cell - 30) / max(1, x1 - x0), (cell - 30) / max(1, y1 - y0))
        p = Pen(1, rgba=True, size=(cell, cell))
        ax = cell / 2 - (x0 + x1) / 2 * s
        ay = cell / 2 - (y0 + y1) / 2 * s
        draw_custom(p, ax, ay, s, None, params)
        im = p.im.resize((cell, cell), Image.LANCZOS)
        ox, oy = (i % cols) * cell, (i // cols) * (cell + 30)
        sheet.paste(im, (ox, oy), im)
        d.text((ox + cell / 2, oy + cell + 12), des["name"].replace("_", " "), fill=(60, 60, 70),
               font=font("semi", 18), anchor="mm")
    sheet.save(path)
    return path
