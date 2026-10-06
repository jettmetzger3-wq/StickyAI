"""Compile a scene described in JSON into a Scene (the LLM never writes Python, it writes this JSON).

See studio/engine/schema.py for the format and studio/prompts/scene_language.md for the LLM-facing docs.
"""
import math

from .core import Scene, W, H, norm_enter
from .geo import View, region_geom
from .palette import color as C, INK, RED, NAVY, WHITE, PAPER, SUN, SEA, DARK, darker
from .pen import ARMS, LEGS, resolve_kind
from .puppet import ACTIONS, resolve_action
from . import props as P
from .registry import PROPS, resolve_prop, prop_bounds, prop_anchor
from .places import PAINTERS
import random

NO_NORMALIZE = {"wall", "bar_chart", "line_chart", "railway", "skyline", "table", "crowd"}
TEXTISH = ("text", "bubble", "note", "sign", "board")


# ------------------------------------------------------------------ helpers
def num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def pos(el, sc, default=(960, 540)):
    """Element position in screen pixels from x/y or lon/lat (map scenes)."""
    if el.get("lon") is not None and el.get("lat") is not None and sc.view is not None:
        return sc.view.xy(num(el["lon"]), num(el["lat"]))
    return num(el.get("x"), default[0]), num(el.get("y"), default[1])


def point(v, sc):
    if isinstance(v, dict):
        if "lon" in v and "lat" in v and sc.view is not None:
            return sc.view.xy(num(v["lon"]), num(v["lat"]))
        return num(v.get("x"), 960), num(v.get("y"), 540)
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return num(v[0]), num(v[1])
    return 960, 540


def anim(el, sc, default_enter="pop"):
    """Common animation kwargs for Scene.layer()."""
    at = sc.timer.resolve(el.get("at"), 0.0) + num(el.get("delay"), 0) / max(sc.dur, 1e-3)
    exit_at = None
    if el.get("exit") is not None:
        exit_at = sc.timer.resolve(el.get("exit"), None)
    move = None
    mv = el.get("move")
    if isinstance(mv, dict) and (mv.get("dx") or mv.get("dy")):
        m0 = sc.timer.resolve(mv.get("from"), at)
        m1 = sc.timer.resolve(mv.get("to"), min(1.0, m0 + 0.5))
        if m1 <= m0:
            m1 = min(1.0, m0 + 0.3)
        move = (num(mv.get("dx")), num(mv.get("dy")), m0, m1)
    enter = el.get("enter", default_enter)
    if enter in ("none", None, ""):
        enter = None
    idle = el.get("idle")
    if idle in ("none", ""):
        idle = None
    sfx = el.get("sfx", "auto")
    if sfx in ("none", "", None):
        sfx = None
    return dict(enter=norm_enter(enter), at=min(at, 0.98), exit_at=exit_at, move=move, idle=idle, sfx=sfx,
                z=int(num(el.get("z"), 1)))


