"""Compile a scene described in JSON into a Scene (the LLM never writes Python, it writes this JSON).

See studio/engine/schema.py for the format and studio/prompts/scene_language.md for the LLM-facing docs.
"""
import math

from .core import Scene, W, H, norm_enter
from .geo import View, region_geom
from .palette import color as C, INK, RED, NAVY, WHITE, PAPER, SUN, SEA, DARK, darker
from .pen import ARMS, LEGS, resolve_kind
from . import props as P
from .registry import PROPS, resolve_prop, prop_bounds

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
    anchor, fn, _ = PROPS[name]
    s = max(0.1, min(num(el.get("scale"), 1.0), 4.0))
    x, y = pos(el, sc)
    params = dict(el.get("params") or {})
    if name in NO_NORMALIZE:
        rx, ry = x, y
    else:
        x0, y0, x1, y1 = prop_bounds(name)
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
    bx0, by0, bx1, by1 = prop_bounds(name)
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
        sc.map_bg(view, base, sea=C(bg.get("sea"), (156, 205, 230)), land=C(bg.get("land"), (238, 214, 160)),
                  labels=labels)
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
def build_element(sc, el, mood):
    t = el.get("type")
    if t == "char":
        a = anim(el, sc, "pop")
        x, y = pos(el, sc, (960, 900))
        s = max(0.15, min(num(el.get("scale"), 1.0), 2.5))
        idle = a["idle"] if "idle" in el else "bob"
        sc.char(x, y, s, enter=a["enter"], at=a["at"], idle=idle, exit_at=a["exit_at"], move=a["move"],
                z=int(num(el.get("z"), 1)), sfx=a["sfx"], **char_pose(el))
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


def build_scene(scene, idx, dur, mood, text, timer=None):
    """scene: validated scene dict. Returns a Scene ready for render_at()."""
    sc = Scene(idx, dur, mood, text, timer=timer)
    build_background(sc, scene.get("bg"))
    for el in scene.get("elements") or []:
        try:
            build_element(sc, el, mood)
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
    return sc
