"""Compile a scene described in JSON into a Scene (the LLM never writes Python, it writes this JSON).

See studio/engine/schema.py for the format and studio/prompts/scene_language.md for the LLM-facing docs.
"""
import math

from .core import Scene, W, H, norm_enter
from .geo import View, region_geom
from .palette import color as C, INK, RED, NAVY, WHITE, PAPER, SUN, SEA, DARK, darker
from .pen import ARMS, LEGS, MOUNTS, resolve_kind
from .puppet import ACTIONS, resolve_action
from . import props as P
from .registry import PROPS, ANIMATED, resolve_prop, prop_bounds, prop_anchor
from .places import PAINTERS as _PLACE_PAINTERS
from .places_work import WORK_PAINTERS
from . import warmap as WM
from . import weather as WX
from . import action_fx as FX
from . import livemap as LM
from . import charts as CH
from . import reactions as RX
import random

PAINTERS = {**_PLACE_PAINTERS, **WORK_PAINTERS}

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
    pose = char_pose(el)
    m = MOUNTS.get(pose.pop("ride", None))
    if m:
        ms = s * m["k"]
        f = -1 if pose.get("flip") else 1
        PROPS[m["prop"]][1](p, x, y, ms, None, {"flip": bool(pose.get("flip")), "saddle": True})
        x, y = x + m["seat"][0] * ms * f, y + m["seat"][1] * ms + (0 if m["stand"] else 112 * s)
        pose["legs"] = LEGS["stand" if m["stand"] else "sit"]
        pose["shadow"] = False
    p.stick(x, y, s, **pose)


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
                shadow=el.get("shadow", True) is not False, coat=el.get("coat"), ride=el.get("ride"))


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
        sc.bg_dark_flag = True
    elif t == "dark":
        sc.bg_dark(C(bg.get("color"), DARK))
        sc.bg_dark_flag = True
    elif t == "city":
        from .places import skyline_key
        time = bg.get("time") if bg.get("time") in ("day", "dawn", "dusk", "night", "storm") else "day"
        sc.bg_city(time, skyline=skyline_key(bg.get("skyline")))
    elif t in ("field", "hills", "desert", "snow"):
        time = bg.get("time") if bg.get("time") in ("day", "dawn", "dusk", "night", "storm") else "day"
        getattr(sc, f"bg_{t}")(time)
    elif t in PAINTERS:
        PAINTERS[t](sc, bg)
    elif t == "interior":
        sc.bg_interior(C(bg.get("wall"), (236, 222, 196)), C(bg.get("floor"), (176, 132, 92)))
    else:
        sc.bg_paper(C(bg.get("color"), PAPER))
    if bg.get("clouds", True) is not False:
        sc.drift_clouds()
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
        if act == "react":
            from .puppet import EXPRESSIONS
            d["expr"] = a.get("expr") if a.get("expr") in EXPRESSIONS else "surprise"
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


STEP_EVERY = {"walk": 0.32, "run": 0.2, "sneak": 0.45}


def action_sounds(sc, acts, crowd=False):
    """Footsteps, jumps, thuds and cheers for a character's actions (mixed quietly under the voice)."""
    for a in acts:
        act, t0, d = a["act"], a["t0"], a.get("dur", 1.0)
        if act in STEP_EVERY:
            t = t0 + 0.05
            while t < t0 + d:
                sc.sfx.append((t, "step_soft" if act == "sneak" or crowd else "step"))
                t += STEP_EVERY[act]
        elif act in ("jump", "hop"):
            sc.sfx.append((t0, "jump"))
        elif act == "faint":
            sc.sfx.append((t0 + d * 0.9, "thud"))
        elif act in ("cheer", "celebrate") and crowd:
            sc.sfx.append((t0, "cheer"))


def talk_sounds(sc, talk, kind, s, seed=0):
    """Little 'blah blah' syllables while a character talks; bigger characters sound lower."""
    r = random.Random(seed)
    hz = 360 / max(0.5, s) ** 0.5 * (1 + (sum(map(ord, str(kind))) % 5 - 2) * 0.06)
    for t0, t1 in talk:
        t, k = t0 + 0.04, 0
        while t < t1 - 0.05:
            sc.sfx.append((round(t, 3), f"blip:{hz:.0f}"))
            k += 1
            t += r.uniform(0.09, 0.15) + (0.12 if k % 4 == 0 else 0)


def build_char(sc, el, k, talk=()):
    a = anim(el, sc, "pop")
    x, y = pos(el, sc, (960, 900))
    s = max(0.15, min(num(el.get("scale"), 1.0), 6.0 if el.get("peek") else 2.5))
    idle = a["idle"] if "idle" in el else "bob"
    acts = char_actions(el, sc, x, y, s, a["at"]) if el.get("do") else []
    if not el.get("do") and el.get("auto", True) is not False:
        acts = auto_actions(el, sc, sc.T(a["at"]), k)
    acts = RX.merge(acts, getattr(sc, "reacts", {}).get(k, []), sc.T(a["at"]),
                    sc.T(a["exit_at"]) if a["exit_at"] is not None else None, sc.dur)
    talk = list(talk) + [(sc.T(sc.timer.resolve(w.get("at"), 0.0)), sc.T(sc.timer.resolve(w.get("at"), 0.0)) + num(w.get("dur"), 2.0))
                         for w in (el.get("talk") or []) if isinstance(w, dict)]
    action_sounds(sc, acts)
    if not el.get("narrator"):               # the host talks with the narrator's voice, not in blips
        talk_sounds(sc, talk, el.get("kind"), s, k)
    for act in acts:
        if act["act"] == "slash" or (act["act"] == "fight" and el.get("prop") in ("sword", "spear")):
            if not hasattr(sc, "fighters"):
                sc.fighters = []
            sc.fighters.append(dict(x=x, y=y, s=s, t0=act["t0"], dur=act["dur"]))
    return sc.char(x, y, s, enter=a["enter"], at=a["at"], idle=idle, exit_at=a["exit_at"], move=a["move"],
                   z=int(num(el.get("z"), 1)), sfx=a["sfx"], actions=acts, talk=talk,
                   life=el.get("life", True) is not False, peek=bool(el.get("peek")), **char_pose(el))