def luminance(c):
    r, g, b = (v / 255 for v in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_lines(t):
    return str(t if t is not None else "").replace("\\n", "\n")


# ------------------------------------------------------------------ drawing of drawable items (also used by groups)
def draw_prop(p, el, sc):
    name = resolve_prop(el.get("name"))
    if not name:
        sc.warn(f"unknown prop '{el.get('name')}' skipped")
        return
    _, fn, _ = PROPS[name]
    s = max(0.1, min(num(el.get("scale"), 1.0), 4.0))
    x, y = pos(el, sc)
    params = dict(el.get("params") or {})
    anchor = prop_anchor(name, params)
    if name in NO_NORMALIZE:
        rx, ry = x, y
    else:
        x0, y0, x1, y1 = prop_bounds(name, params)
        if anchor == "bottom":
            rx, ry = x - (x0 + x1) / 2 * s, y - y1 * s
        else:
            rx, ry = x - (x0 + x1) / 2 * s, y - (y0 + y1) / 2 * s
    fn(p, rx, ry, s, el.get("color"), params)


def draw_text(p, el, sc):
    x, y = pos(el, sc)
    f = "hand" if el.get("font") in ("hand", "handwritten") else "bold"
    anchor = {"left": "lm", "right": "rm"}.get(el.get("align"), "mm")
    lines = text_lines(el.get("text")).split("\n")
    size = num(el.get("size"), 64)
    for i, ln in enumerate(lines):
        yy = y + (i - (len(lines) - 1) / 2) * size * 1.12
        fill = C(el.get("color"), INK)
        # outline contrasts with the fill: light text gets a dark outline, dark text a white one
        auto_stroke = (20, 20, 30) if luminance(fill) > 0.6 else WHITE
        p.text(ln, x, yy, size, fill, anchor=anchor, stroke=num(el.get("stroke"), 9 if f == "bold" else 7),
               scol=C(el.get("stroke_color"), auto_stroke), f=f)


def bubble_size(el):
    lines = text_lines(el.get("text")).split("\n")
    size = num(el.get("size"), 48)
    longest = max((len(l) for l in lines), default=4)
    w = num(el.get("w"), max(220, min(900, longest * size * 0.56 + 80)))
    h = num(el.get("h"), max(110, len(lines) * size * 1.15 + 60))
    return w, h, size


def bubble_tail(el, w, h):
    t = el.get("tail", "left")
    if isinstance(t, (list, tuple)) and len(t) == 2:
        return num(t[0]), num(t[1])
    return {"left": (-w * 0.25, 80), "right": (w * 0.25, 80), "down": (0, 80), "none": (0, 0)}.get(t, (-w * 0.25, 80))


def draw_bubble(p, el, sc):
    x, y = pos(el, sc)
    w, h, size = bubble_size(el)
    f = "hand" if el.get("font") in ("hand", "handwritten") else "bold"
    P.bubble(p, x, y, w, h, text_lines(el.get("text")), size, tail=bubble_tail(el, w, h), f=f)


def draw_note(p, el, sc):
    x, y = pos(el, sc)
    lines = text_lines(el.get("text")).split("\n")
    size = num(el.get("size"), 46)
    longest = max((len(l) for l in lines), default=4)
    w = num(el.get("w"), max(240, min(700, longest * size * 0.5 + 70)))
    h = num(el.get("h"), max(150, len(lines) * size * 1.1 + 70))
    P.note(p, x, y, text_lines(el.get("text")), size, w, h)


def draw_sign(p, el, sc):
    x, y = pos(el, sc)
    size = num(el.get("size"), 48)
    lines = text_lines(el.get("text")).split("\n")
    longest = max((len(l) for l in lines), default=4)
    w = num(el.get("w"), max(240, min(700, longest * size * 0.6 + 70)))
    h = num(el.get("h"), max(110, len(lines) * size * 1.15 + 50))
    # (x, y) = bottom of the post; the board sits on top of a 170 px post
    P.sign(p, x, y - 170, w, h, text_lines(el.get("text")), size)


def draw_board(p, el, sc):
    x, y = pos(el, sc)
    lines = [str(l) for l in (el.get("lines") or [])][:8]
    size = num(el.get("size"), 50)
    longest = max([len(l) for l in lines] + [len(str(el.get("title") or "")) * 1.2, 6])
    w = num(el.get("w"), max(420, min(1100, longest * size * 0.5 + 120)))
    h = num(el.get("h"), (size * 1.7 if el.get("title") else 0) + len(lines) * size * 1.45 + 60)
    P.board(p, x, y, w, h, str(el.get("title") or ""), lines, size, C(el.get("title_color"), RED))


def draw_icons(p, el, sc):
    name = resolve_prop(el.get("icon") or "mini_carrier") or "mini_carrier"
    n = int(max(1, min(num(el.get("count"), 6), 200)))
    per = int(max(1, num(el.get("per_row"), min(n, 10))))
    s = num(el.get("scale"), 0.35)
    x0, y0 = pos(el, sc)
    bx0, by0, bx1, by1 = prop_bounds(name, el.get("params"))
    gap = num(el.get("gap"), (bx1 - bx0) * s * 1.15 + 6)
    gap_y = num(el.get("gap_y"), (by1 - by0) * s * 1.1 + 6)
    rows = math.ceil(n / per)
    # (x, y) = bottom-center of the grid
    left = x0 - (min(n, per) - 1) * gap / 2
    for i in range(n):
        r, c = divmod(i, per)
        draw_prop(p, dict(name=name, x=left + c * gap, y=y0 - r * gap_y, scale=s, color=el.get("color"),
                          params=el.get("params")), sc)


def draw_shape(p, el, sc):
    shape = el.get("shape", "rect")
    fill = C(el.get("fill"), None) if el.get("fill") not in (None, "none") else None
    stroke = C(el.get("stroke"), INK)
    w = num(el.get("width"), 6)
    if shape == "rect":
        x, y = pos(el, sc)
        ww, hh = num(el.get("w"), 300), num(el.get("h"), 200)
        p.rect(x - ww / 2, y - hh / 2, ww, hh, fill, w, stroke, r=num(el.get("radius"), 0))
    elif shape in ("circle", "ellipse"):
        x, y = pos(el, sc)
        r = num(el.get("r"), 80)
        p.ell(x, y, num(el.get("rx"), r), num(el.get("ry"), r), fill, w, stroke)
    elif shape in ("line", "poly", "polygon"):
        pts = [point(q, sc) for q in (el.get("points") or [])]
        if len(pts) >= 2:
            if shape == "line":
                p.line(pts, w, stroke if not fill else fill, 0.6)
            else:
                p.poly(pts, fill, w, stroke, 0.6)


def draw_char_static(p, el, sc):
    """A stickman drawn into a group layer (no blink)."""
    x, y = pos(el, sc)
    s = max(0.15, min(num(el.get("scale"), 1.0), 2.5))
    p.stick(x, y, s, **char_pose(el))


def char_pose(el):
    arms = el.get("arms") or el.get("pose") or "down"
    if isinstance(arms, str):
        arms = ARMS.get(arms, ARMS["down"])
    legs = el.get("legs") or "stand"
    if isinstance(legs, str):
        legs = LEGS.get(legs, LEGS["stand"])
    prop = el.get("prop")
    if prop and el.get("prop_color"):
        prop = (prop, el.get("prop_color"))
    return dict(kind=resolve_kind(el.get("kind")), arms=arms, legs=legs, mouth=el.get("mouth", "smile"),
                eyes=el.get("eyes", "dot"), look=int(num(el.get("look"), 0)), flip=bool(el.get("flip")),
                extra=tuple(el.get("extras") or ()), prop=prop, hat_color=el.get("hat_color"),
                shadow=el.get("shadow", True) is not False)


DRAWERS = {"prop": draw_prop, "text": draw_text, "bubble": draw_bubble, "note": draw_note, "sign": draw_sign,
           "board": draw_board, "icons": draw_icons, "shape": draw_shape, "char": draw_char_static}


# ------------------------------------------------------------------ backgrounds
def build_background(sc, bg):
    bg = bg or {"type": "paper"}
    t = bg.get("type", "paper")
    if t == "map":
        c = bg.get("center") or [0, 30]
        view = View(num(c[0]), num(c[1]), max(2.0, min(num(bg.get("width"), 40), 360)))
        base = []
        for tr in bg.get("territories") or []:
            g = region_geom(tr)
            if g is not None:
                base.append((g, C(tr.get("color"), RED)))
            else:
                sc.warn(f"map territory not found: {tr}")
        labels = []
        for lab in bg.get("labels") or []:
            if lab.get("lon") is None or lab.get("lat") is None:
                continue
            labels.append((str(lab.get("text", "")), num(lab["lon"]), num(lab["lat"]), num(lab.get("size"), 44),
                           C(lab.get("color"), (70, 60, 50))))
        dark = bg.get("style") == "dark"
        sc.map_bg(view, base, sea=C(bg.get("sea"), (16, 24, 52) if dark else (156, 205, 230)),
                  land=C(bg.get("land"), (44, 50, 66) if dark else (238, 214, 160)), labels=labels,
                  style="dark" if dark else "paper")
        # static decorations on top of the map are drawn as an un-animated layer
        _bg_items(sc, bg)
        return
    if t == "sunburst":
        sc.bg_sunburst(C(bg.get("color"), PAPER), C(bg.get("ray"), SUN))
    elif t == "ground":
        sc.bg_ground(C(bg.get("sky"), (198, 228, 245)), C(bg.get("ground"), (222, 205, 160)), int(num(bg.get("y"), 860)),
                     bg.get("clouds", True) is not False)
    elif t == "sea":
        sc.bg_sea(C(bg.get("sky"), (200, 228, 246)), C(bg.get("sea"), SEA), int(num(bg.get("horizon"), 520)),
                  bg.get("clouds", True) is not False)
    elif t == "night":
        sc.bg_night()
    elif t == "dark":
        sc.bg_dark(C(bg.get("color"), DARK))
    elif t == "city":
        from .places import skyline_key
        time = bg.get("time") if bg.get("time") in ("day", "dawn", "dusk", "night", "storm") else "day"
        sc.bg_city(time, skyline=skyline_key(bg.get("skyline")))
    elif t in ("field", "hills", "desert", "snow", "battlefield"):
        time = bg.get("time") if bg.get("time") in ("day", "dawn", "dusk", "night", "storm") else \
            ("storm" if t == "battlefield" else "day")
        getattr(sc, f"bg_{t}")(time)
    elif t in PAINTERS:
        PAINTERS[t](sc, bg)
    elif t == "interior":
        sc.bg_interior(C(bg.get("wall"), (236, 222, 196)), C(bg.get("floor"), (176, 132, 92)))
    else:
        sc.bg_paper(C(bg.get("color"), PAPER))
    _bg_items(sc, bg)


def _bg_items(sc, bg):
    items = bg.get("items") or []
    if not items:
        return
    with sc.layer(None, 0.0, sfx=None, z=-1) as p:
        for it in items:
            fn = DRAWERS.get(it.get("type", "prop"))
            if fn:
                fn(p, it, sc)


# ------------------------------------------------------------------ elements
WALK_SPEED = {"walk": 260.0, "run": 650.0, "sneak": 150.0}   # px per second


def char_actions(el, sc, x, y, s, at_frac):
    """The element's "do" list -> puppet actions (times in seconds)."""
    out = []
    t_default = sc.T(at_frac) + 0.5
    for k, a in enumerate((el.get("do") or [])[:12]):
        if isinstance(a, str):
            a = {"act": a}
        if not isinstance(a, dict):
            continue
        act = resolve_action(a.get("act") or a.get("action"))
        if not act:
            sc.warn(f"unknown action '{a.get('act')}' skipped")
            continue
        frac = sc.timer.resolve(a.get("at"), None) if a.get("at") is not None else None
        t0 = sc.T(frac) if frac is not None else t_default
        d = dict(act=act, t0=max(0.0, t0))
        if act in WALK_SPEED:
            if a.get("to") is not None:
                tx, ty = point(a["to"], sc)
            else:
                tx = x + num(a.get("dx"), 320 * (-1 if el.get("flip") else 1))
                ty = y + num(a.get("dy"), 0)
            if not a.get("offscreen"):
                tx = min(max(tx, 130 * s), W - 130 * s)
                ty = min(max(ty, 375 * s + 12), H - 15)
            d.update(dx=tx - x, dy=ty - y)
            dur = num(a.get("dur"), max(0.6, math.hypot(tx - x, ty - y) / WALK_SPEED[act]))
        else:
            dur = num(a.get("dur"), ACTIONS[act])
        d["dur"] = max(0.0, min(dur, 20.0))
        if act == "look":
            d["dir"] = -1 if a.get("dir") in ("left", -1, "-1") else 1
        if act == "lean":
            d["amount"] = num(a.get("amount"), 28)
        out.append(d)
        t_default = d["t0"] + d["dur"] + 0.2
    return out


def auto_actions(el, sc, at_s, k):
    """A little life when the storyboard didn't ask for any: poses that imply motion get it."""
    arms = el.get("arms") or el.get("pose")
    r = random.Random(sc.idx * 31 + k)
    end = sc.dur - 0.3
    acts = []
    if arms in ("wave", "wave_left"):
        acts.append(dict(act="wave", t0=at_s + 0.4, dur=min(2.2, end - at_s - 0.4)))
    elif arms in ("cheer", "up"):
        acts.append(dict(act="celebrate", t0=at_s + 0.4, dur=min(1.8, end - at_s - 0.4)))
    elif arms in ("point_left", "point_right"):
        acts.append(dict(act="point", t0=at_s + 0.4, dur=0.8))
    elif el.get("eyes") in ("wide", "worried") and (el.get("mouth") in ("wavy", "scream", "o") or
                                                      "sweat" in (el.get("extras") or [])):
        acts.append(dict(act="tremble", t0=at_s + 0.4, dur=min(1.6, end - at_s - 0.4)))
    elif el.get("eyes") == "angry" and el.get("mouth") in ("scream", "frown", "open"):
        acts.append(dict(act="angry", t0=at_s + 0.4, dur=min(1.2, end - at_s - 0.4)))
    elif sc.mood == "fun" and r.random() < 0.45 and el.get("enter", "pop") in ("pop", "drop", None):
        acts.append(dict(act="hop", t0=at_s + 0.45, dur=0.4))
    return [a for a in acts if a["dur"] > 0.2]


def build_char(sc, el, k, talk=()):
    a = anim(el, sc, "pop")
    x, y = pos(el, sc, (960, 900))
    s = max(0.15, min(num(el.get("scale"), 1.0), 2.5))
    idle = a["idle"] if "idle" in el else "bob"
    acts = char_actions(el, sc, x, y, s, a["at"]) if el.get("do") else []
    if not el.get("do") and el.get("auto", True) is not False:
        acts = auto_actions(el, sc, sc.T(a["at"]), k)
    talk = list(talk) + [(sc.T(sc.timer.resolve(w.get("at"), 0.0)), sc.T(sc.timer.resolve(w.get("at"), 0.0)) + num(w.get("dur"), 2.0))
                         for w in (el.get("talk") or []) if isinstance(w, dict)]
    return sc.char(x, y, s, enter=a["enter"], at=a["at"], idle=idle, exit_at=a["exit_at"], move=a["move"],
                   z=int(num(el.get("z"), 1)), sfx=a["sfx"], actions=acts, talk=talk,
                   life=el.get("life", True) is not False, **char_pose(el))


def build_crowd(sc, el):
    """Rows of the same character with depth (back rows smaller and higher), all alive, sharing actions."""
    a = anim(el, sc, "pop")
    x, y = pos(el, sc, (960, 920))
    n = int(max(2, min(num(el.get("count"), 10), 40)))
    rows = int(max(1, min(num(el.get("rows"), 2 if n > 6 else 1), 4)))
    width = max(200, min(num(el.get("width"), 900), W))
    s0 = max(0.25, min(num(el.get("scale"), 0.6), 1.4))
    per = math.ceil(n / rows)
    r = random.Random(sc.idx * 7 + n)
    shared = {}
    for row in range(rows):                       # back row first so the front row covers it
        depth = rows - 1 - row
        s = s0 * (1 - 0.13 * depth)
        yy = y - depth * 70 * s0
        cnt = min(per, n - row * per) if row < rows - 1 else n - per * (rows - 1)
        cache = shared.setdefault(row, {})
        for i in range(max(cnt, 0)):
            xx = x - width / 2 + (i + 0.5) * width / max(cnt, 1) + r.uniform(-12, 12) + (depth % 2) * width / max(cnt, 1) / 2
            xx = min(max(xx, 130 * s), W - 130 * s)
            sub = dict(el, x=xx, y=yy, scale=s, type="char", auto=False)
            acts = char_actions(sub, sc, xx, yy, s, a["at"]) if el.get("do") else []
            for ac in acts:
                ac["t0"] += r.uniform(0, 0.25)       # a ripple, not perfect unison
            L = sc.char(xx, yy, s, enter=a["enter"], at=min(0.98, a["at"] + r.uniform(0, 0.03)), idle=None,
                        exit_at=a["exit_at"], move=a["move"], z=int(num(el.get("z"), 1)) - depth,
                        sfx=a["sfx"] if i == 0 and row == rows - 1 else None, actions=acts,
                        life=el.get("life", True) is not False, **char_pose(sub))
            if L:
                L["puppet"].cache = cache
                L["pseed"] = 4242 + row
                L["puppet"].phase = r.uniform(0, 6.28)


DIRS = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0), "ne": (0.7, -0.7), "nw": (-0.7, -0.7),
        "se": (0.7, 0.7), "sw": (-0.7, 0.7)}


