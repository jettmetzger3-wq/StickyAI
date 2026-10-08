"""Layout validation and local auto-correction: does this scene look composed, or just filled?

One geometry model serves two jobs, so the report and the repair can never disagree:

  findings(items, ...)  -> every problem found, each with a severity and a cost (how bad it is, in rough pixels)
  fix_scene(scene, ...) -> a staged repair that lowers the total cost: first move speech bubbles and labels, then props,
                           then characters (position, then scale), then the camera. Only what is still broken after that is
                           handed back as `escalate` (the only case worth spending Claude on).

What is checked (see docs/layout.md): collisions (text/text, bubble/text, bubble tail/text, text/character with the head
treated as more important than the body, character/important prop, prop/prop), safe margins, the caption zone, character
scale (too small, too big, inconsistent next to a neighbour), text size and breathing room, speech-bubble placement (tail
points at a speaker, size fits the words), visual hierarchy (a minor object must not outweigh the subject; the subject
must not sit in a corner), empty or lopsided scenes, and close-ups that would cut something in half. Consistency across a
whole video is `consistency()`.

Deliberate overlaps are not problems: text on a board or sign, an element that appears after another has gone (times are
compared), a prop that was placed behind a character on purpose (z=0) only counts when it is mostly hidden.
Nothing here calls an AI, and nothing shrinks text to make it fit: it moves things.
"""
import math
import re
from collections import Counter

from .doodle import W, H
from .captions import CAPTION_ZONE
from .geo import View
from .schema import element_bbox, char_box, text_bbox, _f

TEXT_BOTTOM = H - CAPTION_ZONE
MARGIN = {"text": 64, "bubble": 56, "person": 40, "prop": 28}       # px kept clear to the edge of the frame
TOP_MARGIN = 40
GAP = 28                                                            # air kept between a text and its neighbours
HEAD_SHARE = 0.46                                                   # top share of a character's box that is head and hat
MIN_SIZE = {"title": 56, "label": 40, "stat": 60, "bubble": 40, "note": 34, "maplabel": 32}
CHAR_MIN, CHAR_MIN_SPEAKER, CHAR_MIN_GROUP, CHAR_MAX = 0.5, 0.7, 0.42, 1.5
SCALE_RATIO = 1.6                                                   # two neighbours on the same ground may differ this much
SAME_GROUND = 90                                                    # two characters this close in ground height share a scale
TEXTY = ("title", "label", "stat", "maplabel", "bubble", "note")
PERSON = ("char", "crowd")
IMPORTANT_PROPS = {"document", "scroll", "newspaper", "treaty", "telegram", "map", "chart", "trophy", "crown", "check"}
SEV_COST = {"high": 0.25, "medium": 0.10, "low": 0.04, "info": 0.0}  # what a finding takes off the layout score ("info" only steers repairs)
SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