def build_crowd(sc, el, k=0):
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
            acts = RX.merge(acts, getattr(sc, "reacts", {}).get(k, []), sc.T(a["at"]),
                            sc.T(a["exit_at"]) if a["exit_at"] is not None else None, sc.dur)
            for ac in acts:
                ac["t0"] += r.uniform(0, 0.25)       # a ripple, not perfect unison
            if row == rows - 1 and i == 0:
                action_sounds(sc, acts, crowd=True)
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
        build_crowd(sc, el, k)
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
                col=C(el.get("color"), INK), enter=a["enter"] or "pop", exit_at=a["exit_at"],
                capital=bool(el.get("capital")))
        if el.get("capital"):
            x, y = sc.view.xy(num(el.get("lon")), num(el.get("lat")))
            ring = LM.Ring(x, y, sc.T(a["at"]) + 0.15)
            sc.fx(ring.frame, ring.box, None, 0.0, edur=0, z=2)
        return
    if t == "arrow":
        a = anim(el, sc, "wipe_r")
        if el.get("points"):
            pts = [point(q, sc) for q in el["points"]]
        else:
            pts = [point(el.get("from"), sc), point(el.get("to"), sc)]
        if len(pts) < 2:
            return
        edur = num(el.get("edur"), 0.7)
        sc.arrow(pts, col=C(el.get("color"), RED), w=num(el.get("width"), 14), at=a["at"], edur=edur,
                 enter=a["enter"] or "wipe_r", head=el.get("head", True) is not False, z=int(num(el.get("z"), 2)),
                 curve=num(el.get("curve"), 0), exit_at=a["exit_at"], sfx=a["sfx"])
        if el.get("units"):
            build_marchers(sc, el, pts, a, edur)
        return
    if t == "battle":
        build_battle(sc, el)
        return
    if t == "empire":
        build_empire(sc, el)
        return
    if t == "chart":
        build_chart(sc, el)
        return
    if t == "timeline":
        build_timeline(sc, el, mood)
        return
    if t == "compare":
        build_compare(sc, el, mood)
        return
    if t == "split":
        build_split(sc, el, mood)
        return
    if t == "route":
        build_route(sc, el)
        return
    if t == "front":
        build_front(sc, el)
        return
    if t == "counter":
        build_counter(sc, el)
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
    if t == "prop" and (prop_acts(el) or (resolve_prop(el.get("name")) == "explosion" and
                                          el.get("animate", True) is not False)):
        build_prop_fx(sc, el)
        return
    if t == "prop" and resolve_prop(el.get("name")) in ANIMATED and el.get("animate", True) is not False:
        build_moving_prop(sc, el)
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


def build_moving_prop(sc, el):
    """A prop that moves on its own (windmill sails, a waving flag, flames, smoke...), redrawn a few times a second."""
    name = resolve_prop(el.get("name"))
    params = dict(el.get("params") or {})
    s = max(0.1, min(num(el.get("scale"), 1.0), 4.0))
    x, y = pos(el, sc)
    x0, y0, x1, y1 = prop_bounds(name, params)
    w, h = (x1 - x0) * s, (y1 - y0) * s
    m = 0.15 * max(w, h) + 30
    if prop_anchor(name, params) == "bottom":
        box = (x - w / 2 - m, y - h - m, w + 2 * m, h + m + 12)
    else:
        box = (x - w / 2 - m, y - h / 2 - m, w + 2 * m, h + 2 * m)
    local = dict(el, x=x - box[0], y=y - box[1], lon=None, lat=None)

    def draw(p, tl):
        draw_prop(p, dict(local, params=dict(params, t=tl)), sc)

    a = anim(el, sc, "pop")
    sc.dynamic(draw, box, a["enter"], a["at"], edur=num(el.get("edur"), 0.38), idle=a["idle"], exit_at=a["exit_at"],
               sfx=a["sfx"], move=a["move"], z=int(num(el.get("z"), 1)), period=ANIMATED[name])


# ------------------------------------------------------------------ action moments (see action_fx.py)
def prop_acts(el):
    return [a for a in (el.get("do") or []) if isinstance(a, dict) and FX.resolve_prop_act(a.get("act"))]


def build_prop_fx(sc, el):
    """A prop that fires, explodes, collapses, sinks or shakes at a moment (or the explosion prop bursting in)."""
    from .pen import Pen
    from PIL import Image
    name = resolve_prop(el.get("name")) or "explosion"
    params = dict(el.get("params") or {})
    s = max(0.1, min(num(el.get("scale"), 1.0), 4.0))
    x, y = pos(el, sc)
    x0, y0, x1, y1 = prop_bounds(name, params)
    w, h = (x1 - x0) * s, (y1 - y0) * s
    m = 30
    if prop_anchor(name, params) == "bottom":
        box = (x - w / 2 - m, y - h - m, w + 2 * m, h + m + 14)
    else:
        box = (x - w / 2 - m, y - h / 2 - m, w + 2 * m, h + 2 * m)
    p = Pen(sc.seed + 77, rgba=True, size=(box[2], box[3]))
    draw_prop(p, dict(el, x=x - box[0], y=y - box[1], lon=None, lat=None, params=dict(params, t=0.0)), sc)
    img = p.im.convert("RGBa").resize((int(box[2]), int(box[3])), Image.LANCZOS).convert("RGBA")
    bb = img.getbbox()
    if not bb:
        return
    img = img.crop(bb)
    bx, by = box[0] + bb[0], box[1] + bb[1]
    a = anim(el, sc, "pop")
    at_s = sc.T(a["at"])
    events, t_next = [], at_s + 0.6
    for act in prop_acts(el)[:4]:
        kind = FX.resolve_prop_act(act.get("act"))
        t0 = sc.T(sc.timer.resolve(act.get("at"), 0.0)) if act.get("at") is not None else t_next
        t0 = max(t0, at_s + 0.1)
        dur = max(0.4, min(num(act.get("dur"), FX.ACT_DUR[kind]), 10.0))
        events.append(dict(act=kind, t0=t0, dur=dur, target=act.get("target")))
        t_next = t0 + dur + 0.3
    burst = at_s if name == "explosion" and el.get("animate", True) is not False else None
    fx = FX.PropFX(name, img, bx, by, s, bool(params.get("flip")), events, sc.seed + len(sc.layers), burst)
    enter = None if burst is not None else a["enter"]
    sc.fx(fx.frame, fx.box, enter, a["at"], edur=num(el.get("edur"), 0.38),
          idle="pulse" if burst is not None and not a["idle"] else a["idle"], exit_at=a["exit_at"],
          sfx=a["sfx"] if burst is None else None, move=a["move"], z=int(num(el.get("z"), 1)),
          anchor=(x, y))
    sc.sfx.extend(fx.sounds)
    for e in events:
        if e["act"] == "fire" and e.get("target") is not None:
            cannonball(sc, fx, e, point(e["target"], sc))