def build_pointer(sc, el):
    """A big arrow pointing at a spot (a front line, a city, a face), bobbing toward it."""
    a = anim(el, sc, "pop")
    tx, ty = pos(el, sc)
    d = el.get("from", "ne")
    ux, uy = DIRS.get(d, DIRS["ne"])
    size = max(0.4, min(num(el.get("size"), 1.0), 2.5))
    col = C(el.get("color"), RED)
    L = 170 * size
    sx, sy = tx + ux * (L + 30 * size), ty + uy * (L + 30 * size)
    ex, ey = tx + ux * 30 * size, ty + uy * 30 * size
    with sc.layer(a["enter"], a["at"], idle="nudge", exit_at=a["exit_at"], sfx=a["sfx"], z=4) as p:
        ang = math.atan2(ey - sy, ex - sx)
        w = 34 * size
        hw, hl = 62 * size, 70 * size
        bx, by = ex - math.cos(ang) * hl, ey - math.sin(ang) * hl
        nx, ny = -math.sin(ang), math.cos(ang)
        shaft = [(sx + nx * w / 2, sy + ny * w / 2), (bx + nx * w / 2, by + ny * w / 2), (bx + nx * hw, by + ny * hw),
                 (ex, ey), (bx - nx * hw, by - ny * hw), (bx - nx * w / 2, by - ny * w / 2), (sx - nx * w / 2, sy - ny * w / 2)]
        p.poly(shaft, col, 9 * size, (20, 20, 26), 0.4)
    if sc.layers:
        sc.layers[-1]["nudge"] = (-ux, -uy)