# ---------------------------------------------------------------- geometry
def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def _life(el):
    def num(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return num(el.get("at")), num(el.get("exit"))


def coexist(a, b):
    """False only when both are timed and one is gone before the other appears."""
    a0, a1 = _life(a)
    b0, b1 = _life(b)
    if a1 is not None and b0 is not None and b0 >= a1:
        return False
    if b1 is not None and a0 is not None and a0 >= b1:
        return False
    return True


def bubble_geometry(el):
    """(body box, tail tip (x, y) or None) of a speech bubble as the renderer draws it."""
    from .compiler import bubble_size, bubble_tail
    w, h, _ = bubble_size(el)
    x, y = _f(el.get("x"), 960), _f(el.get("y"), 540)
    body = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    if el.get("tail") == "none":
        return body, None
    tx, ty = bubble_tail(el, w, h)
    return body, (x + tx, y + h / 2 + ty)


def _tail_hits(body, tip, box, inflate=4):
    """Does the straight tail from the bubble's bottom edge to its tip cross `box`?"""
    if tip is None:
        return False
    sx = min(max(tip[0], body[0] + 24), body[2] - 24)
    sy = body[3]
    b = (box[0] + inflate, box[1] + inflate, box[2] - inflate, box[3] - inflate)
    if b[2] <= b[0] or b[3] <= b[1]:
        return False
    for k in range(1, 11):
        t = k / 10
        px, py = sx + (tip[0] - sx) * t, sy + (tip[1] - sy) * t
        if b[0] <= px <= b[2] and b[1] <= py <= b[3]:
            return True
    return False


# ---------------------------------------------------------------- the items of a scene
def _words(s):
    return {w for w in re.findall(r"[a-z]{3,}", str(s or "").lower())}


def _important(name, words):
    n = str(name or "").lower()
    if n in IMPORTANT_PROPS or any(k in n for k in ("document", "scroll", "newspaper", "map", "chart", "graph")):
        return True
    toks = [t for t in re.split(r"[_\s]+", n) if len(t) >= 3] + [n]
    return any(w in t or t in w for w in words for t in toks if len(t) >= 3 and len(w) >= 3)


def is_scenery(name):
    """Landmarks and set pieces (the Eiffel Tower, a castle) are the place, not the subject: they are meant to be large."""
    try:
        from .registry import PROPS, resolve_prop
        v = PROPS.get(resolve_prop(name) or name)
        return bool(v and callable(v[1]) and v[1].__module__.endswith("props_places")) or str(name) in ("castle", "folding_screen", "windmill")
    except Exception:
        return False


def _pt_xy(p, view):
    """A point written as [x, y], {x, y} or {lon, lat} -> screen (x, y) or None."""
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return _f(p[0], 0), _f(p[1], 0)
    if isinstance(p, dict):
        if p.get("lon") is not None and p.get("lat") is not None:
            return view.xy(_f(p["lon"], 0), _f(p["lat"], 0)) if view else None
        if p.get("x") is not None and p.get("y") is not None:
            return _f(p["x"], 0), _f(p["y"], 0)
    return None


def _samples(pts, step=14):
    """Points along a polyline (at most every `step` px)."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
    return out


def line_hits(pts, box, inflate=6):
    """How many sample points of the line fall inside `box` (grown a little)."""
    b0, b1, b2, b3 = box[0] - inflate, box[1] - inflate, box[2] + inflate, box[3] + inflate
    return sum(1 for x, y in _samples(pts) if b0 <= x <= b2 and b1 <= y <= b3)


def visual_box(el, view):
    """(role, box) for icon grids, arrows/routes and charts, which element_bbox() does not measure."""
    from .registry import resolve_prop, prop_bounds
    t = el.get("type")
    if t == "icons":
        name = resolve_prop(el.get("icon") or "") or "mini_carrier"
        n = int(max(1, min(_f(el.get("count"), 6), 200)))
        per = int(max(1, _f(el.get("per_row"), min(n, 10))))
        s = _f(el.get("scale"), 0.35)
        bx0, by0, bx1, by1 = prop_bounds(name, el.get("params"))
        gap = _f(el.get("gap"), (bx1 - bx0) * s * 1.15 + 6)
        gap_y = _f(el.get("gap_y"), (by1 - by0) * s * 1.1 + 6)
        rows, cols = -(-n // per), min(n, per)
        x0, y0 = _f(el.get("x"), 960), _f(el.get("y"), 540)
        left = x0 - (cols - 1) * gap / 2
        return "icons", (left + bx0 * s, y0 - (rows - 1) * gap_y + by0 * s, left + (cols - 1) * gap + bx1 * s, y0 + by1 * s), None
    if t in ("arrow", "route"):
        pts = el.get("points") or [el.get("from"), el.get("to")]
        xy = [q for q in (_pt_xy(p_, view) for p_ in pts if p_ is not None) if q]
        if len(xy) >= 2:
            pad = _f(el.get("width"), 14) / 2 + 26
            return "line", (min(q[0] for q in xy) - pad, min(q[1] for q in xy) - pad, max(q[0] for q in xy) + pad, max(q[1] for q in xy) + pad), xy
    if t == "shape" and el.get("shape", "rect") in ("rect", "circle", "ellipse") and el.get("x") is not None:
        x, y = _f(el.get("x"), 960), _f(el.get("y"), 540)
        if el.get("shape", "rect") == "rect":
            w, h = _f(el.get("w"), 300), _f(el.get("h"), 200)
        else:
            r = _f(el.get("r"), 80)
            w, h = 2 * _f(el.get("rx"), r), 2 * _f(el.get("ry"), r)
        return "panel", (x - w / 2, y - h / 2, x + w / 2, y + h / 2), None
    if t == "chart" and el.get("x") is not None:
        x, y = _f(el.get("x"), 960), _f(el.get("y"), 540)
        w, h = _f(el.get("w"), 800), _f(el.get("h"), 500)
        return "container", (x - w / 2, y - h / 2, x + w / 2, y + h / 2), None
    return None


def build_items(sc, ctx=None):
    """[{i, el, role, box, important, size}] for every element that takes room on screen."""
    return _builder(sc, ctx)[0]


def _builder(sc, ctx=None):
    """(items, one) where one(i, el, fixed=False) measures a single element again and returns its item (or None)."""
    ctx = ctx or {}
    words = _words(ctx.get("text")) | {w for n in ctx.get("needs") or [] for w in _words(n)}
    bg = sc.get("bg") or {}
    view = None
    if bg.get("type") == "map" and isinstance(bg.get("center"), (list, tuple)) and bg.get("width"):
        view = View(_f(bg["center"][0], 0), _f(bg["center"][1], 0), _f(bg["width"], 60))
    items = []
    out_one = {}

    def one(i, el, fixed=False):
        t = el.get("type")
        probe, geo = el, el.get("lon") is not None and el.get("lat") is not None
        if geo:
            if view is None:
                return
            mx, my = view.xy(_f(el["lon"], 0), _f(el["lat"], 0))
            probe = {k: v for k, v in el.items() if k not in ("lon", "lat")}
            probe["x"], probe["y"] = mx, my
        vrole, vpts = None, None
        if t in PERSON:
            box = char_box(probe)
        elif t == "bubble":
            box = bubble_geometry(probe)[0]
        elif t in ("icons", "arrow", "route", "chart", "shape"):
            vb = visual_box(probe if t != "arrow" and t != "route" else el, view)
            vrole, box, vpts = vb if vb else (None, None, None)
        else:
            box = element_bbox(probe)
        if not box:
            return
        size = _f(el.get("size"), 0)
        if t == "text":
            y = _f(probe.get("y"), 540)
            digits = re.sub(r"[^0-9]", "", str(el.get("text", "")))
            if geo or (bg.get("type") == "map" and y > 190):
                role = "maplabel"
            elif y <= 190:
                role = "title"
            elif digits and len(str(el.get("text", ""))) <= 14 and size >= 56:
                role = "stat"
            else:
                role = "label"
        elif t == "counter":
            role = "stat"
        elif t == "bubble":
            role = "bubble"
        elif t in ("note", "sign", "board"):
            role = "note" if t == "note" else "container"
        elif t in PERSON:
            role = t
        elif vrole:
            role = vrole
        elif t == "prop":
            role = "prop"
        elif t == "battle":
            role = "marker"
        else:
            return
        imp = (t == "prop" and _important(el.get("name"), words)) or role in ("icons", "line")
        it = dict(i=i, el=el, probe=probe, geo=geo, role=role, box=box, important=imp, size=size, pts=vpts, fixed=fixed,
                  scenery=(t == "prop" and is_scenery(el.get("name"))))
        out_one["last"] = it
        return it

    for i, el in enumerate(sc.get("elements") or []):
        if el.get("type") == "group":                 # a group's pieces are measured too, but only the group as a whole can move
            for k, ch in enumerate(el.get("items") or []):
                if isinstance(ch, dict):
                    it = one(1000 + i * 50 + k, ch, fixed=True)
                    if it:
                        items.append(it)
        else:
            it = one(i, el)
            if it:
                items.append(it)
    return items, one


def speaker_of(it, items):
    """The character a bubble points at (nearest head to its tail tip), or None."""
    _, tip = bubble_geometry(it["probe"])
    if tip is None:
        return None
    best, bd = None, 1e9
    for o in items:
        if o["role"] not in PERSON:
            continue
        b = o["box"]
        hx, hy = (b[0] + b[2]) / 2, b[1] + 0.25 * (b[3] - b[1])
        d = math.hypot(tip[0] - hx, tip[1] - hy)
        if d < bd:
            best, bd = o, d
    return best if best is not None and bd <= 300 else None


def target_of(it, items):
    """What a bubble's tail points at: a character/crowd (nearest head), or a prop it is touching (a ship that "talks")."""
    sp = speaker_of(it, items)
    if sp is not None:
        return sp
    _, tip = bubble_geometry(it["probe"])
    if tip is None:
        return None
    for o in items:
        if o["role"] == "prop":
            b = o["box"]
            if b[0] - 160 <= tip[0] <= b[2] + 160 and b[1] - 160 <= tip[1] <= b[3] + 160:
                return o
    return None


def head_zone(b):
    return (b[0], b[1], b[2], b[1] + HEAD_SHARE * (b[3] - b[1]))


# ---------------------------------------------------------------- findings
def _add(out, kind, sev, idx, msg, cost, fix=""):
    out.append(dict(kind=kind, sev=sev, idx=list(idx), msg=msg, cost=float(cost), fix=fix))


def _label(it):
    el = it["el"]
    return str(el.get("text") or el.get("name") or el.get("title") or it["role"])[:24]


def _edge_findings(items, out):
    for it in items:
        b, r = it["box"], it["role"]
        if r == "panel" or it.get("fixed") or it["el"].get("peek") or (r in ("prop", "marker") and not it["important"]):
            continue                          # backdrops, group pieces and decoration may run off the frame
        cls = "text" if r in ("title", "label", "stat", "maplabel", "note") else "bubble" if r == "bubble" else "person" if r in PERSON else "prop"
        m = MARGIN[cls]
        top_m = TOP_MARGIN if cls != "person" else 8
        left, right, top = b[0], W - b[2], b[1]
        bottom = H - b[3] if cls not in ("person",) else 99
        worst = min(left - m, right - m, top - top_m, (bottom - 0) if cls in ("text", "bubble") else 99)
        out_by = max(-left, -right, -top, -(H - b[3]) if cls in ("text", "bubble") else -99)
        if out_by > 2:
            # a character may be partly cropped by the edge only at its feet; anything else is cut off
            _add(out, "edge", "high", [it["i"]], f"{_label(it)} is cut off by the edge of the frame", 30 + out_by * 0.5,
                 "move it inside the frame")
        elif worst < 0:
            sev = "medium" if (cls in ("text", "bubble", "person") and worst < (-20 if cls == "person" else -28)) else "low"
            _add(out, "margin", sev, [it["i"]], f"{_label(it)} is too close to the edge of the frame", -worst * 1.5,
                 "move it away from the edge")
        if r in ("title", "label", "stat", "maplabel", "note", "bubble") and b[3] > TEXT_BOTTOM + 2 and not it["geo"]:
            _add(out, "caption", "medium", [it["i"]], f"{_label(it)} sits where the captions are burned in", (b[3] - TEXT_BOTTOM) * 0.8,
                 "move it above the caption area")
        if r in ("prop", "icons") and it["important"]:
            below = max(0.0, b[3] - 940.0) / max(1.0, b[3] - b[1])         # captions are burned in over the last ~140px
            if below > 0.25:
                _add(out, "caption", "medium", [it["i"]], f"{_label(it)} is partly under the captions", below * 60, "lift it above the captions")


def _readability(items, out):
    for it in items:
        r = it["role"]
        need = MIN_SIZE.get(r)
        el = it["el"]
        if need and it["size"] and it["size"] < need and not (r == "maplabel" and it["size"] >= 30):
            _add(out, "text_size", "medium", [it["i"]], f"{_label(it)} is too small to read ({it['size']:g}px, wants {need})",
                 (need - it["size"]) * 1.2, "make it larger and give it room")
        if r == "bubble":
            from .compiler import bubble_size
            w0, h0, _ = bubble_size(el)
            auto = bubble_size({k: v for k, v in el.items() if k not in ("w", "h")})
            if (el.get("w") or el.get("h")) and (w0 < auto[0] * 0.95 or h0 < auto[1] * 0.95):
                _add(out, "bubble_fit", "medium", [it["i"]], "a speech bubble is too small for its words", 12, "let it size itself")


def _names(prop_name, text):
    """Is this label the name of that prop ("EIFFEL TOWER" over the eiffel_tower)?"""
    toks = [t for t in re.split(r"[_\s]+", str(prop_name or "").lower()) if len(t) >= 3]
    words = _words(text)
    return bool(toks) and all(any(t in w or w in t for w in words) for t in toks)


def _pair(a, b, items, out):
    ra, rb = a["role"], b["role"]
    ea, eb = a["el"], b["el"]
    if _gap(a["box"], b["box"]) > 90 or not coexist(ea, eb):
        return
    if ("panel" in (ra, rb) and not (ra in TEXTY and rb in TEXTY)) or (a.get("fixed") and b.get("fixed")):
        return                              # a panel is a backdrop: text, people and props sit on it
    ba, bb = a["box"], b["box"]
    gap = _gap(ba, bb)
    if gap > 90:
        return                                # far apart: no rule below applies (the air hints stop at 90 px)
    ov = _inter(ba, bb)
    ia, ib = a["i"], b["i"]
    small = max(1.0, min(_area(ba), _area(bb)))
    frac = ov / small
    # texts and bubbles
    if ra in TEXTY and rb in TEXTY:
        if ra != "bubble" and rb != "bubble" and ov == 0 and any(
                o["role"] in ("container", "panel") and _inter(ba, o["box"]) >= 0.9 * _area(ba) and _inter(bb, o["box"]) >= 0.9 * _area(bb) for o in items):
            return                        # two lines of one card (a name and its title) are a pair on purpose
        if ra == "maplabel" and rb == "maplabel" and frac < 0.04:
            return
        if ov > 0:
            title_hit = "title" in (ra, rb) and "bubble" in (ra, rb)
            sev = "high" if (frac > 0.04 or title_hit) else "medium"
            kind = "bubble_covers_text" if "bubble" in (ra, rb) else "text_overlap"
            msg = f"a speech bubble covers {_label(b if ra == 'bubble' else a)}" if kind == "bubble_covers_text" else \
                f"'{_label(a)}' and '{_label(b)}' overlap"
            _add(out, kind, sev, [ia, ib], msg, 40 + ov / 600, "move one of them to free space")
        elif gap < GAP and "bubble" not in (ra, rb):
            _add(out, "text_close", "low", [ia, ib], f"'{_label(a)}' is very close to '{_label(b)}'", (GAP - gap) * 1.5, "give them air")
        elif gap < 90:
            _add(out, "air", "info", [ia, ib], "", (90 - gap) * 0.18)
        return
    # text-like against a container (board/sign): text on it is intentional
    if "container" in (ra, rb):
        txt, box_ = (a, b) if ra != "container" else (b, a)
        if txt["role"] in TEXTY and txt["role"] != "bubble" and _inter(txt["box"], box_["box"]) >= 0.7 * _area(txt["box"]):
            return
        if txt["role"] == "bubble" and ov > 0.12 * _area(txt["box"]):
            _add(out, "bubble_covers_text", "high", [ia, ib], "a speech bubble covers a board or sign", 40 + ov / 600, "move the bubble")
        return
    # texts against people
    for t_, p_ in ((a, b), (b, a)):
        if t_["role"] in TEXTY and p_["role"] in PERSON:
            tb, pb = t_["box"], p_["box"]
            hz = head_zone(pb)
            own = t_["role"] == "bubble" and speaker_of(t_, items) is p_
            head_ov = _inter(tb, hz)
            body_ov = ov - head_ov
            if head_ov > 150.0 or (head_ov > 0 and t_["role"] == "bubble"):
                who = "its own speaker's" if own else "a character's"
                _add(out, "covers_face", "high", [t_["i"], p_["i"]], f"{_label(t_)} covers {who} face", 45 + head_ov / 400,
                     "move the text off the head")
            elif body_ov > 0.10 * _area(tb) and p_["role"] == "char":
                _add(out, "covers_body", "medium", [t_["i"], p_["i"]], f"{_label(t_)} sits on a character", 14 + body_ov / 900,
                     "move it clear of the character")
            elif ov == 0 and _gap(tb, hz) < GAP and t_["role"] != "bubble":
                _add(out, "text_close", "low", [t_["i"], p_["i"]], f"{_label(t_)} is very close to a character", (GAP - _gap(tb, hz)) * 1.2)
            elif ov == 0 and _gap(tb, hz) < 80 and t_["role"] != "bubble":
                _add(out, "air", "info", [t_["i"], p_["i"]], "", (80 - _gap(tb, hz)) * 0.15)
            if t_["role"] == "bubble" and not own and speaker_of(t_, items) is not p_ and ov > 0 and p_["role"] == "crowd":
                _add(out, "covers_face", "medium", [t_["i"], p_["i"]], "a speech bubble covers a crowd", 16 + ov / 900, "move the bubble")
            return
    # texts against props
    for t_, p_ in ((a, b), (b, a)):
        if t_["role"] in TEXTY and p_["role"] == "prop":
            if ov <= 0:
                return
            cover = ov / max(1.0, _area(p_["box"]))
            if _names(p_["el"].get("name"), t_["el"].get("text")):
                return
            if p_["important"] and cover > 0.12:
                sev = "high" if (t_["role"] in ("bubble", "title") and cover > 0.25) else "medium"
                _add(out, "covers_prop", sev, [t_["i"], p_["i"]], f"{_label(t_)} covers {_label(p_)}", 30 + cover * 30,
                     "move the text off it")
            elif _names(p_["el"].get("name"), t_["el"].get("text")):
                return
            elif t_["role"] in ("title", "stat") and not p_["scenery"] and ov / max(1.0, _area(t_["box"])) > 0.15:
                _add(out, "covers_prop", "medium", [t_["i"], p_["i"]], f"{_label(t_)} sits on top of {_label(p_)}", 22 + ov / 700, "move the text clear of it")
            elif not p_["important"] and ov / max(1.0, _area(t_["box"])) > 0.5:
                _add(out, "covers_prop", "low", [t_["i"], p_["i"]], f"{_label(t_)} sits on top of {_label(p_)}", 6 + cover * 10)
            return
    # icon grids and arrows are the picture: nothing should sit on them
    for v_, o_ in ((a, b), (b, a)):
        if v_["role"] in ("icons", "line"):
            line = v_["role"] == "line" and v_.get("pts")
            if o_["role"] in TEXTY:
                hit = line_hits(v_["pts"], o_["box"]) >= 2 if line else ov > 0.15 * _area(o_["box"])
                if hit and line:                  # a label at either end of an arrow is naming that end: intended
                    ends = (v_["pts"][0], v_["pts"][-1])
                    hit = not any(o_["box"][0] - 70 <= ex_ <= o_["box"][2] + 70 and o_["box"][1] - 70 <= ey_ <= o_["box"][3] + 70 for ex_, ey_ in ends)
                if hit:
                    _add(out, "covers_prop", "medium", [o_["i"], v_["i"]], f"{_label(o_)} sits on top of the {v_['el'].get('type')}", 26 + ov / 800,
                         "move the text off it")
            elif o_["role"] in PERSON:
                hz = head_zone(o_["box"])
                if line:
                    hit = line_hits(v_["pts"], hz, 0) >= 2
                else:
                    solid = _inter(hz, v_["box"]) + 0.3 * max(0.0, ov - _inter(hz, v_["box"]))
                    hit = solid > 0.12 * _area(v_["box"])
                if hit:
                    _add(out, "covers_prop", "medium", [o_["i"], v_["i"]], f"a character stands on the {v_['el'].get('type')}", 20 + ov / 900,
                         "move the character or the picture")
            elif o_["role"] == "prop" and not o_["scenery"]:
                hit = line_hits(v_["pts"], o_["box"], 0) >= 4 if line else ov > 0.2 * min(_area(v_["box"]), _area(o_["box"]))
                if hit:
                    _add(out, "prop_overlap", "medium", [v_["i"], o_["i"]], f"{_label(o_)} runs into the {v_['el'].get('type')}", 16 + ov / 1500,
                         "move the object")
            return
    # people against people
    if ra in PERSON and rb in PERSON:
        if frac > (0.30 if (ra == "char" and rb == "char") else 0.45):
            _add(out, "people_overlap", "medium" if ra == rb == "char" else "low", [ia, ib], "two characters stand on top of each other",
                 12 + frac * 20, "spread them apart")
        return
    # people against important props
    for p_, o_ in ((a, b), (b, a)):
        if p_["role"] in PERSON and o_["role"] == "prop" and o_["important"]:
            # a stickman is thin: its head and hat hide what is behind them, its body only a little
            hz = head_zone(p_["box"])
            solid = _inter(hz, o_["box"]) + 0.3 * max(0.0, ov - _inter(hz, o_["box"]))
            hidden = solid / max(1.0, _area(o_["box"]))
            behind = o_["el"].get("z") is not None and _f(o_["el"].get("z"), 1) <= 0
            head_hit = _inter(hz, o_["box"]) > 600 and not o_["scenery"]
            if head_hit or hidden > (0.5 if o_["scenery"] else 0.2 if behind else 0.12):
                _add(out, "covers_prop", "medium", [p_["i"], o_["i"]], f"a character hides {_label(o_)}", 14 + hidden * 30,
                     "move the object or the character")
            return
    # important props against each other
    if ra == rb == "prop" and a["important"] and b["important"] and frac > 0.25 and "check" not in (ea.get("name"), eb.get("name")):
        _add(out, "prop_overlap", "low", [ia, ib], f"{_label(a)} and {_label(b)} overlap", 6 + frac * 12)


def _tails(items, out):
    for it in items:
        if it["role"] != "bubble":
            continue
        body, tip = bubble_geometry(it["probe"])
        sp = speaker_of(it, items)
        people = [o for o in items if o["role"] in PERSON]
        if tip is not None and people and sp is None and target_of(it, items) is None:
            _add(out, "tail_target", "medium", [it["i"]], "a speech bubble doesn't point at anyone", 18, "point the tail at the nearest speaker")
        for o in items:
            if o is it or not coexist(it["el"], o["el"]):
                continue
            if o["role"] in TEXTY and o["role"] != "bubble" or (o["role"] == "prop" and o["important"]):
                if _tail_hits(body, tip, o["box"]):
                    _add(out, "tail_crosses", "medium", [it["i"], o["i"]], f"a bubble's tail crosses {_label(o)}", 20, "move the bubble")
            elif o["role"] == "char" and o is not sp and tip is not None and _tail_hits(body, tip, head_zone(o["box"]), inflate=10):
                _add(out, "tail_crosses", "medium", [it["i"], o["i"]], "a bubble's tail crosses another character's face", 20, "move the bubble")


def _scale_findings(items, out):
    chars = [o for o in items if o["role"] == "char"]
    speakers = {id(speaker_of(b, items)) for b in items if b["role"] == "bubble"} - {id(None)}
    for c in chars:
        s = _f(c["el"].get("scale"), 1.0)
        spk = id(c) in speakers or bool(c["el"].get("say"))
        need = CHAR_MIN_SPEAKER if spk else CHAR_MIN_GROUP if len(chars) >= 3 else CHAR_MIN
        if s < need - 0.02:
            _add(out, "char_small", "medium", [c["i"]], f"a character is too small to read ({s:.2f})", (need - s) * 120, "make the character larger")
        elif s > CHAR_MAX:
            _add(out, "char_big", "medium", [c["i"]], f"a character is bigger than it needs to be ({s:.2f})", (s - CHAR_MAX) * 120, "make the character smaller")
    for k, a in enumerate(chars):
        for b in chars[k + 1:]:
            if abs(_f(a["el"].get("y"), 900) - _f(b["el"].get("y"), 900)) <= SAME_GROUND and coexist(a["el"], b["el"]):
                sa, sb = _f(a["el"].get("scale"), 1.0), _f(b["el"].get("scale"), 1.0)
                if max(sa, sb) / max(0.01, min(sa, sb)) > SCALE_RATIO:
                    _add(out, "scale_mismatch", "medium", [a["i"], b["i"]], "two characters on the same ground are very different sizes",
                         (max(sa, sb) / min(sa, sb) - SCALE_RATIO) * 60 + 8, "bring them closer in size")


def _hierarchy(items, out, sc):
    bg = (sc.get("bg") or {}).get("type")
    people = [o for o in items if o["role"] in PERSON]
    focus = None
    imps = [o for o in items if o["role"] == "prop" and o["important"]]
    if imps:
        focus = max(imps, key=lambda o: _area(o["box"]))
    elif people:
        focus = max((o for o in people if o["role"] == "char"), key=lambda o: _f(o["el"].get("scale"), 1), default=people[0])
    if focus is None:
        return
    fa = max([_area(o["box"]) for o in people + imps] or [1.0])
    for o in items:
        if o["role"] == "prop" and not o["important"] and not o["scenery"] and _area(o["box"]) > 2.2 * fa and _area(o["box"]) > 0.06 * W * H:
            _add(out, "hierarchy", "medium", [o["i"]], f"{_label(o)} outweighs what the scene is about", 14 + (_area(o["box"]) / fa - 2.2) * 8,
                 "make the minor object smaller")
    cx, cy = (focus["box"][0] + focus["box"][2]) / 2, (focus["box"][1] + focus["box"][3]) / 2
    if bg != "map" and (cx < 0.08 * W or cx > 0.92 * W) and focus["role"] != "crowd":
        _add(out, "corner", "medium", [focus["i"]], "the main subject is pushed to the edge of the picture", 16, "bring it toward the center")


def _balance(items, out, sc):
    if (sc.get("bg") or {}).get("type") == "map":
        return
    body = [o for o in items if o["role"] in PERSON + ("prop", "icons", "container") and not o.get("scenery")]
    if not body:
        return
    tot = sum(_area(o["box"]) for o in body) or 1.0
    cx = sum((o["box"][0] + o["box"][2]) / 2 * _area(o["box"]) for o in body) / tot
    x0, x1 = min(o["box"][0] for o in body), max(o["box"][2] for o in body)
    if abs(cx - W / 2) > 0.24 * W and (x1 - x0) < 0.6 * W:
        _add(out, "balance", "low", [o["i"] for o in body], "everything sits on one side and the rest of the picture is empty", 8 + abs(cx - W / 2) * 0.02,
             "center the group")
    covered = sum(_area(o["box"]) for o in items if o["role"] in PERSON + ("prop", "bubble") + TEXTY[:3])
    if covered < 0.07 * W * H:
        _add(out, "empty", "low", [], "the scene looks empty: little is drawn compared with the size of the frame", 6)


def findings(items, sc=None, ctx=None):
    out = []
    _edge_findings(items, out)
    _readability(items, out)
    for k, a in enumerate(items):
        for b in items[k + 1:]:
            _pair(a, b, items, out)
    _tails(items, out)
    _scale_findings(items, out)
    _hierarchy(items, out, sc or {})
    _balance(items, out, sc or {})
    return out


def total_cost(f):
    return sum(x["cost"] for x in f)


def score(f):
    """1.0 = nothing to say about this layout; each finding takes off by its severity."""
    return round(max(0.0, 1.0 - sum(SEV_COST[x["sev"]] for x in f)), 3)


# ---------------------------------------------------------------- repair
def _set_xy(el, x, y):
    el["x"], el["y"] = round(x), round(y)
    el.pop("lon", None)
    el.pop("lat", None)


def _bubble_candidates(it, items):
    """Positions for a speech bubble body that keep its tail on the same tip."""
    el = it["el"]
    body, tip = bubble_geometry(it["probe"])
    if tip is None:
        return
    w, h = body[2] - body[0], body[3] - body[1]
    top = max(TOP_MARGIN + 6 + h / 2, tip[1] - 24 - h / 2 - 150)       # the tail stays short: 24 to ~170 px
    for by in range(int(top), int(tip[1] - 24 - h / 2) + 1, 30):
        for bx in range(int(tip[0] - w / 2 + 44), int(tip[0] + w / 2 - 44) + 1, 40):
            if bx - w / 2 < MARGIN["bubble"] or bx + w / 2 > W - MARGIN["bubble"]:
                continue
            ty = tip[1] - (by + h / 2)
            yield dict(x=bx, y=by, tail=[round(tip[0] - bx), round(ty)]), math.hypot(bx - (body[0] + body[2]) / 2, by - (body[1] + body[3]) / 2)


def _free_candidates(it, rng):
    el = it["probe"]
    x, y = _f(el.get("x"), 960), _f(el.get("y"), 540)
    for dy in range(-rng[1], rng[1] + 1, 40):
        for dx in range(-rng[0], rng[0] + 1, 60):
            if dx or dy:
                yield dict(x=x + dx, y=y + dy), math.hypot(dx, dy)


_spent = [0]
BUDGET = 2500                       # candidate layouts a single repair may try: a hopeless scene stops here, the same way every time


def _try(sc, ctx, idx, patch, items=None, one=None):
    """The findings of the scene with `patch` applied to element `idx` (the scene itself is left as it was). With the
    current `items` and builder only that one element is measured again."""
    _spent[0] += 1
    el = sc["elements"][idx]
    old = {k: el.get(k, None) for k in list(patch) + ["lon", "lat"]}
    el.update(patch)
    if "x" in patch:
        el.pop("lon", None)
        el.pop("lat", None)
    if items is not None and one is not None:
        new = one(idx, el)
        its = [new if o["i"] == idx else o for o in items]
        if new is None:
            its = [o for o in items if o["i"] != idx]
        f = findings(its, sc, ctx)
    else:
        f = findings(build_items(sc, ctx), sc, ctx)
    for k, v in old.items():
        if v is None:
            el.pop(k, None)
        else:
            el[k] = v
    return f


def _out_of_budget():
    return _spent[0] >= BUDGET


def _problems(f):
    return {(x["kind"], tuple(sorted(x["idx"]))) for x in f if x["sev"] in ("high", "medium")}


def _harmless(before, after):
    """A repair may never create a new medium/high problem: it only gets to remove them."""
    return _problems(after) <= _problems(before)


def _movers(items, stage):
    kinds = {1: ("bubble", "title", "label", "stat", "maplabel", "note"),
             2: ("bubble", "title", "label", "stat", "maplabel", "note", "prop", "container", "marker"),
             3: ("bubble", "title", "label", "stat", "maplabel", "note", "prop", "container", "marker", "char", "crowd")}[stage]
    return [o for o in items if o["role"] in kinds and not o.get("fixed")]


PRIORITY = {"bubble": 0, "label": 1, "stat": 1, "note": 1, "title": 2, "maplabel": 2, "prop": 3, "container": 3, "marker": 3, "char": 4, "crowd": 5}


def _fix_pass(sc, ctx, stage, fixes, rounds=4):
    for _ in range(rounds):
        if _out_of_budget():
            return
        items, one = _builder(sc, ctx)
        f = findings(items, sc, ctx)
        bad = {i for x in f if x["sev"] in ("high", "medium") or x["kind"] in ("text_close", "margin") for i in x["idx"]}
        bad |= {i for x in f if x["kind"] == "air" and x["cost"] > 6 for i in x["idx"]} if bad else set()
        if not bad:
            return
        base = total_cost(f)
        changed = False
        movers = sorted((o for o in _movers(items, stage) if o["i"] in bad), key=lambda o: PRIORITY[o["role"]])
        for it in movers:
            idx = it["i"]
            best = None
            if it["role"] == "bubble":
                cands = _bubble_candidates(it, items)
            elif it["role"] in ("char", "crowd"):
                x0 = _f(it["probe"].get("x"), 960)
                cands = (((dict(x=x0 + d)), abs(d)) for d in range(-400, 401, 40) if d)
                cands = ((dict(c, y=_f(it["probe"].get("y"), 900)), dist) for c, dist in cands)
            elif it["role"] == "maplabel":
                cands = _free_candidates(it, (120, 80))
            elif it["role"] == "title":
                cands = _free_candidates(it, (200, 120))
            else:
                cands = _free_candidates(it, (480, 300) if it["role"] != "prop" else (360, 200))
            for patch, dist in cands:
                if _out_of_budget():
                    break
                f1 = _try(sc, ctx, idx, patch, items, one)
                c = total_cost(f1) + 0.012 * dist
                if c < base - 1.0 and _harmless(f, f1) and (best is None or c < best[0]):
                    best = (c, patch, dist)
            if best:
                el = sc["elements"][idx]
                before = (round(_f(el.get("x"), 0)), round(_f(el.get("y"), 0)))
                if it["role"] in ("char", "crowd"):
                    dx = best[1]["x"] - _f(it["probe"].get("x"), 960)
                    for b in items:                       # its speech bubbles go with it
                        if b["role"] == "bubble" and speaker_of(b, items) is it:
                            b["el"]["x"] = round(_f(b["el"].get("x"), 960) + dx)
                el.update(best[1])
                if "x" in best[1]:
                    el.pop("lon", None)
                    el.pop("lat", None)
                    el["x"], el["y"] = round(el["x"]), round(el["y"])
                fixes.append(f"moved {_label(it)} ({before[0]},{before[1]}) -> ({el.get('x')},{el.get('y')})")
                changed = True
                items, one = _builder(sc, ctx)
                f = findings(items, sc, ctx)
                base = total_cost(f)
        if not changed:
            return


def _fix_sizes(sc, ctx, fixes):
    """Things that are the wrong size: text that is too small, characters too small/big or mismatched, a minor object that
    outweighs the subject. Each change is kept only when it does not make the layout worse."""
    for _ in range(3):
        items = build_items(sc, ctx)
        f = findings(items, sc, ctx)
        base = total_cost(f)
        done = False
        for x in sorted((z for z in f if z["sev"] != "info"), key=lambda z: SEV_ORDER[z["sev"]]):
            patch, idx = None, None
            if x["kind"] != "scale_mismatch" and any(i >= 1000 for i in x["idx"]):
                continue                                # a piece inside a group can't be changed on its own
            if x["kind"] == "text_size":
                idx = x["idx"][0]
                el = sc["elements"][idx]
                need = MIN_SIZE.get({"bubble": "bubble", "note": "note"}.get(el.get("type"), "label"), 40)
                patch = dict(size=max(need, _f(el.get("size"), 0)))
            elif x["kind"] in ("char_small", "char_big"):
                idx = x["idx"][0]
                el = sc["elements"][idx]
                s = _f(el.get("scale"), 1.0)
                patch = dict(scale=round(CHAR_MIN_SPEAKER if x["kind"] == "char_small" and s >= CHAR_MIN - 0.02 else CHAR_MIN if x["kind"] == "char_small" else 1.4, 2))
            elif x["kind"] == "scale_mismatch":
                if any(i >= 1000 for i in x["idx"]):
                    continue
                a, b = (sc["elements"][i] for i in x["idx"])
                small = a if _f(a.get("scale"), 1) < _f(b.get("scale"), 1) else b
                big = b if small is a else a
                idx = sc["elements"].index(small)
                patch = dict(scale=round(min(1.25, max(_f(small.get("scale"), 1), _f(big.get("scale"), 1) * 0.72)), 2))
            elif x["kind"] == "hierarchy":
                idx = x["idx"][0]
                el = sc["elements"][idx]
                patch = dict(scale=round(max(0.5, _f(el.get("scale"), 1.0) * 0.8), 2))
            elif x["kind"] == "bubble_fit":
                idx = x["idx"][0]
                el = sc["elements"][idx]
                for k in ("w", "h"):
                    el.pop(k, None)
                fixes.append("let a speech bubble size itself to its words")
                done = True
                break
            if patch is None:
                continue
            el = sc["elements"][idx]
            if "scale" in patch and el.get("type") in PERSON:        # a bigger body must still fit inside the margins
                hw = 115 * patch["scale"] + 4
                nx = min(max(_f(el.get("x"), 960), MARGIN["person"] + hw), W - MARGIN["person"] - hw)
                if abs(nx - _f(el.get("x"), 960)) > 1:
                    patch["x"] = round(nx)
            f1 = _try(sc, ctx, idx, patch)
            if total_cost(f1) <= base + 0.5 and _harmless(f, f1):
                el = sc["elements"][idx]
                el.update(patch)
                fixes.append(f"{x['kind'].replace('_', ' ')}: {', '.join(f'{k}={v}' for k, v in patch.items())}")
                done = True
                break
        if not done:
            return


def _retarget_tails(sc, ctx, fixes):
    items = build_items(sc, ctx)
    people = [o for o in items if o["role"] in PERSON]
    if not people:
        return
    for b in items:
        if b["role"] != "bubble" or target_of(b, items) is not None or b["el"].get("tail") == "none":
            continue
        body, _ = bubble_geometry(b["probe"])
        bx = (body[0] + body[2]) / 2
        near = min(people, key=lambda o: abs((o["box"][0] + o["box"][2]) / 2 - bx))
        if abs((near["box"][0] + near["box"][2]) / 2 - bx) > 520:
            continue                      # nobody is near enough to be the speaker: leave it for a person to look at
        tip = ((near["box"][0] + near["box"][2]) / 2 + 20, near["box"][1] - 4)
        ty = tip[1] - body[3]
        if ty >= 24:
            b["el"]["tail"] = [round(tip[0] - bx), round(ty)]
            fixes.append("pointed a speech bubble at the nearest speaker")


SIMPLE_X = ("char", "crowd", "text", "bubble", "note", "sign", "board", "prop", "counter")


def _recenter(sc, ctx, fixes):
    """Shift a lopsided group toward the middle: only when every element is a plain x-positioned one, so nothing is left behind."""
    els = sc.get("elements") or []
    if any(e.get("type") not in SIMPLE_X or e.get("lon") is not None or e.get("move") for e in els):
        return
    items = build_items(sc, ctx)
    f = [x for x in findings(items, sc, ctx) if x["kind"] == "balance"]
    if not f:
        return
    idxs = set(f[0]["idx"])
    body = [o for o in items if o["i"] in idxs]
    tot = sum(_area(o["box"]) for o in body) or 1.0
    cx = sum((o["box"][0] + o["box"][2]) / 2 * _area(o["box"]) for o in body) / tot
    lo = MARGIN["person"] - min(o["box"][0] for o in items if o["role"] != "panel")
    hi = W - MARGIN["person"] - max(o["box"][2] for o in items if o["role"] != "panel")
    dx = max(min(lo, 0), min(max(hi, 0), W / 2 - cx))                  # all the way to the middle, but never past a margin
    if abs(dx) < 8:
        return
    f0 = findings(items, sc, ctx)
    base = total_cost(f0)
    saved = [(e, _f(e.get("x"), 960)) for e in els]
    for el, x in saved:
        el["x"] = round(x + dx)
    f1 = findings(build_items(sc, ctx), sc, ctx)
    if total_cost(f1) < base - 0.5 and _harmless(f0, f1):
        fixes.append(f"centered the group ({dx:+.0f}px)")
    else:
        for el, x in saved:
            el["x"] = round(x)


# ---------------------------------------------------------------- the camera
def shot_rect(zoom, focus):
    hw, hh = W / (2 * zoom), H / (2 * zoom)
    fx, fy = (focus if isinstance(focus, (list, tuple)) and len(focus) >= 2 else (W / 2, H / 2))[:2]
    fx, fy = min(max(_f(fx, W / 2), hw), W - hw), min(max(_f(fy, H / 2), hh), H - hh)
    return fx - hw, fy - hh, fx + hw, fy + hh


def cropped(sc, zoom, focus, ctx=None):
    """What a close-up would cut in half that the viewer needs: readable text and boards, and the head of the character
    the camera is on. (Other people at the edge of a close-up are ordinary framing.)"""
    x0, y0, x1, y1 = shot_rect(zoom, focus)
    fx, fy = (focus if isinstance(focus, (list, tuple)) and len(focus) >= 2 else (W / 2, H / 2))[:2]
    fx, fy = _f(fx, W / 2), _f(fy, H / 2)
    items = build_items(sc, ctx)
    chars = [o for o in items if o["role"] == "char"]
    star = min(chars, key=lambda o: math.hypot((o["box"][0] + o["box"][2]) / 2 - fx, (o["box"][1] + o["box"][3]) / 2 - fy), default=None)
    cut = []
    for it in items:
        r = it["role"]
        if r in TEXTY + ("container",) and r != "maplabel":
            b = it["box"]
        elif it is star and star is not None and math.hypot((star["box"][0] + star["box"][2]) / 2 - fx, (star["box"][1] + star["box"][3]) / 2 - fy) < 420:
            b = head_zone(it["box"])
        else:
            continue
        inside = b[0] >= x0 - 6 and b[2] <= x1 + 6 and b[1] >= y0 - 6 and b[3] <= y1 + 6
        outside = b[2] <= x0 or b[0] >= x1 or b[3] <= y0 or b[1] >= y1
        if not inside and not outside:
            cut.append(it["el"])
    return cut


def fix_camera(sc, ctx, fixes):
    cam = sc.get("camera")
    for sh in (cam or {}).get("shots") or []:
        z = _f(sh.get("zoom"), 1.0)
        if z < 1.25 or not cropped(sc, z, sh.get("focus"), ctx):
            continue
        was = z
        while z > 1.25 and cropped(sc, z, sh.get("focus"), ctx):
            z = round(z - 0.1, 2)
        if cropped(sc, z, sh.get("focus"), ctx):
            z = 1.0
        sh["zoom"] = z
        fixes.append(f"camera close-up cut something in half: {'eased it from %gx to %gx' % (was, z) if z > 1.0 else 'removed that close-up'}")


def fix_auto_camera(sc, ctx, fixes):
    """The engine adds close-ups on its own (on whoever talks, on a reaction). If one of them would cut a label or speech
    bubble in half, switch the automatic camera off for this scene: a steady shot beats a cropped one."""
    cam = sc.get("camera") or {}
    if cam.get("shots") or cam.get("auto_shots") is False:
        return
    z = cam.get("zoom")
    if _f(z[-1] if isinstance(z, (list, tuple)) and z else z, 1.0) > 1.08:
        return
    for it in build_items(sc, ctx):
        if it["role"] != "char":
            continue
        s_ = max(0.15, _f(it["el"].get("scale"), 1.0))
        x, y = _f(it["probe"].get("x"), 960), _f(it["probe"].get("y"), 900)
        for zoom, focus in ((1.5, (x, y - 260 * s_)), (max(1.25, min(1.9, 1.45 / max(0.6, s_))), (x, y - 220 * s_))):
            if cropped(sc, zoom, focus, ctx):
                sc["camera"] = dict(cam, auto_shots=False)
                fixes.append("turned off the automatic close-up: it would have cut a label or speech bubble in half")
                return


# ---------------------------------------------------------------- entry points
def audit(sc, ctx=None):
    """What is wrong with a scene as it is (nothing changes). Clearance hints ("info") are not reported."""
    return [x for x in findings(build_items(sc, ctx), sc, ctx) if x["sev"] != "info"]


def _fix_once(sc, ctx, fixes):
    _retarget_tails(sc, ctx, fixes)
    _fix_sizes(sc, ctx, fixes)
    for stage in (1, 2, 3):
        _fix_pass(sc, ctx, stage, fixes)
        if not [x for x in audit(sc, ctx) if x["sev"] in ("high", "medium")]:
            break
    _fix_sizes(sc, ctx, fixes)
    _recenter(sc, ctx, fixes)
    fix_camera(sc, ctx, fixes)
    fix_auto_camera(sc, ctx, fixes)


def fix_scene(sc, ctx=None):
    """Repair a scene in place, cheapest change first, until nothing more can be improved (so running it again changes
    nothing). Returns (remaining findings, fixes made, escalate?).
    escalate is True only when a HIGH finding is left after every local step: then (and only then) a new layout is worth asking for."""
    fixes = []
    ctx = ctx or {}
    if not (sc.get("elements") or []):
        return [], fixes, False
    _spent[0] = 0
    for _ in range(5):
        if _out_of_budget():
            break
        n = len(fixes)
        _fix_once(sc, ctx, fixes)
        if len(fixes) == n:
            break
    left = audit(sc, ctx)
    return left, fixes, any(x["sev"] == "high" for x in left)


def explain(f):
    """One plain sentence per finding, worst first."""
    return [x["msg"] for x in sorted(f, key=lambda z: (SEV_ORDER[z["sev"]], -z["cost"]))]


# ---------------------------------------------------------------- the whole video
def consistency(scenes, fix=True, only=None):
    """Rules that only make sense across scenes: one title style, one scale for the people who carry the story.
    scenes = {index: scene}; `only` limits what may be changed (others are only reported).
    Returns [{beat, msg, fixed}]."""
    out = []
    may = (lambda i: only is None or i in only)

    def ctxcost(sc):
        return total_cost(findings(build_items(sc, None), sc, None))
    # 1. titles/banners: one size and one height for every scene's top label
    tops = [(i, el) for i, sc in sorted(scenes.items()) for el in sc.get("elements") or []
            if el.get("type") == "text" and el.get("lon") is None and _f(el.get("y"), 999) <= 190 and _f(el.get("size"), 0) >= 56
            and el.get("exit") is None]
    if len(tops) >= 3:
        size = Counter(round(_f(el.get("size"), 0)) for _, el in tops).most_common(1)[0][0]
        ys = Counter(round(_f(el.get("y"), 0)) for _, el in tops).most_common(1)[0][0]
        for i, el in tops:
            if abs(_f(el.get("size"), 0) - size) > 6 or abs(_f(el.get("y"), 0) - ys) > 12:
                row = dict(beat=i, msg=f"the title here ({_f(el.get('size'), 0):g}px at y={_f(el.get('y'), 0):g}) doesn't match the video's ({size}px at y={ys})", fixed=False)
                if fix and may(i):
                    sc = scenes[i]
                    old, before = (el.get("size"), el.get("y")), ctxcost(sc)
                    bb = text_bbox(el.get("text", ""), _f(el.get("x"), 960), ys, size, el.get("font", "bold"))
                    if bb[0] >= MARGIN["text"] and bb[2] <= W - MARGIN["text"]:
                        el["size"], el["y"] = size, ys
                        if ctxcost(sc) > before + 0.5:
                            el["size"], el["y"] = old                     # it would collide with something: leave it
                        else:
                            row.update(fixed=True, msg=row["msg"] + f": set to the video's style")
                out.append(row)
    # 2. the same person keeps the same size from scene to scene, as a lead with the leads and as a supporting part with the
    #    supporting parts (a figure who carries one scene and stands in the background of another is not inconsistent)
    seen = {}
    for i, sc in sorted(scenes.items()):
        chars = [e for e in sc.get("elements") or [] if e.get("type") == "char" and e.get("lon") is None]
        top = max([_f(e.get("scale"), 1.0) for e in chars] or [1.0])
        for el in chars:
            if el.get("who"):
                lead = _f(el.get("scale"), 1.0) >= 0.9 * top
                seen.setdefault((str(el["who"]).lower(), lead), []).append((i, el))
    for (who, lead), lst in seen.items():
        if len(lst) < 3:
            continue
        scales = sorted(_f(e.get("scale"), 1.0) for _, e in lst)
        med = scales[len(scales) // 2]
        for i, el in lst:
            s = _f(el.get("scale"), 1.0)
            if med and abs(s - med) / med > 0.32 and CHAR_MIN <= med <= CHAR_MAX:
                row = dict(beat=i, msg=f"{el['who']} is drawn at {s:.2f} here and about {med:.2f} in the other {'lead' if lead else 'supporting'} scenes", fixed=False)
                if fix and may(i):
                    sc = scenes[i]
                    f0 = findings(build_items(sc, None), sc, None)
                    el["scale"] = round(med, 2)
                    f1 = findings(build_items(sc, None), sc, None)
                    if total_cost(f1) > total_cost(f0) + 0.5 or not _harmless(f0, f1):
                        el["scale"] = s
                    else:
                        row.update(fixed=True, msg=row["msg"] + ": resized to match")
                out.append(row)
    return out