def cannonball(sc, fx, e, target):
    """The shot flies from the muzzle to the target and explodes there."""
    mx, my = fx._muzzles()[0]
    sx, sy = fx.box[0] + mx, fx.box[1] + my
    tx, ty = target
    flight = max(0.35, min(math.hypot(tx - sx, ty - sy) / 1800, 1.0))
    t0 = e["t0"] + 0.03
    pad = 60
    box = (min(sx, tx) - pad, min(sy, ty) - 200 - pad, abs(tx - sx) + 2 * pad, abs(ty - sy) + 200 + 2 * pad)
    ball = FX.sprites()["ball"]
    empty = blank_rgba(1, 1)

    def frame(t):
        q = (t - t0) / flight
        if not 0 <= q < 1:
            return empty
        cv = blank_rgba(int(box[2]), int(box[3]))
        bx = sx + (tx - sx) * q - box[0]
        by = sy + (ty - sy) * q - 4 * 160 * q * (1 - q) - box[1]
        FX.put(cv, ball, bx, by, fx.s * 1.2)
        return cv

    sc.fx(frame, box, None, 0.0, edur=0, z=4)
    hit = FX.burst_at(tx, ty, max(0.6, fx.s), t0 + flight, seed=sc.seed + 5)
    sc.fx(hit.frame, hit.box, None, 0.0, edur=0, z=4)
    sc.sfx.append((t0 + flight, "boom"))


def blank_rgba(w, h):
    from PIL import Image
    return Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))


def sword_clashes(sc):
    """Two characters slashing at each other: sparks and a clang on every strike; alone: a swish."""
    fighters = getattr(sc, "fighters", [])
    used = set()
    spark = FX.spark_sprite()
    for i, a in enumerate(fighters):
        if i in used:
            continue
        partner = None
        for j, b in enumerate(fighters):
            if j == i or j in used:
                continue
            close = abs(a["x"] - b["x"]) < 620 * max(a["s"], b["s"]) and abs(a["y"] - b["y"]) < 200
            overlap = a["t0"] < b["t0"] + b["dur"] and b["t0"] < a["t0"] + a["dur"]
            if close and overlap:
                partner = j
                break
        times = FX.strike_times(a["t0"], a["dur"])[:10]
        if partner is None:
            for t in times[:8]:
                sc.sfx.append((t, "swish"))
            continue
        b = fighters[partner]
        used.update((i, partner))
        lo, hi = max(a["t0"], b["t0"]), min(a["t0"] + a["dur"], b["t0"] + b["dur"])
        times = [t for t in times if lo <= t <= hi]
        cx = (a["x"] + b["x"]) / 2
        cy = (a["y"] - 212 * a["s"] + b["y"] - 212 * b["s"]) / 2
        sz = 260 * max(a["s"], b["s"])
        box = (cx - sz / 2, cy - sz / 2, sz, sz)
        empty = blank_rgba(1, 1)

        def frame(t, times=times, sz=sz, k=max(a["s"], b["s"])):
            for ts in times:
                if 0 <= t - ts < 0.13:
                    cv = blank_rgba(int(sz), int(sz))
                    FX.put(cv, spark, sz / 2, sz / 2, k * (1.3 + 3 * (t - ts)), 1 - 0.6 * (t - ts) / 0.13)
                    return cv
            return empty

        sc.fx(frame, box, None, 0.0, edur=0, z=5)
        for t in times:
            sc.sfx.append((t, "clang"))


