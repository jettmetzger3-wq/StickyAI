"""JSON Schema for scenes, plus validation and automatic repair.

Pipeline for every LLM-made scene:  parse -> repair_scene() (fix names, clamp positions, keep text out of
the caption zone, somber rules) -> validate_scene() against SCENE_SCHEMA -> compile.
"""
import copy
import difflib
import math

import jsonschema

from .doodle import W, H
from .fonts import font
from .pen import ARMS, LEGS, MOUTHS, EYES, EXTRAS, HELD, HATS, KIND_ALIASES
from .puppet import resolve_action
from .registry import PROPS, PROP_ALIASES, resolve_prop, guess_prop, prop_bounds, prop_anchor
from .custom_props import clean_parts, kit_lookup, to_element_params, slug
from .geo import REGIONS, View, unknown_names
from .captions import CAPTION_ZONE

BG_TYPES = ("paper", "sunburst", "ground", "field", "hills", "desert", "snow", "city", "interior", "battlefield",
            "sea", "night", "dark", "map", "street", "palace", "harbor", "beach", "underwater", "space", "jungle",
            "mountains", "trench")
BG_ALIASES = {"ocean": "sea", "port": "harbor", "docks": "harbor", "harbour": "harbor", "coast": "beach",
              "island": "beach", "shore": "beach", "seabed": "underwater", "under_water": "underwater",
              "deep_sea": "underwater", "town": "street", "village": "street", "market": "street", "road": "street",
              "throne_room": "palace", "court": "palace", "ballroom": "palace", "castle_hall": "palace",
              "room": "interior", "office": "interior", "house": "interior", "stars": "space", "orbit": "space",
              "forest": "jungle", "rainforest": "jungle", "alps": "mountains", "mountain": "mountains",
              "trenches": "trench", "war": "battlefield", "skyline": "city", "plain": "field", "meadow": "field",
              "farm": "field", "countryside": "hills", "sand": "desert", "arctic": "snow", "winter": "snow"}
TIMES = ("day", "dawn", "dusk", "night", "storm")
ENTERS = ("pop", "drop", "grow", "fade", "slide_left", "slide_right", "slide_up", "slide_down",
          "wipe_right", "wipe_left", "wipe_up", "wipe_down", "none")
IDLES = ("bob", "float", "pulse", "shake", "drift", "none")
SFX = ("auto", "none", "pop", "whoosh", "swish", "boom", "tick")
EL_TYPES = ("char", "crowd", "text", "prop", "bubble", "note", "sign", "board", "icons", "shape", "group",
            "territory", "city", "arrow", "pointer")
MOVES = ("cut", "pan", "whip")
POINTER_DIRS = ("n", "s", "e", "w", "ne", "nw", "se", "sw")
MOODS = ("fun", "tense", "somber")