def build_element(sc, el, mood, k=0, talk=()):
    t = el.get("type")
    if t == "char":
        build_char(sc, el, k, talk)
        return
    if t == "crowd":
        build_crowd(sc, el)
        return
    if t == "pointer":
        build_pointer(sc, el)
        return
    if t == "territory":
        if sc.view is None:
            sc.warn("territory outside a map scene skipped")
            return
        g = region_geom(el)
        if g is None:
            sc.warn(f"territory not found: {el.get('region') or el.get('countries')}")
            return
        a = anim(el, sc, "wipe_r")
        sc.terr(g, C(el.get("color"), RED), enter=a["enter"], at=a["at"], edur=num(el.get("edur"), 0.9), sfx=a["sfx"],
                outline=C(el.get("outline"), darker(C(el.get("color"), RED), 0.55)), exit_at=a["exit_at"])
        return
    if t == "city":
        if sc.view is None:
            sc.warn("city outside a map scene skipped")
            return
        a = anim(el, sc, "pop")
        sc.city(str(el.get("name", "")), num(el.get("lon")), num(el.get("lat")), at=a["at"], size=num(el.get("size"), 40),
                dx=num(el.get("dx"), 0), dy=num(el.get("dy"), -44), dot=el.get("dot", True) is not False,
                col=C(el.get("color"), INK), enter=a["enter"] or "pop", exit_at=a["exit_at"])
        return
    if t == "arrow":
        a = anim(el, sc, "wipe_r")
        if el.get("points"):
            pts = [point(q, sc) for q in el["points"]]
        else:
            pts = [point(el.get("from"), sc), point(el.get("to"), sc)]
        if len(pts) < 2:
            return
        sc.arrow(pts, col=C(el.get("color"), RED), w=num(el.get("width"), 14), at=a["at"], edur=num(el.get("edur"), 0.7),
                 enter=a["enter"] or "wipe_r", head=el.get("head", True) is not False, z=int(num(el.get("z"), 2)),
                 curve=num(el.get("curve"), 0), exit_at=a["exit_at"], sfx=a["sfx"])
        return
    if t == "group":
        items = el.get("items") or []
        a = anim(el, sc, "pop")
        with sc.layer(a["enter"], a["at"], edur=num(el.get("edur"), 0.38), idle=a["idle"], exit_at=a["exit_at"],
                      sfx=a["sfx"], move=a["move"], z=int(num(el.get("z"), 1))) as p:
            for it in items:
                fn = DRAWERS.get(it.get("type", "prop"))
                if fn:
                    fn(p, it, sc)
        return
    fn = DRAWERS.get(t)
    if not fn:
        sc.warn(f"unknown element type '{t}' skipped")
        return
    default_enter = "pop"
    default_z = 3 if t in TEXTISH else 1
    a = anim(el, sc, default_enter)
    with sc.layer(a["enter"], a["at"], edur=num(el.get("edur"), 0.38), idle=a["idle"], exit_at=a["exit_at"],
                  sfx=a["sfx"], move=a["move"], z=int(num(el.get("z"), default_z))) as p:
        fn(p, el, sc)