# ------------------------------------------------------------------ living maps (see livemap.py)
def build_empire(sc, el):
    """An empire (or any country) whose borders change over the years, with the year ticking in a corner."""
    if sc.view is None:
        sc.warn("empire outside a map scene skipped")
        return
    raw = [st for st in (el.get("steps") or []) if isinstance(st, dict)][:6]
    steps = []
    for k, st in enumerate(raw):
        g = region_geom(st)
        if g is None:
            sc.warn(f"empire step not found: {st.get('region') or st.get('countries')}")
            continue
        default = 0.08 + 0.72 * k / max(1, len(raw) - 1)
        t0 = sc.T(sc.timer.resolve(st.get("at"), default)) if st.get("at") is not None else sc.T(default)
        year = num(st.get("year"), None) if st.get("year") is not None else None
        steps.append((t0, g, year))
    if not steps:
        return
    steps.sort(key=lambda s_: s_[0])
    dark = getattr(sc, "map_style", "paper") == "dark"
    col = C(el.get("color"), RED)
    emp = LM.Empire(sc, steps, col, (245, 245, 250) if dark else darker(col, 0.55))
    a = anim(el, sc, "fade")
    t_first = steps[0][0]
    sc.fx(emp.frame, emp.box, a["enter"] or "fade", t_first / sc.dur, edur=0.6, exit_at=a["exit_at"],
          z=int(num(el.get("z"), 0)))
    for t0, _, _ in steps[1:]:
        sc.sfx.append((t0, "swish"))
    if any(y is not None for _, _, y in steps) and el.get("show_year", True) is not False:
        xy = point(el.get("year_at"), sc) if el.get("year_at") is not None else (290, 120)
        yl = LM.YearLabel(emp.year_at, xy[0], xy[1], num(el.get("year_size"), LM.YEAR_SIZE), dark, emp.bc)
        sc.fx(yl.frame, yl.box, "pop", t_first / sc.dur, z=4)
        for t0, _, _ in steps[1:]:
            for i in range(6):
                sc.sfx.append((t0 + LM.STEP_FADE * i / 6, "tick1"))
    if el.get("name"):
        g = steps[0][1]                     # name the empire where it started
        c = g.representative_point()
        lon, lat = (num(el["label_at"][0]), num(el["label_at"][1])) if isinstance(el.get("label_at"), list) and \
            len(el["label_at"]) == 2 else (c.x, c.y)
        with sc.layer("pop", min(0.95, (steps[-1][0] + LM.STEP_FADE) / sc.dur), z=3, sfx=None,
                      exit_at=a["exit_at"]) as p:
            sc._map_label(p, str(el["name"])[:30], lon, lat, num(el.get("size"), 54))


def build_route(sc, el):
    """A route that draws itself (trade routes, voyages, migrations), a ship / caravan / walker riding the tip."""
    if el.get("points"):
        pts = [point(q, sc) for q in el["points"]]
    else:
        pts = [point(el.get("from"), sc), point(el.get("to"), sc)]
    if len(pts) < 2:
        return
    if len(pts) == 2 and num(el.get("curve"), 0):
        (x1, y1), (x2, y2) = pts
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        nx, ny = -(y2 - y1), (x2 - x1)
        nn = math.hypot(nx, ny) or 1
        cx, cy = mx + nx / nn * num(el.get("curve")), my + ny / nn * num(el.get("curve"))
        pts = [((1 - u) ** 2 * x1 + 2 * (1 - u) * u * cx + u * u * x2, (1 - u) ** 2 * y1 + 2 * (1 - u) * u * cy + u * u * y2)
               for u in [i / 30 for i in range(31)]]
    a = anim(el, sc, None)
    length = sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip(pts, pts[1:]))
    dur = max(0.6, min(num(el.get("dur"), length / 650), 8.0))
    style = el.get("style") if el.get("style") in ("dashed", "dotted", "solid") else "dashed"
    route = LM.Route(pts, C(el.get("color"), RED), max(4.0, min(num(el.get("width"), 10), 24)), style,
                     sc.T(a["at"]), dur, el.get("icon") or el.get("units"), max(0.5, min(num(el.get("icon_scale"), 1.0), 2.5)),
                     sc.seed + len(sc.layers))
    sc.fx(route.frame, route.box, None, a["at"], edur=0, exit_at=a["exit_at"], z=int(num(el.get("z"), 2)))
    sc.sfx.append((sc.T(a["at"]), "swish"))


# ------------------------------------------------------------------ charts and timelines (see charts.py)
def dark_bg(sc):
    return getattr(sc, "bg_dark_flag", False) or getattr(sc, "map_style", "paper") == "dark"


def build_chart(sc, el):
    rows = []
    for k, d in enumerate((el.get("data") or [])[:10]):
        if isinstance(d, dict):
            rows.append((str(d.get("label", ""))[:18], num(d.get("value"), 0.0), C(d.get("color"), CH.SERIES[k % 8])))
    if not rows:
        sc.warn("chart without data skipped")
        return
    a = anim(el, sc, "pop")
    x, y = pos(el, sc, (960, 470))
    w = max(400.0, min(num(el.get("w"), 1100), W - 40))
    h = max(300.0, min(num(el.get("h"), 620), 860))
    style = el.get("style") if el.get("style") in ("bar", "hbar", "line") else "bar"
    ch = CH.Chart(style, rows, x, y, w, h, str(el.get("title") or "")[:40], sc.T(a["at"]) + 0.35,
                  num(el.get("dur"), 1.6), str(el.get("prefix") or ""), str(el.get("suffix") or ""),
                  int(num(el.get("decimals"), 0)), el.get("max"), dark_bg(sc))
    sc.fx(ch.frame, ch.box, a["enter"], a["at"], edur=0.38, idle=a["idle"], exit_at=a["exit_at"], sfx=a["sfx"],
          move=a["move"], z=int(num(el.get("z"), 2)))
    t0 = sc.T(a["at"]) + 0.35
    for i in range(8):
        sc.sfx.append((t0 + num(el.get("dur"), 1.6) * i / 8, "tick1"))