_num = {"type": "number"}
_at = {"anyOf": [{"type": "number"}, {"type": "string"}, {"type": "object"}]}
_pt = {"anyOf": [{"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                 {"type": "object", "properties": {"lon": _num, "lat": _num, "x": _num, "y": _num}}]}
_anim = {
    "enter": {"enum": list(ENTERS)},
    "at": _at,
    "delay": _num,
    "edur": _num,
    "idle": {"enum": list(IDLES)},
    "exit": _at,
    "move": {"type": "object", "properties": {"dx": _num, "dy": _num, "from": _at, "to": _at}},
    "z": _num,
    "sfx": {"enum": list(SFX)},
}
_xy = {"x": _num, "y": _num, "lon": _num, "lat": _num}


def _obj(required=(), **props):
    return {"type": "object", "required": list(required), "properties": props}


ELEMENT_SCHEMAS = {
    "char": _obj(("type",), type={"const": "char"}, **_xy, **_anim, scale=_num, kind={"type": "string"},
                 hat_color={"type": "string"},
                 pose={"anyOf": [{"enum": list(ARMS)}, {"type": "array"}]},
                 arms={"type": "array"}, legs={"anyOf": [{"enum": list(LEGS)}, {"type": "array"}]},
                 mouth={"enum": list(MOUTHS)}, eyes={"enum": list(EYES)},
                 extras={"type": "array", "items": {"enum": list(EXTRAS) + ["?"]}},
                 prop={"enum": list(HELD)}, prop_color={"type": "string"}, flip={"type": "boolean"},
                 look={"type": "number"}, do={"type": "array", "maxItems": 12}, talk={"type": "array"},
                 auto={"type": "boolean"}, life={"type": "boolean"}),
    "crowd": _obj(("type",), type={"const": "crowd"}, **_xy, **_anim, kind={"type": "string"}, count=_num, rows=_num,
                  width=_num, scale=_num, flip={"type": "boolean"}, do={"type": "array", "maxItems": 12},
                  mouth={"enum": list(MOUTHS)}, eyes={"enum": list(EYES)}, prop={"enum": list(HELD)},
                  pose={"anyOf": [{"enum": list(ARMS)}, {"type": "array"}]}, hat_color={"type": "string"}),
    "pointer": _obj(("type",), type={"const": "pointer"}, **_xy, **_anim, **{"from": {"enum": list(POINTER_DIRS)}},
                    size=_num, color={"type": "string"}),
    "text": _obj(("type", "text"), type={"const": "text"}, **_xy, **_anim, text={"type": "string"}, size=_num,
                 color={"type": "string"}, font={"enum": ["bold", "hand"]}, stroke=_num,
                 align={"enum": ["center", "left", "right"]}),
    "prop": _obj(("type", "name"), type={"const": "prop"}, **_xy, **_anim, name={"enum": sorted(PROPS)}, scale=_num,
                 color={"type": "string"}, params={"type": "object"}),
    "bubble": _obj(("type", "text"), type={"const": "bubble"}, **_xy, **_anim, text={"type": "string"}, size=_num,
                   w=_num, h=_num, font={"enum": ["bold", "hand"]}, placed={"type": "boolean"},
                   tail={"anyOf": [{"enum": ["left", "right", "down", "none"]}, {"type": "array"}]}),
    "note": _obj(("type", "text"), type={"const": "note"}, **_xy, **_anim, text={"type": "string"}, size=_num, w=_num, h=_num),
    "sign": _obj(("type", "text"), type={"const": "sign"}, **_xy, **_anim, text={"type": "string"}, size=_num, w=_num, h=_num),
    "board": _obj(("type",), type={"const": "board"}, **_xy, **_anim, title={"type": "string"},
                  lines={"type": "array", "items": {"type": "string"}}, size=_num, w=_num, h=_num),
    "icons": _obj(("type", "icon", "count"), type={"const": "icons"}, **_xy, **_anim, icon={"enum": sorted(PROPS)},
                  count=_num, per_row=_num, scale=_num, gap=_num, color={"type": "string"}),
    "shape": _obj(("type", "shape"), type={"const": "shape"}, **_xy, **_anim,
                  shape={"enum": ["rect", "circle", "ellipse", "line", "poly"]}, w=_num, h=_num, r=_num,
                  points={"type": "array", "items": _pt}, fill={"type": "string"}, stroke={"type": "string"},
                  width=_num, radius=_num),
    "group": _obj(("type", "items"), type={"const": "group"}, **_anim, items={"type": "array"}),
    "territory": _obj(("type",), type={"const": "territory"}, **_anim, region={"type": "string"},
                      countries={"type": "array", "items": {"type": "string"}},
                      clip={"type": "array", "items": {"type": "array"}}, box={"type": "array"},
                      color={"type": "string"}),
    "city": _obj(("type", "name", "lon", "lat"), type={"const": "city"}, **_anim, name={"type": "string"},
                 lon=_num, lat=_num, size=_num, color={"type": "string"}, dot={"type": "boolean"}),
    "arrow": _obj(("type",), type={"const": "arrow"}, **_anim, **{"from": _pt}, to=_pt,
                  points={"type": "array", "items": _pt}, curve=_num, color={"type": "string"}, width=_num,
                  head={"type": "boolean"}),
}

SCENE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Stickman Studio scene",
    "type": "object",
    "required": ["bg", "elements"],
    "properties": {
        "bg": {
            "type": "object", "required": ["type"],
            "properties": {
                "type": {"enum": list(BG_TYPES)}, "time": {"enum": list(TIMES)},
                "style": {"enum": ["paper", "dark", "europe", "medieval", "asia", "arab", "western"]},
                "skyline": {"type": "string"}, "wall": {"type": "string"}, "floor": {"type": "string"},
                "color": {"type": "string"}, "ray": {"type": "string"}, "sky": {"type": "string"},
                "ground": {"type": "string"}, "sea": {"type": "string"}, "land": {"type": "string"},
                "y": _num, "horizon": _num, "clouds": {"type": "boolean"},
                "center": {"type": "array", "items": _num, "minItems": 2, "maxItems": 2},
                "width": _num,
                "territories": {"type": "array", "items": {"type": "object"}},
                "labels": {"type": "array", "items": {"type": "object", "required": ["text", "lon", "lat"]}},
                "items": {"type": "array"},
            },
        },
        "elements": {"type": "array", "maxItems": 30,
                     "items": {"type": "object", "required": ["type"],
                               "properties": {"type": {"enum": list(EL_TYPES)}}}},
        "camera": {"type": "object", "properties": {"zoom": {"anyOf": [_num, {"type": "array"}]},
                                                    "center": _pt, "to": _pt, "auto_shots": {"type": "boolean"},
                                                    "shots": {"type": "array", "maxItems": 6, "items": {
                                                        "type": "object", "properties": {
                                                            "at": _at, "zoom": _num, "focus": _pt,
                                                            "move": {"enum": list(MOVES)}}}}}},
        "note": {"type": "string"},
    },
}

_validator = jsonschema.Draft7Validator(SCENE_SCHEMA)
_el_validators = {k: jsonschema.Draft7Validator(v) for k, v in ELEMENT_SCHEMAS.items()}


def validate_scene(scene):
    """Return a list of human readable schema errors (empty = valid)."""
    if not isinstance(scene, dict):
        return ["scene is not a JSON object"]
    errs = [f"{'/'.join(str(p) for p in e.path) or 'scene'}: {e.message}" for e in _validator.iter_errors(scene)]
    for i, el in enumerate(scene.get("elements") or []):
        v = _el_validators.get(el.get("type")) if isinstance(el, dict) else None
        if v:
            for e in v.iter_errors(el):
                errs.append(f"elements/{i}/{'/'.join(str(p) for p in e.path)}: {e.message}")
    return errs


# ------------------------------------------------------------------ repair helpers
TYPE_ALIASES = {"label": "text", "title": "text", "caption": "text", "character": "char", "stickman": "char",
                "person": "char", "speech": "bubble", "speech_bubble": "bubble", "thought": "bubble",
                "sticky_note": "note", "postit": "note", "list": "board", "whiteboard": "board", "plan": "board",
                "object": "prop", "item": "prop", "image": "prop", "icon_grid": "icons", "count": "icons",
                "region": "territory", "country": "territory", "marker": "city", "town": "city", "rect": "shape",
                "line": "shape", "circle": "shape", "army": "crowd", "soldiers": "crowd", "people": "crowd",
                "troops": "crowd", "mob": "crowd", "audience": "crowd", "pointer_arrow": "pointer",
                "indicator": "pointer", "big_arrow": "pointer"}
SOMBER_NO = ("cheer", "celebrate", "dance", "laugh", "hop", "jump")
ENTER_ALIASES = {"slide_l": "slide_left", "slide_r": "slide_right", "slide_u": "slide_up", "slide_d": "slide_down",
                 "wipe_r": "wipe_right", "wipe_l": "wipe_left", "wipe_u": "wipe_up", "wipe_d": "wipe_down",
                 "appear": "pop", "zoom": "grow", "fade_in": "fade", "slide": "slide_left", "wipe": "wipe_right",
                 "bounce": "drop", "fall": "drop", "scale": "grow"}
POSE_ALIASES = {"arms_down": "down", "idle": "down", "neutral": "down", "stand": "down", "arms_up": "up",
                "celebrate": "cheer", "happy": "cheer", "hands_on_hips": "hips", "crossed": "cross",
                "arms_crossed": "cross", "point": "point_right", "pointing": "point_right", "waving": "wave",
                "thinking": "think", "holding": "hold", "salute": "raise_right", "angry": "angry_fists",
                "panic": "up", "surrender": "up", "confused": "shrug"}


def nearest(value, choices, default):
    if value in choices:
        return value
    if value is None:
        return default
    s = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if s in choices:
        return s
    m = difflib.get_close_matches(s, list(choices), n=1, cutoff=0.6)
    return m[0] if m else default


def _f(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def text_bbox(text, x, y, size, f="bold", align="center"):
    lines = str(text).replace("\\n", "\n").split("\n")
    fnt = font("hand" if f == "hand" else "bold", size)
    widths = [fnt.getlength(l) for l in lines] or [0]
    w = max(widths) + 18
    h = len(lines) * size * 1.12 + 10
    if align == "left":
        return (x - 9, y - h / 2, x + w, y + h / 2)
    if align == "right":
        return (x - w, y - h / 2, x + 9, y + h / 2)
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def element_bbox(el):
    """Rough on-screen bounding box (x0, y0, x1, y1) of a screen-positioned element, or None."""
    t = el.get("type")
    if el.get("lon") is not None and el.get("lat") is not None:
        return None
    x, y = _f(el.get("x"), 960), _f(el.get("y"), 540)
    if t == "char":
        s = _f(el.get("scale"), 1.0)
        return (x - 130 * s, y - 375 * s, x + 130 * s, y + 15 * s)
    if t == "text":
        return text_bbox(el.get("text", ""), x, y, _f(el.get("size"), 64), el.get("font", "bold"), el.get("align", "center"))
    if t in ("bubble", "note", "board", "sign"):
        from .compiler import bubble_size
        if t == "board":
            lines = el.get("lines") or []
            size = _f(el.get("size"), 50)
            longest = max([len(str(l)) for l in lines] + [len(str(el.get("title") or "")) * 1.2, 6])
            w = _f(el.get("w"), max(420, min(1100, longest * size * 0.5 + 120)))
            h = _f(el.get("h"), (size * 1.7 if el.get("title") else 0) + len(lines) * size * 1.45 + 60)
            return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        w, h, _ = bubble_size(el)
        if t == "sign":
            return (x - w / 2, y - 170 - h, x + w / 2, y)
        extra = 80 if t == "bubble" and el.get("tail") != "none" else 0
        return (x - w / 2, y - h / 2, x + w / 2, y + h / 2 + extra)
    if t == "prop":
        name = resolve_prop(el.get("name"))
        if not name:
            return None
        s = _f(el.get("scale"), 1.0)
        x0, y0, x1, y1 = prop_bounds(name, el.get("params"))
        anchor = prop_anchor(name, el.get("params"))
        w, h = (x1 - x0) * s, (y1 - y0) * s
        if name in ("railway",):
            return None
        if anchor == "bottom":
            return (x - w / 2, y - h, x + w / 2, y)
        return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    return None



def camera_safe_rect(cam, margin=8):
    """The part of the 1920x1080 frame that stays visible for the whole scene, given the camera move."""
    cam = cam if isinstance(cam, dict) else {}
    z = cam.get("zoom") if cam.get("zoom") is not None else [1.0, 1.035]
    if not isinstance(z, (list, tuple)):
        z = [1.0, _f(z, 1.035)]
    z0, z1 = max(1.0, min(_f(z[0], 1.0), 1.15)), max(1.0, min(_f(z[-1], 1.035), 1.15))

    def ctr(v):
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            return _f(v[0], W / 2), _f(v[1], H / 2)
        return W / 2, H / 2
    c0 = ctr(cam.get("center") or cam.get("from"))
    c1 = ctr(cam.get("to")) if cam.get("to") else c0
    rects = []
    for zz, (cx, cy) in ((z0, c0), (z1, c1)):
        hw, hh = W / (2 * zz), H / (2 * zz)
        cx = min(max(cx, hw), W - hw)
        cy = min(max(cy, hh), H - hh)
        rects.append((cx - hw, cy - hh, cx + hw, cy + hh))
    x0 = max(r[0] for r in rects) + margin
    y0 = max(r[1] for r in rects) + margin
    x1 = min(r[2] for r in rects) - margin
    y1 = min(r[3] for r in rects) - margin
    return x0, y0, x1, y1

def _shift_into_frame(el, bb, margin=8, bottom_limit=H, safe=None):
    """Move el (x/y) so bb is inside the visible frame. Returns True if moved."""
    x0, y0, x1, y1 = bb
    sx0, sy0, sx1, sy1 = safe or (margin, margin, W - margin, H)
    sy1 = min(sy1, bottom_limit)
    dx = dy = 0.0
    if x1 - x0 < sx1 - sx0:
        if x0 < sx0:
            dx = sx0 - x0
        elif x1 > sx1:
            dx = sx1 - x1
    if y1 - y0 < sy1 - sy0:
        if y0 < sy0:
            dy = sy0 - y0
        elif y1 > sy1:
            dy = sy1 - y1
    if abs(dx) > 0.5 or abs(dy) > 0.5:
        el["x"] = round(_f(el.get("x"), 960) + dx)
        el["y"] = round(_f(el.get("y"), 540) + dy)
        return True
    return False


def _shrink_text(el, max_w):
    """Make a text element fit in max_w pixels by lowering its size."""
    size = _f(el.get("size"), 64)
    for _ in range(12):
        bb = text_bbox(el.get("text", ""), 0, 0, size, el.get("font", "bold"))
        if bb[2] - bb[0] <= max_w or size <= 22:
            break
        size = int(size * 0.9)
    el["size"] = size


def overlaps(a, b, pad=4):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


TALL_HATS = ("bearskin", "shako", "tophat", "tophat_gray", "mitre", "wizard", "chef", "pharaoh", "crown", "bicorne",
             "turban")


def wrap_line(text, n=18, max_lines=3):
    words = str(text).replace("\n", " ").split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,!?;:") + "..."
    return "\n".join(lines)


def say_lines(says):
    if isinstance(says, (str, dict)):
        says = [says]
    out = []
    for s in says if isinstance(says, list) else []:
        if isinstance(s, str):
            s = {"text": s}
        if not isinstance(s, dict):
            continue
        txt = str(s.get("text") or s.get("line") or "").strip()
        if txt:
            out.append({"text": txt[:90], "at": s.get("at")})
    return out[:3]


def _at_num(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def say_bubbles(el, says, safe, mood="fun", others=()):
    """Speech bubbles for a character's (or crowd's) "say" lines: above the head, tail pointing at the speaker,
    shown one after another."""
    from .compiler import bubble_size
    lines = say_lines(says)
    if not lines or el.get("lon") is not None:
        return []
    crowd = el.get("type") == "crowd"
    s = _f(el.get("scale"), 0.6 if crowd else 1.0)
    cx, fy = _f(el.get("x"), 960), _f(el.get("y"), 900)
    if crowd:
        head_top = fy - 400 * s - 70 * (int(_f(el.get("rows"), 2)) - 1)
    else:
        kind = str(el.get("kind") or "")
        head_top = fy - (375 + (75 if kind in TALL_HATS else 30)) * s
    first = -1 if el.get("flip") else 1
    base = _at_num(el.get("at"), 0.0) if not isinstance(el.get("at"), str) else 0.0
    n = len(lines)
    times = []
    for k, ln in enumerate(lines):
        if ln["at"] is not None:
            times.append(ln["at"])
        elif k == 0 and isinstance(el.get("at"), str):
            times.append(el["at"])
        else:
            times.append(round(min(0.9, base + 0.08 + k * (0.86 - base) / n), 2))
    texty = [element_bbox(o) for o in others if o.get("type") in ("text", "note", "board", "bubble", "sign")
             and o.get("exit") is None and element_bbox(o)]
    solid = [element_bbox(o) for o in others if o.get("type") in ("prop", "icons") and element_bbox(o)]

    def area(a, b):
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))

    made = []
    for k, ln in enumerate(lines):
        b = {"type": "bubble", "text": wrap_line(ln["text"]), "size": 44 if len(ln["text"]) <= 36 else 40}
        w, h, _ = bubble_size(b)
        cands = []
        for side in (first, -first):
            tip_x, tip_y = cx + side * 34 * s, head_top - 4
            for shift, lift in ((0, 0), (0.55, 0), (0, 1), (1.0, 0.5)):
                bx = tip_x + side * (w / 2 - 46 + shift * w)
                by = tip_y - 72 - h / 2
                if by - h / 2 < safe[1] + 4:
                    by = safe[1] + 4 + h / 2
                    bx = cx + side * (70 * s + w / 2 + 10 + shift * w * 0.5)
                bx = max(safe[0] + w / 2 + 4, min(bx, safe[2] - w / 2 - 4))
                if lift:
                    bb = (bx - w / 2, by - h / 2, bx + w / 2, by + h / 2)
                    hits = [o for o in texty if overlaps(bb, o)]
                    if hits:
                        up = min(o[1] for o in hits) - 14 - h / 2
                        if up - h / 2 >= safe[1] + 4 and by - up <= 170:
                            by = up
                bb = (bx - w / 2, by - h / 2, bx + w / 2, by + h / 2)
                score = sum(area(bb, o) for o in texty) * 10 + sum(area(bb, o) for o in solid) + \
                    abs(bx - tip_x) * 2 + (tip_y - by) * 3
                cands.append((score, bx, by, tip_x, tip_y))
        _, bx, by, tip_x, tip_y = min(cands)
        ty = tip_y - (by + h / 2)
        b.update(x=round(bx), y=round(by), tail=[round(tip_x - bx), round(ty)] if ty >= 24 else "none",
                 at=times[k], enter="fade" if mood == "somber" else "pop", z=6, placed=True)
        if k < n - 1:
            b["exit"] = times[k + 1]
        made.append(b)
    # later speakers keep clear of these (this speaker's own lines replace each other, so they may share a spot)
    others_out = [element_bbox(m) for m in made]
    texty.extend(o for o in others_out if o)
    return made


def repair_scene(scene, mood="fun", text="", kit=None):
    """Fix common LLM mistakes. Returns (scene, list_of_fixes).
    kit: the props designed for this video (see custom_props); scenes may use them by name."""
    fixes = []
    custom = kit_lookup(kit)
    if not isinstance(scene, dict):
        return {"bg": {"type": "paper"}, "elements": []}, ["scene was not an object; replaced with an empty one"]
    sc = copy.deepcopy(scene)
    # background
    bg = sc.get("bg") if isinstance(sc.get("bg"), dict) else {"type": sc.get("bg") if isinstance(sc.get("bg"), str) else "paper"}
    bt = str(bg.get("type") or "").strip().lower().replace(" ", "_")
    bt = BG_ALIASES.get(bt, bt)
    bt = nearest(bt, BG_TYPES, "paper")
    if bt != bg.get("type"):
        fixes.append(f"bg type {bg.get('type')!r} -> {bt!r}")
    bg["type"] = bt
    if bg.get("time") is not None and bg["time"] not in TIMES:
        bg["time"] = nearest(bg["time"], TIMES, "day")
    if bt == "street":
        from .places import STREET_STYLES
        st = str(bg.get("style") or "europe").strip().lower().replace(" ", "_").replace("-", "_")
        st = {"european": "europe", "medieval_europe": "medieval", "old": "medieval", "asian": "asia",
              "chinese": "asia", "japanese": "asia", "middle_east": "arab", "arabic": "arab", "desert": "arab",
              "wild_west": "western", "cowboy": "western", "american_west": "western"}.get(st, st)
        bg["style"] = st if st in STREET_STYLES else "europe"
    elif bg.get("style") is not None and bg["style"] not in ("paper", "dark"):
        bg["style"] = "dark" if "dark" in str(bg["style"]).lower() else "paper"
    if bt == "city" and bg.get("skyline") is not None:
        from .places import skyline_key
        key = skyline_key(bg.get("skyline"))
        if key:
            bg["skyline"] = key
        else:
            fixes.append(f"unknown skyline {bg.get('skyline')!r}, used a plain city")
            bg.pop("skyline")
    if mood == "somber" and bt in ("sunburst",):
        bg["type"] = "dark"
        fixes.append("somber scene: sunburst background -> dark")
    if bt == "map":
        c = bg.get("center")
        if not (isinstance(c, (list, tuple)) and len(c) == 2):
            bg["center"] = [0, 30]
            fixes.append("map center missing; set to [0, 30]")
        bg["center"] = [_f(bg["center"][0], 0), max(-75, min(80, _f(bg["center"][1], 30)))]
        bg["width"] = max(3, min(_f(bg.get("width"), 40), 340))
        for tr in bg.get("territories") or []:
            bad = unknown_names(tr.get("countries") if isinstance(tr, dict) else None)
            if bad:
                fixes.append(f"unknown countries {bad}")
        bg["labels"] = [l for l in (bg.get("labels") or []) if isinstance(l, dict) and "lon" in l and "lat" in l]
    sc["bg"] = bg
    is_map = bg["type"] == "map"
    view = View(bg["center"][0], bg["center"][1], bg["width"]) if is_map else None
    if isinstance(sc.get("camera"), dict) and sc["camera"].get("zoom") is not None:
        z = sc["camera"]["zoom"]
        z = z if isinstance(z, (list, tuple)) else [1.0, z]
        sc["camera"]["zoom"] = [max(1.0, min(_f(v, 1.0), 1.15)) for v in z][:2]
    safe = camera_safe_rect(sc.get("camera"))
    cam = sc.get("camera")
    if isinstance(cam, dict) and cam.get("shots") is not None:
        shots = []
        for sh in (cam["shots"] if isinstance(cam["shots"], list) else [])[:6]:
            if not isinstance(sh, dict):
                continue
            sh = dict(sh)
            if "focus" not in sh:
                for k in ("center", "on", "target"):
                    if k in sh:
                        sh["focus"] = sh.pop(k)
                        break
            sh["zoom"] = max(1.0, min(_f(sh.get("zoom"), 1.4), 2.2))
            sh["move"] = nearest(sh.get("move", "cut"), MOVES, "cut")
            if isinstance(sh.get("at"), str) and not sh["at"].lower().startswith("word:"):
                try:
                    sh["at"] = float(sh["at"])
                except ValueError:
                    sh["at"] = "word:" + sh["at"]
            shots.append(sh)
        cam["shots"] = shots

    els = sc.get("elements")
    if not isinstance(els, list):
        els = []
    out = []
    pending_says = []
    for el in els:
        if not isinstance(el, dict):
            continue
        t = el.get("type")
        t2 = TYPE_ALIASES.get(t, t)
        if t2 not in EL_TYPES:
            t2 = nearest(t2, EL_TYPES, None)
        if t2 is None:
            fixes.append(f"dropped element of unknown type {t!r}")
            continue
        if t2 != t:
            fixes.append(f"element type {t!r} -> {t2!r}")
            el["type"] = t2
        t = t2
        says = el.pop("say", None) if t in ("char", "crowd") else None
        if says:
            pending_says.append((el, says))
        if t in ("territory", "city") and not is_map:
            fixes.append(f"dropped {t} in a non-map scene")
            continue
        if t == "shape" and el.get("shape") is None:
            el["shape"] = {"line": "line", "circle": "circle"}.get(str(el.get("kind")), "rect")
        # animation fields
        if "enter" in el:
            e = ENTER_ALIASES.get(el["enter"], el["enter"])
            el["enter"] = nearest(e, ENTERS, "pop")
        if "idle" in el:
            el["idle"] = nearest(el["idle"], IDLES, "none")
        if "sfx" in el:
            el["sfx"] = nearest(el["sfx"], SFX, "auto")
        if mood == "somber":
            if el.get("enter") in ("pop", "drop", "grow") or ("enter" not in el and t not in ("territory", "arrow")):
                el["enter"] = "fade"
            if el.get("idle") in ("shake", "pulse"):
                el["idle"] = "none"
            if el.get("sfx") == "pop":
                el["sfx"] = "none"
        if isinstance(el.get("at"), str) and not el["at"].lower().startswith("word:"):
            try:
                el["at"] = float(el["at"])
            except ValueError:
                el["at"] = "word:" + el["at"]
        if t in ("char", "crowd") and el.get("do") is not None:
            acts = []
            for a in (el["do"] if isinstance(el["do"], list) else [el["do"]])[:12]:
                a = {"act": a} if isinstance(a, str) else (dict(a) if isinstance(a, dict) else None)
                if a is None:
                    continue
                name = resolve_action(a.get("act") or a.get("action"))
                if name is None:
                    fixes.append(f"dropped unknown action {a.get('act')!r}")
                    continue
                if mood == "somber" and name in SOMBER_NO:
                    fixes.append(f"somber scene: dropped action {name!r}")
                    continue
                a["act"] = name
                a.pop("action", None)
                if isinstance(a.get("at"), str) and not a["at"].lower().startswith("word:"):
                    try:
                        a["at"] = float(a["at"])
                    except ValueError:
                        a["at"] = "word:" + a["at"]
                if a.get("dur") is not None:
                    a["dur"] = max(0.1, min(_f(a["dur"], 1.5), 20))
                acts.append(a)
            el["do"] = acts
        if t == "crowd":
            k = str(el.get("kind") or "civ").lower().replace(" ", "_")
            el["kind"] = k if (k in HATS or k in KIND_ALIASES) else nearest(k, HATS, "civ")
            el["count"] = int(max(2, min(_f(el.get("count"), 10), 40)))
            el["rows"] = int(max(1, min(_f(el.get("rows"), 2), 4)))
            el["scale"] = max(0.25, min(_f(el.get("scale"), 0.6), 1.4))
            el["width"] = max(200, min(_f(el.get("width"), 900), W - 80))
            if el.get("lon") is None:
                x = _f(el.get("x"), 960)
                half = el["width"] / 2 + 130 * el["scale"]
                el["x"] = max(half, min(x, W - half)) if half * 2 < W else W / 2
                el["y"] = max(440 * el["scale"] + 80 * el["rows"], min(_f(el.get("y"), 920), H - 15))
            if isinstance(el.get("pose"), str):
                el["pose"] = nearest(POSE_ALIASES.get(el["pose"], el["pose"]), ARMS, "down")
        if t == "pointer":
            if el.get("from") not in POINTER_DIRS:
                el["from"] = nearest(str(el.get("from", "ne")).lower(), POINTER_DIRS, "ne")
            el["size"] = max(0.4, min(_f(el.get("size"), 1.0), 2.5))
        if t == "char":
            el["kind"] = el.get("kind") or "civ"
            k = str(el["kind"]).lower().replace(" ", "_")
            if k not in HATS and k not in KIND_ALIASES:
                el["kind"] = nearest(k, HATS, "civ")
                fixes.append(f"char kind {k!r} -> {el['kind']!r}")
            pose = el.get("pose")
            if isinstance(pose, str):
                pose = POSE_ALIASES.get(pose, pose)
                el["pose"] = nearest(pose, ARMS, "down")
            legs = el.get("legs")
            if isinstance(legs, str):
                el["legs"] = nearest(legs, LEGS, "stand")
            if "mouth" in el:
                el["mouth"] = nearest(el["mouth"], MOUTHS, "smile")
            if "eyes" in el:
                el["eyes"] = nearest(el["eyes"], EYES, "dot")
            if el.get("extras"):
                ex = el["extras"] if isinstance(el["extras"], list) else [el["extras"]]
                el["extras"] = [e for e in (("q" if e == "?" else nearest(e, EXTRAS, None)) for e in ex) if e]
            if el.get("prop"):
                el["prop"] = nearest(el["prop"], HELD, None)
                if el["prop"] is None:
                    del el["prop"]
            el["scale"] = max(0.2, min(_f(el.get("scale"), 1.0), 2.2))
            if mood == "somber":
                if el.get("mouth") in ("grin", "scream"):
                    el["mouth"] = "flat"
                if el.get("eyes") == "dead":
                    el["eyes"] = "closed"
        elif t == "prop":
            n = resolve_prop(el.get("name"))
            design = custom.get(slug(el.get("name"))) or custom.get(slug(el.get("name")).replace("_", ""))
            if design and n is None:
                el["params"] = to_element_params(design, el.get("params"))
                n = "custom"
            elif n == "custom":
                parts = clean_parts((el.get("params") or {}).get("parts"))
                if len(parts) < 2:
                    fixes.append("dropped a custom prop without shapes")
                    continue
                el["params"] = dict(el.get("params") or {}, parts=parts)
            if n is None:
                n = guess_prop(el.get("name"))
                if n is None:
                    fixes.append(f"dropped unknown prop {el.get('name')!r}")
                    continue
                fixes.append(f"prop {el.get('name')!r} -> {n!r}")
            el["name"] = n
            el["scale"] = max(0.1, min(_f(el.get("scale"), 1.0), 3.0))
        elif t == "icons":
            design = custom.get(slug(el.get("icon")))
            if design and resolve_prop(el.get("icon")) is None:
                el["params"] = to_element_params(design, el.get("params"))
                n = "custom"
            else:
                n = resolve_prop(el.get("icon")) or guess_prop(el.get("icon")) or "mini_carrier"
                if n == "custom" and len(clean_parts((el.get("params") or {}).get("parts"))) < 2:
                    n = "mini_carrier"
            el["icon"] = n
            el["count"] = int(max(1, min(_f(el.get("count"), 6), 120)))
        elif t == "text":
            el["text"] = str(el.get("text", ""))[:120]
            el["size"] = max(30, min(_f(el.get("size"), 64), 200))
            if bg["type"] in ("dark", "night", "space", "underwater") or \
                    (bg["type"] == "map" and bg.get("style") == "dark") or \
                    (bg.get("time") == "night" and bg["type"] in ("field", "hills", "city", "snow", "street", "harbor",
                                                                   "beach", "jungle", "mountains")):
                from .palette import color as _col
                from .compiler import luminance
                if el.get("color") is None or luminance(_col(el.get("color"))) < 0.45:
                    el["color"] = "#EBEBF5"
            if el.get("font") not in (None, "bold", "hand"):
                el["font"] = "hand" if "hand" in str(el.get("font")) else "bold"
        elif t in ("bubble", "note", "sign"):
            el["text"] = str(el.get("text", ""))[:160]
        elif t == "board":
            el["lines"] = [str(l)[:60] for l in (el.get("lines") or [])][:8]

        # positions: map coordinates only make sense on maps
        if not is_map and (el.get("lon") is not None or el.get("lat") is not None) and el.get("x") is None:
            el.pop("lon", None)
            el.pop("lat", None)
            fixes.append(f"{t}: lon/lat in a non-map scene, used default position")
        if is_map and el.get("lon") is not None and el.get("lat") is not None:
            mx, my = view.xy(_f(el["lon"], 0), _f(el["lat"], 0))
            if t == "city":
                if not (0 <= mx <= W and 0 <= my <= H - CAPTION_ZONE + 40):
                    fixes.append(f"city {el.get('name')!r} is outside the visible map")
            elif t in ("text", "char", "prop", "bubble", "note", "icons", "sign", "board"):
                probe = dict(el, x=mx, y=my)
                probe.pop("lon", None)
                probe.pop("lat", None)
                bb = element_bbox(probe)
                limit = H - CAPTION_ZONE if t in ("text", "bubble", "note", "board") else H
                if bb is not None and (bb[0] < safe[0] or bb[2] > safe[2] or bb[1] < safe[1] or bb[3] > min(limit, safe[3] if t != "char" else H)):
                    el.pop("lon")
                    el.pop("lat")
                    el["x"], el["y"] = round(mx), round(my)
                    fixes.append(f"{t} at lon/lat was off-screen; converted to screen position")
        # keep things inside the frame, and text out of the caption zone
        if t == "text":
            _shrink_text(el, W - 40)
        bb = element_bbox(el)
        if bb is not None:
            limit = H - CAPTION_ZONE if t in ("text", "bubble", "note", "board", "sign") else H
            if t == "sign":
                limit = H
            if t == "char":
                # feet may stand in the caption zone; only keep the body inside the visible area
                cs = (safe[0], safe[1], safe[2], H)
                moved = _shift_into_frame(el, bb, bottom_limit=H, safe=cs)
            else:
                moved = _shift_into_frame(el, bb, bottom_limit=limit, safe=safe)
            if moved:
                fixes.append(f"{t} moved inside the frame / out of the caption zone")
        out.append(el)

    # "say" lines -> speech bubbles over the speaker's head, one after another
    for el, says in pending_says:
        if el in out:
            made = say_bubbles(el, says, safe, mood, out)
            out.extend(made)

    # labels sitting on a character's face move above its head
    heads = []
    for e in out:
        if e.get("type") == "char" and e.get("lon") is None:
            sc_ = _f(e.get("scale"), 1.0)
            cx, cy = _f(e.get("x"), 960), _f(e.get("y"), 900)
            heads.append((cx - 70 * sc_, cy - 340 * sc_, cx + 70 * sc_, cy - 236 * sc_))  # the face, below any hat
    for e in out:
        if e.get("type") != "text" or e.get("lon") is not None:
            continue
        bb = element_bbox(e)
        for hb in heads:
            if bb and overlaps(bb, hb, pad=0):
                ny = hb[1] - (bb[3] - bb[1]) / 2 - 12
                if ny - (bb[3] - bb[1]) / 2 >= safe[1]:
                    e["y"] = round(ny)
                    fixes.append(f"label '{str(e.get('text'))[:20]}' moved off a character's face")
                break

    # nudge overlapping text-like elements apart (later one moves down, or up if no room)
    # boards and signs are containers: text placed on top of them is intentional
    textish = [e for e in out if e.get("type") in ("text", "bubble", "note") and element_bbox(e)]
    for i, a in enumerate(textish):
        for b in textish[i + 1:]:
            ba, bb_ = element_bbox(a), element_bbox(b)
            if ba and bb_ and overlaps(ba, bb_) and a.get("exit") is None and b.get("exit") is None and \
                    not b.get("placed"):
                hb = bb_[3] - bb_[1]
                down = ba[3] + 10 - bb_[1]
                up = bb_[3] - (ba[1] - 10)
                if bb_[3] + down <= H - CAPTION_ZONE:
                    b["y"] = round(_f(b.get("y"), 540) + down)
                elif bb_[1] - up >= 8:
                    b["y"] = round(_f(b.get("y"), 540) - up)
                else:
                    continue
                fixes.append(f"moved overlapping {b.get('type')} '{str(b.get('text') or b.get('title') or '')[:20]}'")
    if len(out) > 24:
        fixes.append(f"too many elements ({len(out)}), kept 24")
        out = out[:24]
    sc["elements"] = out
    cam = sc.get("camera")
    if cam is not None and not isinstance(cam, dict):
        sc["camera"] = {}
    return sc, fixes


def check_scene(scene, mood="fun", text="", kit=None):
    """repair + validate. Returns (scene, fixes, errors)."""
    fixed, fixes = repair_scene(scene, mood, text, kit)
    return fixed, fixes, validate_scene(fixed)