def talk_windows(sc, elements):
    """Speech bubbles make the nearest character talk while the bubble is up. {element index: [(t0, t1)]}."""
    chars = [(i, pos(e, sc, (960, 900)), max(0.15, num(e.get("scale"), 1.0)))
             for i, e in enumerate(elements) if e.get("type") == "char"]
    out = {}
    for e in elements:
        if e.get("type") != "bubble" or not chars:
            continue
        bx, by = pos(e, sc)
        w, h, _ = bubble_size(e)
        tx, ty = bubble_tail(e, w, h)
        px, py = bx + tx, by + h / 2 + ty            # where the tail points
        best = min(chars, key=lambda c: math.hypot(c[1][0] - px, c[1][1] - 300 * c[2] - py))
        if math.hypot(best[1][0] - px, best[1][1] - 300 * best[2] - py) > 700:
            continue
        t0 = sc.T(sc.timer.resolve(e.get("at"), 0.0))
        t1 = sc.T(sc.timer.resolve(e.get("exit"), 1.0)) if e.get("exit") is not None else sc.dur
        words = len(text_lines(e.get("text")).split())
        out.setdefault(best[0], []).append((t0, min(t1, t0 + max(1.0, words * 0.38))))
    return out


def build_shots(sc, cam, elements, talk):
    """Camera shots: explicit "shots", or a few automatic ones (close-up on whoever talks, zoom toward where a
    map arrow lands) so long scenes don't sit still."""
    shots = cam.get("shots")
    if isinstance(shots, list):
        for sh in shots[:6]:
            if not isinstance(sh, dict):
                continue
            t = sc.T(sc.timer.resolve(sh.get("at"), 0.0))
            focus = sh.get("focus") or sh.get("center") or sh.get("on")
            sc.shot(t, max(1.0, min(num(sh.get("zoom"), 1.4), 2.2)), point(focus, sc) if focus else None,
                    sh.get("move", "cut"))
        return
    z = cam.get("zoom")
    z_end = num(z[-1] if isinstance(z, (list, tuple)) and z else z, 1.0)
    if cam.get("auto_shots") is False or sc.dur < 4.5 or z_end > 1.08:
        return
    chars = [(i, e) for i, e in enumerate(elements) if e.get("type") == "char"]
    if len(chars) >= 2 and talk:
        i, wins = next(iter(sorted(talk.items(), key=lambda kv: kv[1][0][0])))
        t0, t1 = wins[0]
        if t0 > 1.0 and t1 - t0 >= 1.2 and sc.dur - t0 > 1.6:
            e = elements[i]
            x, y = pos(e, sc, (960, 900))
            s = max(0.15, num(e.get("scale"), 1.0))
            sc.shot(t0, 1.5, (x, y - 260 * s), "cut")
            if sc.dur - t1 > 1.0:
                sc.shot(t1 + 0.2, 1.0, None, "cut")
        return
    if sc.view is not None:
        arrows = [e for e in elements if e.get("type") == "arrow"]
        if arrows:
            e = arrows[-1]
            pts = [point(q, sc) for q in e["points"]] if e.get("points") else [point(e.get("from"), sc), point(e.get("to"), sc)]
            if len(pts) >= 2:
                t = sc.T(sc.timer.resolve(e.get("at"), 0.1)) + num(e.get("edur"), 0.7) + 0.2
                if sc.dur - t > 1.5:
                    (x0, y0), (x1, y1) = pts[0], pts[-1]
                    target = ((x0 + 1.4 * x1) / 2.4, (y0 + 1.4 * y1) / 2.4)
                    z = safe_zoom(sc, elements, target)
                    if z:
                        sc.shot(t, z, target, "pan")