def build_timeline(sc, el, mood):
    evs = []
    raw = [e for e in (el.get("events") or []) if isinstance(e, dict) and e.get("year") is not None][:8]
    for k, e in enumerate(raw):
        default = 0.12 + 0.7 * k / max(1, len(raw) - 1)
        evs.append((sc.T(sc.timer.resolve(e.get("at"), default)) if e.get("at") is not None else sc.T(default),
                    num(e.get("year")), str(e.get("label", ""))[:24], C(e.get("color"), None)))
    if not evs:
        sc.warn("timeline without events skipped")
        return
    years = [e[1] for e in evs]
    span = max(1.0, max(years) - min(years))
    y_from = num(el.get("from"), min(years) - span * 0.08)
    y_to = num(el.get("to"), max(years) + span * 0.08)
    a = anim(el, sc, "wipe_right")
    yy = max(300.0, min(num(el.get("y"), 640), 800))
    x0, x1 = num(el.get("x0"), 150), num(el.get("x1"), 1740)
    dark = dark_bg(sc)
    col = C(el.get("color"), RED)
    tl = CH.Timeline(x0, x1, yy, y_from, y_to, evs, col, dark)
    with sc.layer(a["enter"] or "wipe_right", a["at"], edur=0.7, exit_at=a["exit_at"], sfx=a["sfx"], z=1) as p:
        tl.draw_axis(p, CH.nice_ticks(y_from, y_to, 6))
    ink, halo = tl.ink, tl.halo
    for k, (t0, year, label, ecol) in enumerate(sorted(evs, key=lambda e: e[1])):
        xx = tl.xof(year)
        lift = 0 if k % 2 == 0 else 110
        with sc.layer("drop" if mood != "somber" else "fade", t0 / sc.dur, edur=0.4, exit_at=a["exit_at"], z=3) as p:
            CH.marker(p, xx, yy - 6, ecol or col)
            p.line([(xx, yy - 64), (xx, yy - 84 - lift)], 4, ink, 0.2)
            p.text(WM.fmt_count(year, "year"), xx, yy - 108 - lift, 42, ecol or col, stroke=7, scol=halo)
            if label:
                p.text(label, xx, yy - 156 - lift, 46, ink, stroke=7, scol=halo)
    if el.get("travel", True) is not False and len(evs) > 1:
        order = sorted(evs, key=lambda e: e[0])
        stops = [(t0, tl.xof(year)) for t0, year, _, _ in order]
        box = (x0 - 60, yy + 70, x1 - x0 + 120, 60)
        cache = {}

        def frame(t):
            if t < stops[0][0]:
                return CH.blank()
            x = stops[0][1]
            for (ta, xa), (tb, xb) in zip(stops, stops[1:]):
                if t >= tb:
                    x = xb
                elif t >= tb - 0.5:
                    q = CH.ease_out((t - (tb - 0.5)) / 0.5)
                    x = xa + (xb - xa) * q
                    break
                else:
                    x = xa
                    break
            key = int(x)
            im = cache.get("cv")
            if im is None:
                from .pen import Pen
                p = Pen(4, rgba=True, size=(60, 60))
                p.poly([(30, 6), (8, 50), (52, 50)], col, 5, INK)
                im = cache["cv"] = CH._finish(p, 60, 60)
            cv = CH.blank(box[2], box[3])
            cv.alpha_composite(im, (int(min(max(0, key - box[0] - 30), box[2] - 60)), 0))
            return cv

        sc.fx(frame, box, None, 0.0, edur=0, z=3)
    for t0, *_ in evs:
        sc.sfx.append((t0, "pop"))


def build_compare(sc, el, mood):
    """Two to four things side by side as circles whose AREA matches their numbers (army sizes, populations)."""
    items = [it for it in (el.get("items") or []) if isinstance(it, dict)][:4]
    if not items:
        sc.warn("compare without items skipped")
        return
    vals = [max(0.0, num(it.get("value"), 0.0)) for it in items]
    vmax = max(vals) or 1.0
    max_r = max(80.0, min(num(el.get("size"), 230), 300))
    rs = [max(18.0, max_r * math.sqrt(v / vmax)) for v in vals]
    gap = 70
    total = sum(2 * r for r in rs) + gap * (len(rs) - 1)
    if total > W - 120:
        k = (W - 120) / total
        rs = [r * k for r in rs]
        total = W - 120
    a = anim(el, sc, "grow")
    base_y = max(2 * max(rs) + 160, min(num(el.get("y"), 800), 860))
    cx = num(el.get("x"), 960) - total / 2
    at0 = a["at"]
    dark = dark_bg(sc)
    ink = (238, 240, 246) if dark else INK
    for k, (it, v, r) in enumerate(zip(items, vals, rs)):
        x = cx + r
        cx += 2 * r + gap
        col = C(it.get("color"), CH.SERIES[k % 8])
        at = min(0.9, at0 + 0.12 * k)
        with sc.layer("grow" if mood != "somber" else "fade", at, edur=0.6, exit_at=a["exit_at"], z=1) as p:
            light = tuple(int(c + (255 - c) * 0.55) for c in col)
            p.circ(x, base_y - r, r, light, 7, col)
            icon = resolve_prop(it.get("icon")) if it.get("icon") else None
            if icon and r > 40:
                x0_, y0_, x1_, y1_ = prop_bounds(icon, {})
                s_ = min(1.3 * r / max(1.0, x1_ - x0_), 1.3 * r / max(1.0, y1_ - y0_))
                yy = base_y - r + ((y1_ - y0_) * s_ / 2 if prop_anchor(icon, {}) == "bottom" else 0)
                PROPS[icon][1](p, x, yy, s_, None, {})
        if it.get("label"):
            build_element(sc, {"type": "text", "text": str(it["label"])[:20], "x": round(x), "y": round(base_y + 46),
                               "size": 44, "color": "#EBEBF5" if dark else None, "at": at, "z": 3}, mood)
        build_element(sc, {"type": "counter", "from": 0, "to": v, "x": round(x), "y": round(base_y - 2 * r - 44),
                           "size": max(44, min(80, r * 0.5)), "prefix": it.get("prefix", el.get("prefix", "")),
                           "suffix": it.get("suffix", el.get("suffix", "")), "format": "number", "at": at,
                           "dur": 1.2, "color": "#EBEBF5" if dark else None}, mood)


def build_split(sc, el, mood):
    """Then vs now: a divider down the middle, a heading on each side, the "then" side in old-photo sepia."""
    a = anim(el, sc, "pop")
    with sc.layer("wipe_down", a["at"], edur=0.5, sfx=None, z=1) as p:
        p.line([(W / 2, -10), (W / 2, H - 170)], 12, INK, 0.3)
    left, right = str(el.get("left") or "THEN")[:16], str(el.get("right") or "NOW")[:16]
    for txt, x in ((left, W / 4), (right, 3 * W / 4)):
        build_element(sc, {"type": "text", "text": txt, "x": round(x), "y": 92, "size": 84, "at": a["at"],
                           "z": 4}, mood)
    tint = el.get("tint", "left")
    if tint in ("left", "right"):
        sc.overlay(CH.SplitTint(tint).apply, z=2.4)