def safe_zoom(sc, elements, center, zooms=(1.22, 1.18, 1.14, 1.1)):
    """The biggest automatic zoom toward `center` that keeps every label, title and bubble in view (or None)."""
    pts = []
    for e in elements:
        if e.get("type") in ("text", "bubble", "note", "board", "sign", "city"):
            x, y = pos(e, sc)
            pts.append((x, y))
    for z in zooms:
        hw, hh = W / (2 * z), H / (2 * z)
        cx = min(max(center[0], hw), W - hw)
        cy = min(max(center[1], hh), H - hh)
        if all(cx - hw + 110 <= x <= cx + hw - 110 and cy - hh + 70 <= y <= cy + hh - 60 for x, y in pts):
            return z
    return None


def build_scene(scene, idx, dur, mood, text, timer=None):
    """scene: validated scene dict. Returns a Scene ready for render_at()."""
    sc = Scene(idx, dur, mood, text, timer=timer)
    build_background(sc, scene.get("bg"))
    elements = scene.get("elements") or []
    talk = talk_windows(sc, elements)
    for k, el in enumerate(elements):
        try:
            build_element(sc, el, mood, k, talk.get(k, ()))
        except Exception as e:  # one bad element should never kill the whole scene
            sc.warn(f"element {el.get('type')} failed: {e}")
    cam = scene.get("camera") or {}
    z = cam.get("zoom") or [1.0, 1.035]
    if not isinstance(z, (list, tuple)):
        z = [1.0, num(z, 1.035)]
    c0 = cam.get("center") or cam.get("from")
    c1 = cam.get("to")
    sc.camera(max(1.0, num(z[0], 1.0)), max(1.0, num(z[-1], 1.035)),
              point(c0, sc) if c0 else None, point(c1, sc) if c1 else None)
    try:
        build_shots(sc, cam, elements, talk)
    except Exception as e:
        sc.warn(f"camera shots failed: {e}")
    return sc