# ------------------------------------------------------------------ war maps (see warmap.py)
def build_marchers(sc, el, pts, a, edur):
    """Soldiers (or a tank, a ship...) marching along an arrow, a little behind its tip."""
    if len(pts) == 2 and num(el.get("curve"), 0):
        (x1, y1), (x2, y2) = pts
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        nx, ny = -(y2 - y1), (x2 - x1)
        nn = math.hypot(nx, ny) or 1
        cx, cy = mx + nx / nn * num(el.get("curve")), my + ny / nn * num(el.get("curve"))
        pts = [((1 - u) ** 2 * x1 + 2 * (1 - u) * u * cx + u * u * x2, (1 - u) ** 2 * y1 + 2 * (1 - u) * u * cy + u * u * y2)
               for u in [i / 24 for i in range(25)]]
    units = str(el.get("units"))
    prop = resolve_prop(units)
    n = int(max(1, min(num(el.get("count"), 1 if prop else 4), 8)))
    s = max(0.4, min(num(el.get("unit_scale"), 1.0), 2.5))
    col = C(el.get("unit_color") or el.get("color"), RED)
    t0 = sc.T(a["at"])
    march = max(edur, num(el.get("march"), max(2.0, edur * 2.5)))
    box = WM.bbox(pts, 140 * s)

    def draw(p, tl):
        q = min(1.0, tl / march) * (1 + 0.07 * (n - 1))
        local = [(x - box[0], y - box[1]) for x, y in pts]
        WM.draw_marchers(p, local, min(q, 1.0 + 0.07 * (n - 1)), units, n, col, s, tl)

    sc.dynamic(draw, box, None, a["at"], edur=0, exit_at=a["exit_at"], sfx=None, z=int(num(el.get("z"), 2)) + 1,
               fps=12)


def build_battle(sc, el):
    a = anim(el, sc, "pop")
    x, y = pos(el, sc)
    s = max(0.4, min(num(el.get("size"), 1.0), 2.5))
    label = str(el.get("label") or el.get("text") or "")[:24]
    box = (x - 120 * s, y - 120 * s, 240 * s, 240 * s + (90 * s if label else 0))
    if label:
        box = (min(box[0], x - len(label) * 14 * s - 20), box[1], max(box[2], len(label) * 28 * s + 40), box[3])

    def draw(p, tl):
        WM.draw_battle(p, x - box[0], y - box[1], s, label, math.sin(2 * math.pi * tl / 0.8))

    sfx = a["sfx"] if el.get("sfx") is not None else "boom"
    sc.dynamic(draw, box, a["enter"] or "pop", a["at"], edur=0.38, exit_at=a["exit_at"], sfx=None,
               z=int(num(el.get("z"), 3)), fps=12, period=0.8)
    if sfx and sfx != "auto":
        sc.sfx.append((sc.T(a["at"]), sfx))
    elif sfx == "auto":
        sc.sfx.append((sc.T(a["at"]), "boom"))


def front_keys(el, sc):
    """[(t seconds, [24 points])] for a front line that may move over time."""
    keys = []
    if isinstance(el.get("keys"), list):
        for k in el["keys"][:6]:
            if isinstance(k, dict) and isinstance(k.get("points"), list) and len(k["points"]) >= 2:
                keys.append((sc.T(sc.timer.resolve(k.get("at"), 0.0)), WM.resample([point(q, sc) for q in k["points"]])))
    elif isinstance(el.get("points"), list) and len(el["points"]) >= 2:
        keys.append((0.0, WM.resample([point(q, sc) for q in el["points"]])))
    keys.sort(key=lambda kv: kv[0])
    return keys


def build_front(sc, el):
    keys = front_keys(el, sc)
    if not keys:
        sc.warn("front line without points skipped")
        return
    a = anim(el, sc, "fade")
    col = C(el.get("color"), RED)
    width = max(4.0, min(num(el.get("width"), 12), 30))
    side = -1 if str(el.get("side", "right")).lower() in ("left", "-1") else 1
    allpts = [q for _, pts in keys for q in pts]
    box = WM.bbox(allpts, 60)
    t_start = sc.T(a["at"])

    def draw(p, tl):
        t = t_start + tl
        if len(keys) == 1 or t <= keys[0][0]:
            pts = keys[0][1]
        elif t >= keys[-1][0]:
            pts = keys[-1][1]
        else:
            for (ta, pa), (tb, pb) in zip(keys, keys[1:]):
                if ta <= t <= tb:
                    f = (t - ta) / max(tb - ta, 1e-3)
                    f = f * f * (3 - 2 * f)
                    pts = [(xa + (xb - xa) * f, ya + (yb - ya) * f) for (xa, ya), (xb, yb) in zip(pa, pb)]
                    break
        WM.draw_front(p, [(x - box[0], y - box[1]) for x, y in pts], col, width, side,
                      el.get("teeth", True) is not False)

    sc.dynamic(draw, box, a["enter"], a["at"], edur=0.5, exit_at=a["exit_at"], sfx=None,
               z=int(num(el.get("z"), 2)), fps=12, period=None if len(keys) > 1 else 1 / 12)


def build_counter(sc, el):
    """A number that counts up or down: a year ticking by, troops, money."""
    a = anim(el, sc, "pop")
    x, y = pos(el, sc)
    v0, v1 = num(el.get("from"), 0), num(el.get("to"), 100)
    kind = "year" if (str(el.get("format", "")).lower() == "year" or
                      (el.get("format") is None and 0 < abs(v0) < 2100 and 0 < abs(v1) < 2100 and v0 == int(v0)
                       and v1 == int(v1) and not el.get("prefix") and not el.get("suffix"))) else "number"
    size = max(30.0, min(num(el.get("size"), 90), 220))
    col = C(el.get("color"), INK)
    t0 = sc.T(a["at"])
    until = el.get("until")
    t1 = sc.T(sc.timer.resolve(until, 0.0)) if until is not None else t0 + num(el.get("dur"), 2.0)
    t1 = max(t1, t0 + 0.3)
    longest = max(len(WM.fmt_count(v, kind, el.get("prefix", ""), el.get("suffix", ""), el.get("decimals", 0)))
                  for v in (v0, v1))
    w, h = longest * size * 0.62 + 60, size * 1.5
    box = (x - w / 2, y - h / 2, w, h)

    def draw(p, tl):
        f = min(1.0, max(0.0, (t0 + tl - t0) / (t1 - t0)))
        f = 1 - (1 - f) ** 2
        v = v0 + (v1 - v0) * f
        p.text(WM.fmt_count(v, kind, el.get("prefix", ""), el.get("suffix", ""), el.get("decimals", 0)),
               w / 2, h / 2, size, col, stroke=9, scol=(25, 25, 32) if luminance(col) > 0.6 else WHITE)

    sc.dynamic(draw, box, a["enter"], a["at"], edur=0.38, idle=a["idle"], exit_at=a["exit_at"], sfx=a["sfx"],
               move=a["move"], z=int(num(el.get("z"), 3)), fps=30)
    n_ticks = int(min(12, (t1 - t0) * 6))
    for i in range(n_ticks):
        sc.sfx.append((t0 + (t1 - t0) * i / max(n_ticks, 1), "tick1"))


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
            zoom = num(sh.get("zoom"), 1.4)
            if sh.get("region") and sc.view is not None:
                fz = region_focus(sc, sh["region"])
                if fz:
                    focus, zoom = fz[0], (zoom if sh.get("zoom") is not None else fz[1])
            sc.shot(t, max(1.0, min(zoom, 2.2)), point(focus, sc) if focus else None, sh.get("move", "pan"
                    if sh.get("region") else "cut"))
        return
    z = cam.get("zoom")
    z_end = num(z[-1] if isinstance(z, (list, tuple)) and z else z, 1.0)
    if cam.get("auto_shots") is False or sc.dur < 4.5 or z_end > 1.08:
        return
    if punch_shot(sc, elements):
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
                sc.shot(t1 + 0.2, 1.0, None, "cut", base=True)
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


PUNCH = ("surprise", "angry", "smug", "laugh", "sad", "scared", "confused", "happy")
PAN_BGS = ("field", "hills", "desert", "snow", "city", "battlefield", "street", "harbor", "beach", "jungle",
           "mountains", "trench", "palace", "construction", "factory", "farm", "mine", "classroom", "lab",
           "parliament", "courtroom", "prison", "market", "camp", "sea")


def punch_shot(sc, elements):
    """A close-up that cuts in exactly on the punchline word (the latest word a single character reacts to:
    "...and Francis was FURIOUS"), holds while the face reacts, then cuts back to the scene's own camera."""
    reacts = getattr(sc, "reacts", {}) or {}
    by_time = {}
    for k, lst in reacts.items():
        for t0, expr in lst:
            by_time.setdefault(round(t0, 2), []).append((k, expr))
    best = None
    for t0, who in sorted(by_time.items()):
        if len(who) != 1 or who[0][1] not in PUNCH:
            continue                           # everybody gasping is a wide shot, not a close-up
        k, expr = who[0]
        e = elements[k] if k < len(elements) else None
        if not e or e.get("type") != "char" or e.get("lon") is not None:
            continue
        if t0 < 1.0 or sc.dur - t0 < 0.6:
            continue
        best = (t0, k, expr)                   # the last one wins: punchlines come at the end
    if best is None:
        return False
    t0, k, expr = best
    e = elements[k]
    x, y = pos(e, sc, (960, 900))
    s = max(0.15, num(e.get("scale"), 1.0))
    talking = bool(e.get("say")) or any(isinstance(o, dict) and o.get("type") == "bubble" for o in elements)
    zoom = max(1.25, min(1.9, (1.45 if talking else 1.75) / max(0.6, s)))   # leave room for a speech bubble
    # the close-up must keep the speaker's head, hat and speech bubble in view (a bubble above a tall hat used to be cut off)
    from .schema import char_box, element_bbox
    cb = char_box(e)
    rect = [cb[0], cb[1], cb[2], y - 60 * s] if cb else [x - 130 * s, y - 400 * s, x + 130 * s, y - 60 * s]
    for o in elements:
        if isinstance(o, dict) and o.get("type") == "bubble" and abs(num(o.get("x"), 960) - x) < 500:
            bb = element_bbox(o)
            if bb and bb[3] < y - 150 * s:
                rect = [min(rect[0], bb[0]), min(rect[1], bb[1]), max(rect[2], bb[2]), rect[3]]
    need_h, need_w = rect[3] - rect[1] + 50, rect[2] - rect[0] + 50
    fit = min(H / max(need_h, 1.0), W / max(need_w, 1.0))
    zoom = min(zoom, fit)
    if zoom < 1.12:
        return False                           # the picture is too tall to close in on without cutting something off
    focus = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
    if sc.mood == "somber":
        sc.shot(t0 - 0.3, min(zoom, 1.3), focus, "pan")      # a slow push, never a snap
    else:
        sc.shot(t0 - 0.04, zoom, focus, "cut")
    back = min(sc.dur - 0.5, t0 + 1.7)
    if sc.dur - back > 0.6:
        sc.shot(back, 1.0, None, "cut", base=True)
    return True


def slow_pan(sc, scene):
    """Wide painted places get a slow sideways pan instead of a plain push-in, when every character and label
    still fits in the frame from start to end."""
    bg = scene.get("bg") or {}
    cam = scene.get("camera") or {}
    if bg.get("type") not in PAN_BGS or cam.get("center") or cam.get("to") or cam.get("pan") is False:
        return False
    z = cam.get("zoom")
    if z is not None:
        zz = z if isinstance(z, (list, tuple)) else [1.0, z]
        if num(zz[0], 1.0) > 1.01 or num(zz[-1], 1.0) > 1.06:
            return False                       # the storyboard asked for its own zoom
    if sc.idx % 5 in (1, 4) or sc.dur < 3.5:
        return False                           # keep some plain push-ins for variety
    xs = []
    for e in scene.get("elements") or []:
        if e.get("type") in ("char", "crowd", "text", "bubble", "note", "sign", "board", "prop", "counter"):
            x, _ = pos(e, sc, (960, 900))
            half = 150 * num(e.get("scale"), 1.0) if e.get("type") == "char" else \
                num(e.get("width"), 300) / 2 if e.get("type") == "crowd" else 170
            xs += [x - half, x + half]
    zoom = 1.12
    # everything must also stay inside the frame vertically (a speech bubble above a tall hat used to get cut off)
    from .schema import element_bbox
    top = min([bb[1] for bb in (element_bbox(e) for e in scene.get("elements") or [] if isinstance(e, dict)) if bb] or [H])
    view_top = H / 2 + 20 - H / (2 * (zoom + 0.025))
    if top < view_top + 12:
        return False
    hw = W / (2 * zoom)
    lo, hi = hw, W - hw
    if xs:
        lo, hi = max(lo, max(xs) - hw + 20), min(hi, min(xs) + hw - 20)
    if hi - lo < 50:
        return False
    a, b = (lo, hi) if sc.idx % 2 == 0 else (hi, lo)
    sc.camera(zoom, zoom + 0.025, (a, H / 2 + 20), (b, H / 2 + 20))
    return True


def region_focus(sc, spec):
    """([x, y] screen point, zoom) that frames a country or region on the current map."""
    g = region_geom(spec)
    if g is None:
        return None
    gg = sc.view.in_view(g)
    if gg is None:
        return None
    x0, y0, x1, y1 = gg.bounds
    (sx0, sy1), (sx1, sy0) = sc.view.xy(x0, y0), sc.view.xy(x1, y1)
    w, h = max(40.0, abs(sx1 - sx0)), max(40.0, abs(sy1 - sy0))
    return [(sx0 + sx1) / 2, (sy0 + sy1) / 2], max(1.0, min(W / (w * 1.5), H / (h * 1.5), 2.2))


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


# ------------------------------------------------------------------ weather and light (see weather.py)
NIGHT_SKY = ("field", "hills", "desert", "snow", "city", "battlefield", "street", "harbor", "beach", "jungle",
             "mountains", "trench", "construction", "factory", "farm", "market", "camp")
HORIZON = {"field": 640, "hills": 700, "desert": 700, "snow": 700, "city": 820, "battlefield": 620, "sea": 520,
           "construction": 730, "factory": 520, "farm": 600, "market": 520, "camp": 600}


def _when(sc, v, default):
    return sc.T(sc.timer.resolve(v, default)) if v is not None else None


def build_weather(sc, scene):
    bg = scene.get("bg") or {}
    w = scene.get("weather")
    if isinstance(w, str):
        w = {"type": w}
    if isinstance(w, dict):
        kind = WX.norm_weather(w.get("type"))
        if kind:
            wx = WX.Weather(kind, sc.seed, num(w.get("amount"), 1.0), w.get("wind"),
                            _when(sc, w.get("at"), 0.0) or 0.0, _when(sc, w.get("until"), 1.0), sc.dur)
            sc.overlay(wx.apply, WX.WEATHER_Z)
            sc.sfx.extend(wx.sounds())
    if (bg.get("time") == "night" and bg.get("type") in NIGHT_SKY and bg.get("style") != "inside") or \
            bg.get("type") in ("night", "space"):
        tw = WX.Twinkle(sc.seed, HORIZON.get(bg.get("type"), 600), sc.dur, sc.bg)
        sc.overlay(tw.apply, z=-0.5)
    light = scene.get("light")
    if isinstance(light, str):
        light = {"to": light}
    if isinstance(light, dict):
        to = WX.norm_light(light.get("to"))
        if to:
            t0 = _when(sc, light.get("at"), 0.15) if light.get("at") is not None else sc.T(0.15)
            t1 = t0 + max(0.5, num(light.get("dur"), 3.0))
            sc.overlay(WX.Light(to, t0, t1).apply, WX.WEATHER_Z + 0.1)


def build_scene(scene, idx, dur, mood, text, timer=None):
    """scene: validated scene dict. Returns a Scene ready for render_at()."""
    sc = Scene(idx, dur, mood, text, timer=timer)
    build_background(sc, scene.get("bg"))
    elements = scene.get("elements") or []
    talk = talk_windows(sc, elements)
    try:
        sc.reacts = RX.plan(scene, sc.timer, mood)       # faces that react to the narration's words
    except Exception as e:
        sc.reacts = {}
        sc.warn(f"reactions failed: {e}")
    for k, el in enumerate(elements):
        try:
            build_element(sc, el, mood, k, talk.get(k, ()))
        except Exception as e:  # one bad element should never kill the whole scene
            sc.warn(f"element {el.get('type')} failed: {e}")
    try:
        sword_clashes(sc)
    except Exception as e:
        sc.warn(f"sword clashes failed: {e}")
    try:
        build_weather(sc, scene)
    except Exception as e:
        sc.warn(f"weather failed: {e}")
    cam = scene.get("camera") or {}
    z = cam.get("zoom") or [1.0, 1.035]
    if not isinstance(z, (list, tuple)):
        z = [1.0, num(z, 1.035)]
    c0 = cam.get("center") or cam.get("from")
    c1 = cam.get("to")
    sc.camera(max(1.0, num(z[0], 1.0)), max(1.0, num(z[-1], 1.035)),
              point(c0, sc) if c0 else None, point(c1, sc) if c1 else None)
    if not cam.get("shots"):
        try:
            slow_pan(sc, scene)
        except Exception as e:
            sc.warn(f"slow pan failed: {e}")
    try:
        build_shots(sc, cam, elements, talk)
    except Exception as e:
        sc.warn(f"camera shots failed: {e}")
    return sc
