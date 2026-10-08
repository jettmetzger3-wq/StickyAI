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
from .pen import ARMS, LEGS, MOUTHS, EYES, EXTRAS, HELD, HATS, KIND_ALIASES, MOUNTS, MOUNT_ALIASES, mount_lift, hat_top, \
    resolve_kind
from .puppet import resolve_action
from .registry import PROPS, PROP_ALIASES, resolve_prop, guess_prop, prop_bounds, prop_anchor
from .custom_props import clean_parts, kit_lookup, to_element_params, slug
from .geo import REGIONS, View, unknown_names
from .captions import CAPTION_ZONE
from .weather import WEATHERS, LIGHTS, norm_weather, norm_light

BG_TYPES = ("paper", "sunburst", "ground", "field", "hills", "desert", "snow", "city", "interior", "battlefield",
            "sea", "night", "dark", "map", "street", "palace", "harbor", "beach", "underwater", "space", "jungle",
            "mountains", "trench", "construction", "factory", "farm", "mine", "classroom", "lab", "parliament",
            "courtroom", "prison", "market", "camp")
BG_ALIASES = {"ocean": "sea", "port": "harbor", "docks": "harbor", "harbour": "harbor", "coast": "beach",
              "island": "beach", "shore": "beach", "seabed": "underwater", "under_water": "underwater",
              "deep_sea": "underwater", "town": "street", "village": "street", "road": "street",
              "throne_room": "palace", "court": "palace", "royal_court": "palace", "ballroom": "palace",
              "castle_hall": "palace", "room": "interior", "office": "interior", "house": "interior",
              "stars": "space", "orbit": "space", "forest": "jungle", "rainforest": "jungle", "alps": "mountains",
              "mountain": "mountains", "trenches": "trench", "war": "battlefield", "battle": "battlefield",
              "skyline": "city", "plain": "field", "meadow": "field", "countryside": "hills", "sand": "desert",
              "arctic": "snow", "winter": "snow",
              # places where things happen (places_work.py)
              "construction_site": "construction", "building_site": "construction", "site": "construction",
              "shipyard": "construction", "dockyard": "construction", "build": "construction",
              "factory_floor": "factory", "assembly_line": "factory", "industry": "factory", "industrial": "factory",
              "mill": "factory", "workshop": "factory", "plant": "factory", "foundry": "factory",
              "steelworks": "factory", "farmland": "farm", "fields": "farm", "ranch": "farm", "plantation": "farm",
              "mines": "mine", "coal_mine": "mine", "gold_mine": "mine", "tunnel": "mine", "quarry": "mine",
              "school": "classroom", "class": "classroom", "university": "classroom", "lecture": "classroom",
              "laboratory": "lab", "science": "lab", "senate": "parliament", "congress": "parliament",
              "assembly": "parliament", "house_of_commons": "parliament", "chamber": "parliament",
              "legislature": "parliament", "duma": "parliament", "reichstag": "parliament",
              "courthouse": "courtroom", "trial": "courtroom", "tribunal": "courtroom", "jail": "prison",
              "cell": "prison", "dungeon": "prison", "gulag": "prison", "bazaar": "market",
              "marketplace": "market", "souk": "market", "fair": "market", "army_camp": "camp",
              "encampment": "camp", "barracks": "camp", "bivouac": "camp", "tents": "camp"}
# what a bg alias also says about the place: a shipyard is a construction site with a ship on it
BG_PRESETS = {"shipyard": {"what": "ship"}, "dockyard": {"what": "ship"}, "factory_floor": {"style": "inside"},
              "assembly_line": {"style": "inside"}, "workshop": {"style": "inside"}}
PLACE_STYLES = {"battlefield": ("river", "open", "ruins"), "factory": ("outside", "inside"),
                "market": ("europe", "medieval", "asia", "arab", "western")}
TIMES = ("day", "dawn", "dusk", "night", "storm")
ENTERS = ("pop", "drop", "grow", "fade", "slide_left", "slide_right", "slide_up", "slide_down",
          "wipe_right", "wipe_left", "wipe_up", "wipe_down", "none")
IDLES = ("bob", "float", "pulse", "shake", "drift", "none")
SFX = ("auto", "none", "pop", "whoosh", "swish", "boom", "tick")
EL_TYPES = ("char", "crowd", "text", "prop", "bubble", "note", "sign", "board", "icons", "shape", "group",
            "territory", "city", "arrow", "pointer", "battle", "front", "counter", "empire", "route", "chart",
            "timeline", "compare", "split")
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
                 auto={"type": "boolean"}, life={"type": "boolean"}, coat={"type": "string"},
                 ride={"enum": list(MOUNTS)}, who={"type": "string"}),
    "crowd": _obj(("type",), type={"const": "crowd"}, **_xy, **_anim, kind={"type": "string"}, count=_num, rows=_num,
                  width=_num, scale=_num, flip={"type": "boolean"}, do={"type": "array", "maxItems": 12},
                  mouth={"enum": list(MOUTHS)}, eyes={"enum": list(EYES)}, prop={"enum": list(HELD)},
                  pose={"anyOf": [{"enum": list(ARMS)}, {"type": "array"}]}, hat_color={"type": "string"},
                  coat={"type": "string"}, ride={"enum": list(MOUNTS)}, who={"type": "string"}),
    "pointer": _obj(("type",), type={"const": "pointer"}, **_xy, **_anim, **{"from": {"enum": list(POINTER_DIRS)}},
                    size=_num, color={"type": "string"}),
    "text": _obj(("type", "text"), type={"const": "text"}, **_xy, **_anim, text={"type": "string"}, size=_num,
                 color={"type": "string"}, font={"enum": ["bold", "hand"]}, stroke=_num,
                 align={"enum": ["center", "left", "right"]}),
    "prop": _obj(("type", "name"), type={"const": "prop"}, **_xy, **_anim, name={"enum": sorted(PROPS)}, scale=_num,
                 animate={"type": "boolean"}, do={"type": "array", "maxItems": 4, "items": {
                     "type": "object", "required": ["act"], "properties": {
                         "act": {"enum": ["fire", "explode", "collapse", "sink", "shake"]}, "at": _at, "dur": _num,
                         "target": _pt}}},
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
                 lon=_num, lat=_num, size=_num, color={"type": "string"}, dot={"type": "boolean"},
                 capital={"type": "boolean"}),
    "empire": _obj(("type", "steps"), type={"const": "empire"}, **_anim, name={"type": "string"},
                   color={"type": "string"}, size=_num, label_at=_pt, year_at=_pt, year_size=_num,
                   show_year={"type": "boolean"},
                   steps={"type": "array", "minItems": 1, "maxItems": 6, "items": {
                       "type": "object", "properties": {"at": _at, "year": _num, "region": {"type": "string"},
                                                        "countries": {"type": "array", "items": {"type": "string"}},
                                                        "clip": {"type": "array"}, "box": {"type": "array"}}}}),
    "chart": _obj(("type", "data"), type={"const": "chart"}, **_xy, **_anim, style={"enum": ["bar", "hbar", "line"]},
                  title={"type": "string"}, w=_num, h=_num, dur=_num, max=_num, decimals=_num,
                  prefix={"type": "string"}, suffix={"type": "string"},
                  data={"type": "array", "minItems": 1, "maxItems": 10, "items": {
                      "type": "object", "required": ["label", "value"],
                      "properties": {"label": {"type": "string"}, "value": _num, "color": {"type": "string"}}}}),
    "timeline": _obj(("type", "events"), type={"const": "timeline"}, **_anim, y=_num, x0=_num, x1=_num,
                     color={"type": "string"}, travel={"type": "boolean"}, **{"from": _num}, to=_num,
                     events={"type": "array", "minItems": 1, "maxItems": 8, "items": {
                         "type": "object", "required": ["year"],
                         "properties": {"year": _num, "label": {"type": "string"}, "at": _at,
                                        "color": {"type": "string"}}}}),
    "compare": _obj(("type", "items"), type={"const": "compare"}, **_xy, **_anim, size=_num,
                    prefix={"type": "string"}, suffix={"type": "string"},
                    items={"type": "array", "minItems": 1, "maxItems": 4, "items": {
                        "type": "object", "required": ["value"],
                        "properties": {"label": {"type": "string"}, "value": _num, "color": {"type": "string"},
                                       "icon": {"type": "string"}}}}),
    "split": _obj(("type",), type={"const": "split"}, **_anim, left={"type": "string"}, right={"type": "string"},
                  tint={"enum": ["left", "right", "none"]}),
    "route": _obj(("type",), type={"const": "route"}, **_anim, **{"from": _pt}, to=_pt,
                  points={"type": "array", "items": _pt}, curve=_num, color={"type": "string"}, width=_num,
                  style={"enum": ["dashed", "dotted", "solid"]}, icon={"type": "string"}, icon_scale=_num, dur=_num),
    "arrow": _obj(("type",), type={"const": "arrow"}, **_anim, **{"from": _pt}, to=_pt,
                  points={"type": "array", "items": _pt}, curve=_num, color={"type": "string"}, width=_num,
                  head={"type": "boolean"}, units={"type": "string"}, count=_num, march=_num,
                  unit_color={"type": "string"}, unit_scale=_num),
    "battle": _obj(("type",), type={"const": "battle"}, **_xy, **_anim, label={"type": "string"}, size=_num),
    "front": _obj(("type",), type={"const": "front"}, **_anim, points={"type": "array", "items": _pt},
                  keys={"type": "array", "maxItems": 6, "items": {"type": "object", "required": ["points"],
                                                                  "properties": {"at": _at, "points": {
                                                                      "type": "array", "items": _pt}}}},
                  color={"type": "string"}, width=_num, side={"enum": ["left", "right"]}, teeth={"type": "boolean"}),
    "counter": _obj(("type", "from", "to"), type={"const": "counter"}, **_xy, **_anim, **{"from": _num}, to=_num,
                    until=_at, dur=_num, size=_num, color={"type": "string"}, prefix={"type": "string"},
                    suffix={"type": "string"}, decimals=_num, format={"enum": ["year", "number"]}),
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
                "style": {"enum": ["paper", "dark", "europe", "medieval", "asia", "arab", "western", "river", "open",
                                   "ruins", "outside", "inside"]},
                "what": {"enum": ["factory", "house", "tower", "castle", "wall", "ship"]},
                "progress": {"anyOf": [_num, {"type": "array", "items": _num, "minItems": 2, "maxItems": 2},
                                       {"enum": ["done"]}]},
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
                                                            "region": {"type": "string"},
                                                            "move": {"enum": list(MOVES)}}}}}},
        "note": {"type": "string"},
        "transition": {"enum": ["auto", "cut", "slide", "wipe", "zoom", "iris", "paper", "fade"]},
        "weather": {"type": "object", "required": ["type"],
                    "properties": {"type": {"enum": list(WEATHERS)}, "amount": _num, "wind": _num, "at": _at,
                                   "until": _at}},
        "light": {"type": "object", "required": ["to"],
                  "properties": {"to": {"enum": list(LIGHTS)}, "at": _at, "dur": _num}},
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
                "indicator": "pointer", "big_arrow": "pointer", "empire_growth": "empire", "expansion": "empire",
                "borders": "empire", "kingdom": "empire", "trade_route": "route", "voyage": "route",
                "journey": "route", "path": "route", "trail": "route", "capital": "city", "bar_chart": "chart",
                "graph": "chart", "line_chart": "chart", "line_graph": "chart", "bars": "chart", "ranking": "chart",
                "chart_bar": "chart", "stats": "chart", "time_line": "timeline", "dates": "timeline",
                "comparison": "compare", "versus": "compare", "vs": "compare", "size_comparison": "compare",
                "then_now": "split", "then_vs_now": "split", "before_after": "split", "split_screen": "split"}
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
        lift, half = mount_lift(el.get("ride"), s)
        return (x - max(130 * s, half), y - 375 * s - lift, x + max(130 * s, half), y + 15 * s)
    if t == "text":
        return text_bbox(el.get("text", ""), x, y, _f(el.get("size"), 64), el.get("font", "bold"), el.get("align", "center"))
    if t == "counter":
        from .warmap import fmt_count
        longest = max(fmt_count(_f(el.get(k), 0), "year" if el.get("format") == "year" else "number",
                                str(el.get("prefix", "")), str(el.get("suffix", ""))) for k in ("from", "to"))
        return text_bbox(longest, x, y, _f(el.get("size"), 90), "bold", "center")
    if t == "battle":
        s = _f(el.get("size"), 1.0)
        return (x - 70 * s, y - 70 * s, x + 70 * s, y + 70 * s + (60 * s if el.get("label") else 0))
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


def char_box(el):
    """The space a character (head, hat and body) or a crowd takes on screen: nothing else should cover it."""
    if el.get("lon") is not None:
        return None
    x, y = _f(el.get("x"), 960), _f(el.get("y"), 900)
    if el.get("type") == "crowd":
        s_ = _f(el.get("scale"), 0.6)
        w = max(_f(el.get("width"), 600), 160) / 2 + 60 * s_
        return (x - w, y - 400 * s_ - 70 * (int(_f(el.get("rows"), 2)) - 1) - 20, x + w, y + 12)
    if el.get("type") != "char":
        return None
    s_ = _f(el.get("scale"), 1.0)
    lift, half = mount_lift(el.get("ride"), s_)
    top = y - max(405, 300 + hat_top(str(el.get("kind") or "")) + 26) * s_ - lift
    return (x - max(115 * s_, half), top, x + max(115 * s_, half), y + 12 * s_)


def _area(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


BUBBLE_MARGIN = 56                    # speech bubbles keep this far from the edge of the frame (see layout.py)


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
        head_top = fy - max(405, 300 + hat_top(kind) + 26) * s - mount_lift(el.get("ride"), s)[0]
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
    people = [char_box(o) for o in others if o is not el and o.get("type") in ("char", "crowd") and char_box(o)]

    def area(a, b):
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))

    made = []
    safe = (max(safe[0], BUBBLE_MARGIN), safe[1], min(safe[2], W - BUBBLE_MARGIN), safe[3])     # keep clear of the frame edge
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
                    sum(area(bb, o) for o in people) * 12 + abs(bx - tip_x) * 2 + (tip_y - by) * 3
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


LOOKS = ("beard", "mustache")
COSTUMES = ("crown", "laurel", "knight", "astronaut", "wizard", "chef", "graduate", "pirate", "headphones", "glasses",
            "hardhat", "mitre", "turban", "cowboy", "pilot")


def cast_member(cast, who):
    """The cast entry a character's "who" refers to ("Napoleon" finds "Napoleon Bonaparte")."""
    w = str(who or "").strip().lower()
    if not w or not cast:
        return None
    for c in cast:
        n = str(c.get("name") or "").strip().lower()
        if n and (n == w or w in n.split() or n in w or w in n):
            return c
    return None


def apply_cast(el, cast, fixes):
    """Make a character look like its cast entry in every scene: same hat, outfit color and beard."""
    t = el.get("type")
    c = cast_member(cast, el.get("who"))
    if c is None and el.get("who") is None and el.get("kind"):
        # no name given: a hat worn by exactly one cast member is that member
        k = resolve_kind(el["kind"])
        same = [m for m in cast if resolve_kind(m.get("kind")) == k]
        c = same[0] if len(same) == 1 else None
    if c is None:
        return
    ck = str(c.get("kind") or "").strip().lower()
    if ck and t == "char" and (not el.get("kind") or el.get("kind") == "civ") and (ck in HATS or ck in KIND_ALIASES):
        el["kind"] = ck
    elif ck and t == "char" and el.get("who") and resolve_kind(el.get("kind")) != resolve_kind(ck) and \
            resolve_kind(el.get("kind")) not in COSTUMES:
        fixes.append(f"{c.get('name')} keeps the hat from the cast ({ck})")
        el["kind"] = ck
    if c.get("coat") and not el.get("coat"):
        el["coat"] = c["coat"]
    if c.get("hat_color") and not el.get("hat_color"):
        el["hat_color"] = c["hat_color"]
    look = str(c.get("look") or "").strip().lower()
    if t == "char" and look in LOOKS:
        ex = list(el.get("extras") or [])
        if look not in ex and not any(x in ex for x in LOOKS):
            el["extras"] = ex + [look]


def repair_scene(scene, mood="fun", text="", kit=None, cast=None):
    """Fix common LLM mistakes. Returns (scene, list_of_fixes).
    kit: the props designed for this video (see custom_props); scenes may use them by name.
    cast: the script's recurring characters; characters in the scene take their look from it."""
    fixes = []
    cast = [c for c in (cast or []) if isinstance(c, dict)]
    custom = kit_lookup(kit)
    if not isinstance(scene, dict):
        return {"bg": {"type": "paper"}, "elements": []}, ["scene was not an object; replaced with an empty one"]
    sc = copy.deepcopy(scene)
    # background
    bg = sc.get("bg") if isinstance(sc.get("bg"), dict) else {"type": sc.get("bg") if isinstance(sc.get("bg"), str) else "paper"}
    bt = str(bg.get("type") or "").strip().lower().replace(" ", "_")
    for k, v in BG_PRESETS.get(bt, {}).items():
        bg.setdefault(k, v)
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
    elif bt in PLACE_STYLES:
        st = str(bg.get("style") or "").strip().lower().replace(" ", "_").replace("-", "_")
        st = {"interior": "inside", "indoors": "inside", "floor": "inside", "assembly": "inside",
              "exterior": "outside", "outdoors": "outside", "bridge": "river", "plain": "open", "field": "open",
              "ruined": "ruins", "bombed": "ruins", "ww1": "ruins", "wwi": "ruins", "ww2": "ruins",
              "european": "europe", "asian": "asia", "arabic": "arab", "middle_east": "arab",
              "wild_west": "western"}.get(st, st)
        if st in PLACE_STYLES[bt]:
            bg["style"] = st
        else:
            bg.pop("style", None)
    elif bg.get("style") is not None and bg["style"] not in ("paper", "dark"):
        bg["style"] = "dark" if "dark" in str(bg["style"]).lower() else "paper"
    if bt == "construction":
        from .places_work import norm_what, build_progress
        bg["what"] = norm_what(bg.get("what") or build_what_from_text(text))
        if bg.get("progress") is not None:
            a, b = build_progress(bg["progress"])
            bg["progress"] = "done" if a >= 0.999 else [round(a, 2), round(b, 2)]
    else:
        bg.pop("what", None)
        bg.pop("progress", None)
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
            if t2 == "chart" and not el.get("style"):
                el["style"] = "line" if "line" in str(t) else "hbar" if str(t) == "ranking" else "bar"
        t = t2
        says = el.pop("say", None) if t in ("char", "crowd") else None
        if says:
            pending_says.append((el, says))
        if is_map and t in ("arrow", "route", "front"):
            _lonlat_points(el, fixes)
        if t in ("territory", "city", "empire") and not is_map:
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
        if t in ("char", "crowd") and cast:
            apply_cast(el, cast, fixes)
        if t in ("char", "crowd"):
            if el.get("who") is not None:
                el["who"] = str(el["who"])[:40]
            if el.get("ride") is not None:
                r = str(el["ride"]).strip().lower().replace(" ", "_")
                r = MOUNT_ALIASES.get(r, r)
                r = r if r in MOUNTS else nearest(r, list(MOUNTS), None)
                if r:
                    el["ride"] = r
                else:
                    fixes.append(f"{t}: can't ride {el['ride']!r}")
                    el.pop("ride")
            if el.get("coat") is not None:
                from .palette import color as _col
                if not isinstance(el["coat"], str) or _col(el["coat"], None) is None:
                    fixes.append(f"{t}: coat color {el['coat']!r} not understood")
                    el.pop("coat")
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
            if el.get("do") is not None:
                from .action_fx import resolve_prop_act
                acts = []
                for a in el["do"] if isinstance(el["do"], list) else [el["do"]]:
                    a = {"act": a} if isinstance(a, str) else a
                    if not isinstance(a, dict):
                        continue
                    k = resolve_prop_act(a.get("act") or a.get("action"))
                    if not k:
                        fixes.append(f"prop {n}: unknown action {a.get('act')!r} dropped")
                        continue
                    if mood == "somber" and k in ("explode",):
                        fixes.append(f"somber scene: prop {n} doesn't explode")
                        continue
                    a = {kk: v for kk, v in dict(a, act=k).items() if kk in ("act", "at", "dur", "target")}
                    if a.get("dur") is not None:
                        a["dur"] = max(0.4, min(_f(a["dur"], 2.0), 10))
                    if a.get("target") is not None and not (isinstance(a["target"], (list, dict))):
                        a.pop("target")
                    acts.append(a)
                if acts:
                    el["do"] = acts[:4]
                else:
                    el.pop("do", None)
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
        elif t == "battle":
            el["label"] = str(el.get("label") or el.get("text") or "")[:24]
            el.pop("text", None)
            el["size"] = max(0.4, min(_f(el.get("size"), 1.0), 2.5))
        elif t == "empire":
            steps = []
            for st in el.get("steps") or []:
                if isinstance(st, str):
                    st = {"region": st} if st.lower() in REGIONS else {"countries": [st]}
                if not isinstance(st, dict):
                    continue
                st = {k: v for k, v in st.items() if k in ("at", "year", "region", "countries", "clip", "box")}
                if isinstance(st.get("countries"), str):
                    st["countries"] = [st["countries"]]
                if st.get("countries"):
                    bad = unknown_names(st["countries"])
                    if bad:
                        fixes.append(f"empire: unknown countries {bad}")
                        st["countries"] = [c for c in st["countries"] if c not in bad]
                        if not st["countries"]:
                            st.pop("countries")
                if st.get("region") is not None and str(st["region"]).lower() not in REGIONS:
                    fixes.append(f"empire: unknown region {st['region']!r}")
                    st.pop("region")
                if not st.get("countries") and not st.get("region"):
                    continue
                if st.get("year") is not None:
                    try:
                        st["year"] = int(round(float(st["year"])))
                    except (TypeError, ValueError):
                        st.pop("year")
                steps.append(st)
            if not steps:
                fixes.append("dropped an empire without usable steps")
                continue
            el["steps"] = steps[:6]
            if el.get("name") is not None:
                el["name"] = str(el["name"])[:30]
        elif t == "chart":
            rows = []
            data = el.get("data") if isinstance(el.get("data"), list) else el.get("bars") or el.get("items") or []
            for d in data if isinstance(data, list) else []:
                if isinstance(d, (list, tuple)) and len(d) >= 2:
                    d = {"label": d[0], "value": d[1]}
                if not isinstance(d, dict) or d.get("value") is None:
                    continue
                try:
                    v = float(str(d["value"]).replace(",", "").replace("%", "").replace("$", ""))
                except ValueError:
                    continue
                row = {"label": str(d.get("label", d.get("name", "")))[:18], "value": v}
                if d.get("color") is not None:
                    row["color"] = str(d["color"])
                rows.append(row)
            el.pop("bars", None)
            el.pop("items", None)
            if not rows:
                fixes.append("dropped a chart without numbers")
                continue
            el["data"] = rows[:10]
            st = str(el.get("style") or "bar").lower()
            el["style"] = "hbar" if st in ("hbar", "horizontal", "ranking", "race") else "line" if "line" in st else "bar"
            if el.get("title") is not None:
                el["title"] = str(el["title"])[:40]
            for k in ("prefix", "suffix"):
                if el.get(k) is not None:
                    el[k] = str(el[k])[:10]
            w_, h_ = max(400, min(_f(el.get("w"), 1100), W - 40)), max(300, min(_f(el.get("h"), 620), 860))
            el["w"], el["h"] = w_, h_
            cx_, cy_ = _f(el.get("x"), 960), _f(el.get("y"), 470)
            el["x"] = max(w_ / 2 + 20, min(cx_, W - w_ / 2 - 20))
            el["y"] = max(h_ / 2 + 10, min(cy_, H - CAPTION_ZONE - h_ / 2))
        elif t == "timeline":
            evs = []
            for e in el.get("events") or []:
                if isinstance(e, (list, tuple)) and len(e) >= 1:
                    e = {"year": e[0], "label": e[1] if len(e) > 1 else ""}
                if not isinstance(e, dict):
                    continue
                try:
                    yr = int(round(float(str(e.get("year", e.get("date"))).replace("BC", "").strip()) *
                                   (-1 if "BC" in str(e.get("year", "")) else 1)))
                except (TypeError, ValueError):
                    continue
                ev = {k: v for k, v in e.items() if k in ("at", "color")}
                ev["year"] = yr
                ev["label"] = str(e.get("label") or e.get("text") or "")[:24]
                evs.append(ev)
            if not evs:
                fixes.append("dropped a timeline without years")
                continue
            el["events"] = evs[:8]
            el["y"] = max(300, min(_f(el.get("y"), 640), 800))
        elif t == "compare":
            items = []
            for it in el.get("items") or []:
                if not isinstance(it, dict) or it.get("value") is None:
                    continue
                try:
                    v = float(str(it["value"]).replace(",", ""))
                except ValueError:
                    continue
                c = {k: v_ for k, v_ in it.items() if k in ("label", "color", "prefix", "suffix")}
                c["value"] = v
                if it.get("icon") is not None:
                    ic = resolve_prop(it["icon"]) or guess_prop(it["icon"])
                    if ic:
                        c["icon"] = ic
                if c.get("label") is not None:
                    c["label"] = str(c["label"])[:20]
                items.append(c)
            if not items:
                fixes.append("dropped a comparison without numbers")
                continue
            el["items"] = items[:4]
        elif t == "split":
            for k in ("left", "right"):
                if el.get(k) is not None:
                    el[k] = str(el[k])[:16]
            if el.get("tint") not in (None, "left", "right", "none"):
                el["tint"] = "none" if el["tint"] in (False, "no", "off") else "left"
        elif t == "route":
            pts = el.get("points") if isinstance(el.get("points"), list) else \
                [el.get("from"), el.get("to")] if el.get("from") is not None and el.get("to") is not None else []
            pts = [q for q in pts if (isinstance(q, (list, tuple)) and len(q) >= 2) or
                   (isinstance(q, dict) and (("lon" in q and "lat" in q and is_map) or ("x" in q and "y" in q)))]
            if len(pts) < 2:
                fixes.append("dropped a route without usable points")
                continue
            el["points"] = pts[:40]
            el.pop("from", None)
            el.pop("to", None)
            if el.get("style") not in (None, "dashed", "dotted", "solid"):
                el["style"] = "dotted" if "dot" in str(el["style"]) else "solid" if "solid" in str(el["style"]) else "dashed"
            ic = el.pop("units", None) if el.get("icon") is None else el.get("icon")
            if ic is not None:
                from .warmap import is_kind
                u = str(ic).strip().lower().replace(" ", "_")
                if resolve_prop(u):
                    el["icon"] = resolve_prop(u)
                elif is_kind(u):
                    el["icon"] = u
                else:
                    g = guess_prop(u)
                    if g:
                        el["icon"] = g
                    else:
                        el.pop("icon", None)
                        fixes.append(f"route icon {u!r} not found")
        elif t == "front":
            def _pts(ps):
                if not isinstance(ps, list):
                    return []
                ok = [q for q in ps if (isinstance(q, (list, tuple)) and len(q) >= 2) or
                      (isinstance(q, dict) and (("lon" in q and "lat" in q and is_map) or ("x" in q and "y" in q)))]
                return ok if len(ok) >= 2 else []
            if el.get("keys"):
                keys = [dict(k, points=_pts(k.get("points"))) for k in el["keys"] if isinstance(k, dict)]
                el["keys"] = [k for k in keys if k["points"]][:6]
                if not el["keys"]:
                    el.pop("keys")
            if el.get("points") is not None:
                el["points"] = _pts(el["points"])
                if not el["points"]:
                    el.pop("points")
            if not el.get("keys") and not el.get("points"):
                fixes.append("dropped a front line without usable points")
                continue
            el["width"] = max(4, min(_f(el.get("width"), 12), 30))
            if el.get("side") not in (None, "left", "right"):
                el["side"] = "left" if str(el["side"]).lower().startswith("l") else "right"
        elif t == "counter":
            if bg["type"] in ("dark", "night", "space", "underwater") or (bg["type"] == "map" and bg.get("style") == "dark"):
                from .palette import color as _col
                from .compiler import luminance
                if el.get("color") is None or luminance(_col(el.get("color"))) < 0.45:
                    el["color"] = "#EBEBF5"
            try:
                el["from"], el["to"] = float(el.get("from")), float(el.get("to"))
            except (TypeError, ValueError):
                fixes.append("dropped a counter without numbers")
                continue
            for k in ("from", "to"):
                if el[k] == int(el[k]):
                    el[k] = int(el[k])
            el["size"] = max(30, min(_f(el.get("size"), 90), 220))
            for k in ("prefix", "suffix"):
                if el.get(k) is not None:
                    el[k] = str(el[k])[:14]
            if el.get("format") not in (None, "year", "number"):
                el["format"] = "year" if "year" in str(el["format"]).lower() else "number"
        elif t == "arrow" and el.get("units") is not None:
            from .warmap import is_kind
            u = str(el["units"]).strip().lower().replace(" ", "_")
            if resolve_prop(u):
                el["units"] = resolve_prop(u)
            elif is_kind(u):
                el["units"] = u
            else:
                g = guess_prop(u)
                el["units"] = g or "army"
                fixes.append(f"arrow units {u!r} -> {el['units']!r}")
            el["count"] = int(max(1, min(_f(el.get("count"), 1 if resolve_prop(el["units"]) else 4), 8)))
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
            elif t in ("text", "char", "prop", "bubble", "note", "icons", "sign", "board", "counter", "battle"):
                probe = dict(el, x=mx, y=my)
                probe.pop("lon", None)
                probe.pop("lat", None)
                bb = element_bbox(probe)
                limit = H - CAPTION_ZONE if t in ("text", "bubble", "note", "board", "counter", "battle") else H
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
            limit = H - CAPTION_ZONE if t in ("text", "bubble", "note", "board", "sign", "counter", "battle") else H
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

    # nothing may cover a character: labels and bubbles keep off every head, hat and body; props that overlap go behind it
    people = [(e, char_box(e)) for e in out if e.get("type") in ("char", "crowd") and char_box(e)]
    top_limit = safe[1] + 6
    for e in out:
        t_ = e.get("type")
        if e.get("lon") is not None or e.get("placed") or t_ not in ("text", "note", "sign", "counter", "bubble", "board", "prop", "icons"):
            continue
        bb = element_bbox(e)
        if not bb or not people:
            continue
        def zone(pb):
            """What a label must not cover: the head and hat (the top half of the box). Bubbles, notes and signs
            must keep off the whole character."""
            return (pb[0], pb[1], pb[2], pb[1] + 0.5 * (pb[3] - pb[1])) if t_ == "text" else pb
        label_area = max(1.0, (bb[2] - bb[0]) * (bb[3] - bb[1]))
        hits = [(p, pb) for p, pb in people if p is not e and _area(bb, zone(pb)) > 0]
        if not hits or sum(_area(bb, zone(pb)) for _, pb in hits) <= (0.4 if t_ == "text" else 0.12) * label_area:
            continue
        if t_ in ("prop", "icons"):
            # a free-standing thing that overlaps a character is drawn BEHIND it (held items are the character's own `prop`)
            if e.get("z") is None:
                e["z"] = 0
            continue
        if t_ == "crowd" or (t_ == "text" and e.get("exit") is not None):
            continue
        h_ = bb[3] - bb[1]
        w_ = bb[2] - bb[0]
        cx_, cy_ = _f(e.get("x"), 960), _f(e.get("y"), 540)
        cands = []
        top_of_all = min(pb[1] for _, pb in hits)
        cands.append((cx_, cy_ - (bb[3] - top_of_all) - 12))                      # above the heads
        lx = min(pb[0] for _, pb in hits)
        rx = max(pb[2] for _, pb in hits)
        cands.append((lx - w_ / 2 - 14, cy_))                                      # to the left of them
        cands.append((rx + w_ / 2 + 14, cy_))                                      # to the right of them
        best, best_cost = None, None
        for nx, ny in cands:
            nb = (bb[0] + nx - cx_, bb[1] + ny - cy_, bb[2] + nx - cx_, bb[3] + ny - cy_)
            if nb[0] < safe[0] or nb[2] > safe[2] or nb[1] < top_limit or nb[3] > H - CAPTION_ZONE:
                continue
            cost = sum(_area(nb, pb) for _, pb in people if _ is not e) * 5 + abs(nx - cx_) + abs(ny - cy_)
            if best_cost is None or cost < best_cost:
                best, best_cost = (nx, ny), cost
        if best is not None:
            now = sum(_area(bb, pb) for _, pb in hits)
            nb2 = (bb[0] + best[0] - cx_, bb[1] + best[1] - cy_, bb[2] + best[0] - cx_, bb[3] + best[1] - cy_)
            if sum(_area(nb2, pb) for _, pb in people) < now:
                e["x"], e["y"] = round(best[0]), round(best[1])
                fixes.append(f"{t_} '{str(e.get('text') or e.get('title') or '')[:20]}' moved so it doesn't cover a character")

    # nudge overlapping text-like elements apart (later one moves down, or up if no room)
    # boards and signs are containers: text placed on top of them is intentional
    textish = [e for e in out if e.get("type") in ("text", "bubble", "note", "counter") and element_bbox(e)]
    for i, a in enumerate(textish):
        for b in textish[i + 1:]:
            if b.get("placed") and not a.get("placed") and a.get("type") == "text":
                a, b = b, a                              # a speech bubble was placed on purpose: the label gives way
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
    if sc.get("transition") is not None:
        tr = str(sc["transition"]).lower().replace("_", "")
        tr = {"cutto": "cut", "push": "slide", "swipe": "wipe", "dissolve": "fade", "crossfade": "fade",
              "circle": "iris", "page": "paper", "pageturn": "paper", "zoomin": "zoom", "none": "cut"}.get(tr, tr)
        if tr not in ("auto", "cut", "slide", "wipe", "zoom", "iris", "paper", "fade"):
            fixes.append(f"unknown transition {sc['transition']!r}, used auto")
            tr = "auto"
        sc["transition"] = tr
    upgrade_place(sc, bg, text, fixes)
    repair_weather(sc, bg, mood, text, fixes)
    cam = sc.get("camera")
    if cam is not None and not isinstance(cam, dict):
        sc["camera"] = {}
    return sc, fixes


def _lonlat_points(el, fixes):
    """On a map, [lon, lat] lists written where {lon, lat} was meant: points that would all sit inside a
    180 x 90 pixel corner (or are negative) are coordinates, not pixels."""
    groups = []
    for k in ("points", "from", "to"):
        v = el.get(k)
        if k == "points" and isinstance(v, list):
            groups.append((k, v, True))
        elif isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(c, (int, float)) for c in v):
            groups.append((k, [v], False))
    for kk in el.get("keys") or []:
        if isinstance(kk, dict) and isinstance(kk.get("points"), list):
            groups.append((kk, kk["points"], True))
    pts = [q for _, v, _ in groups for q in v if isinstance(q, (list, tuple)) and len(q) >= 2]
    if not pts or not all(isinstance(q[0], (int, float)) and isinstance(q[1], (int, float)) and
                          abs(q[0]) <= 180 and abs(q[1]) <= 90 for q in pts):
        return
    conv = lambda q: {"lon": q[0], "lat": q[1]} if isinstance(q, (list, tuple)) and len(q) >= 2 else q
    for k, v, many in groups:
        if isinstance(k, dict):
            k["points"] = [conv(q) for q in v]
        elif many:
            el[k] = [conv(q) for q in v]
        else:
            el[k] = conv(v[0])
    fixes.append(f"{el.get('type')}: read [lon, lat] lists as map coordinates")


INDOORS = ("interior", "palace", "underwater", "space", "paper", "sunburst", "dark", "mine", "classroom", "lab",
           "parliament", "courtroom", "prison")
WEATHER_WORDS = (("blizzard", ("blizzard", "snowstorm", "froze to death", "frozen to death")),
                 ("snow", ("snow", "snowed", "snowing", "winter", "freezing")),
                 ("storm", ("thunderstorm", "thunder", "lightning", "hurricane", "typhoon", "monsoon")),
                 ("rain", ("rain", "rained", "raining", "downpour", "rainy")),
                 ("fog", ("fog", "foggy", "mist", "misty")),
                 ("ash", ("burned down", "burnt down", "burned to the ground", "went up in flames", "set fire to",
                          "in flames", "ablaze", "great fire", "torched", "razed", "reduced to ashes")))


def weather_from_text(text):
    import re
    low = " " + str(text or "").lower() + " "
    for kind, words in WEATHER_WORDS:
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", low):
                return kind
    return None


def repair_weather(sc, bg, mood, text, fixes):
    """Clean "weather" and "light"; add weather the narration talks about (snow in a winter campaign, rain at
    Waterloo) to outdoor places; gentle snowfall in snowy places."""
    w = sc.get("weather")
    if isinstance(w, str):
        w = {"type": w}
    if w is not None and not isinstance(w, dict):
        w = None
    if isinstance(w, dict):
        kind = norm_weather(w.get("type"))
        if not kind:
            if str(w.get("type", "")).lower() not in ("none", "clear", "sunny", ""):
                fixes.append(f"unknown weather {w.get('type')!r} removed")
            w = None
        elif bg["type"] in INDOORS or bg.get("style") == "inside":
            fixes.append(f"no {kind} indoors / on a plain background")
            w = None
        else:
            w = {k: v for k, v in dict(w, type=kind).items() if k in ("type", "amount", "wind", "at", "until")}
            for k, lo, hi in (("amount", 0.2, 2.0), ("wind", -2.0, 2.0)):
                if w.get(k) is not None:
                    w[k] = max(lo, min(_f(w[k], 1.0 if k == "amount" else 0.0), hi))
    elif sc.get("weather") is None and bg["type"] not in INDOORS and bg["type"] != "map" and \
            bg.get("style") != "inside":
        kind = weather_from_text(text)
        if kind == "ash" and bg["type"] not in ("city", "street", "battlefield", "trench", "harbor"):
            kind = None
        if kind == "snow" and bg["type"] in ("desert", "beach", "jungle"):
            kind = None
        if kind:
            w = {"type": kind, "amount": 0.8}
            fixes.append(f"added {kind} because the narration mentions it")
        elif bg["type"] == "snow":
            w = {"type": "snow", "amount": 0.45}
    if w:
        sc["weather"] = w
    else:
        sc.pop("weather", None)
    li = sc.get("light")
    if isinstance(li, str):
        li = {"to": li}
    if isinstance(li, dict):
        to = norm_light(li.get("to"))
        if to:
            li = {k: v for k, v in dict(li, to=to).items() if k in ("to", "at", "dur")}
            if li.get("dur") is not None:
                li["dur"] = max(0.5, min(_f(li["dur"], 3.0), 12.0))
            sc["light"] = li
        else:
            fixes.append(f"unknown light change {li.get('to')!r} removed")
            sc.pop("light", None)
    elif li is not None:
        sc.pop("light", None)


def check_scene(scene, mood="fun", text="", kit=None, cast=None):
    """repair + validate. Returns (scene, fixes, errors)."""
    fixed, fixes = repair_scene(scene, mood, text, kit, cast)
    return fixed, fixes, validate_scene(fixed)


# ------------------------------------------------------------------ places where things happen
# "He built a factory" should look like a construction site filling the screen, not a little factory prop on a
# plain page; "the trial" is a courtroom, "they were thrown in jail" a prison cell. These read the narration.
import re as _re

BUILD_VERBS = r"(?:buil[dt]s?|building|constructs?|constructed|constructing|erects?|erected|put up|puts up|raised)"
NOT_BUILT = ("empire", "reputation", "alliance", "coalition", "career", "fortune", "business", "case", "army",
             "following", "network", "dynasty")
BUILD_THINGS = (("factory", r"factor(?:y|ies)|plants?|mills?|works|foundr(?:y|ies)|steelworks|warehouses?|"
                            r"workshops?|refiner(?:y|ies)"),
                ("ship", r"ships?|fleet|navy|warships?|battleships?|dreadnoughts?|boats?|submarines?|carriers?"),
                ("tower", r"skyscrapers?|towers?|office blocks?|hotels?|apartments?|tower blocks?"),
                ("castle", r"castles?|forts?|fortress(?:es)?|palaces?|cathedrals?|citadels?|strongholds?"),
                ("wall", r"walls?|dams?|great wall"),
                ("house", r"houses?|homes?|cottages?|cabins?|churches|church|schools?|barns?"))
PLACE_WORDS = (  # (bg, extra settings, pattern) - first match wins
    ("prison", {}, r"prisons?|jail(?:ed|s)?|gaol|imprison(?:ed|ment)?|locked (?:him |her |them )?up|behind bars|"
                   r"dungeons?|gulags?|(?:his|her|a|the) cell|thrown in(?:to)? (?:a )?cell|prison camps?|"
                   r"labou?r camps?|prisoners? of war"),
    ("courtroom", {}, r"trials?|put on trial|courtroom|judges?|jury|juries|verdict|sentenced|convicted|acquitted|"
                      r"pleaded guilty|tribunal|lawsuits?|sued"),
    ("parliament", {}, r"parliament|senate|congress|house of commons|lawmakers|mps|senators|legislat\w+|"
                       r"debated|passed (?:a|the) (?:new )?(?:law|bill|act)|duma|reichstag"),
    ("mine", {}, r"(?<!land )(?<!naval )(?<!sea )mines|(?:coal|gold|silver|salt|diamond|copper) mines?|miners|"
                 r"mining|down the mine|dug for (?:gold|coal|silver)|digging for (?:gold|coal|silver)|in the mines?"),
    ("lab", {}, r"laborator(?:y|ies)|labs?|scientists?|experiments?|chemists?|test tubes?|invented|"
                r"discovered (?:a|the) (?:cure|vaccine|element)"),
    ("classroom", {}, r"schools?|classrooms?|teachers?|lessons?|pupils|students|lectures?|professors?|"
                      r"universit(?:y|ies)|homework"),
    ("factory", {"style": "inside"}, r"assembly lines?|production lines?|factory floor|conveyor belts?"),
    ("factory", {}, r"factor(?:y|ies)|industrial revolution|steelworks|textile mills?|cotton mills?|"
                    r"foundr(?:y|ies)|smokestacks?"),
    ("farm", {}, r"farms?|farmers?|farming|harvests?|crops?|peasants?|plough(?:ed)?|plow(?:ed)?|wheat fields?|"
                 r"agricultur\w+|grain|famine"),
    ("market", {}, r"(?<!stock )markets?|marketplace|bazaars?|merchants?|traders? (?:sold|selling)|market stalls?|"
                   r"haggl\w+"),
    ("camp", {}, r"(?<!concentration )(?<!death )(?<!refugee )(?<!extermination )camp(?:ed|s)?|encamp\w*|"
                 r"barracks|bivouac\w*|pitched (?:their )?tents"),
    ("street", {}, r"riots?|rioters|rioting|in the streets|street fighting|barricades|mobs? (?:stormed|marched)"),
    ("battlefield", {}, r"battles?|battlefields?|fought(?! for)|fighting(?! for)|clashed|charged (?:at|into|across|"
                        r"forward|the enemy)|cannons? fired|opened fire|(?<!heart )attack(?:ed|s)?|armies met|"
                        r"the armies|skirmish\w*|bayonets?|volleys?"),
    ("construction", {}, r"construction|building site|under construction|scaffolding|cranes?"),
)
GENERIC_BGS = ("paper", "sunburst", "ground", "field", "hills", "interior")
DIAGRAMS = ("chart", "timeline", "compare", "split", "board", "icons", "territory", "empire", "route", "front",
            "counter", "arrow", "battle", "city")
SAME_AS_PLACE = {"factory": ("construction", "factory"), "barn": ("farm",), "tent": ("camp",)}


def _has(pattern, low):
    return _re.search(r"\b(?:" + pattern + r")\b", low) is not None


def build_what_from_text(text):
    """What the narration says is being built ("built a navy" -> ship); None if it doesn't say."""
    low = " " + str(text or "").lower() + " "
    for what, things in BUILD_THINGS:
        m = _re.search(r"\b" + BUILD_VERBS + r"\b((?:\s+[\w'-]+){0,3}?)\s+(?:" + things + r")\b", low)
        if m and not any(w in m.group(1).split() for w in NOT_BUILT):
            return what
    return None


SENSITIVE_PLACES = r"concentration camps?|death camps?|extermination camps?|holocaust|genocide"


def activity_place(text):
    """The full background the narration's activity happens in, e.g. {"type": "construction", "what": "factory"}
    for "he built a factory"; None when it names no such place (or a place we shouldn't draw as a cartoon)."""
    low = " " + str(text or "").lower() + " "
    if _has(SENSITIVE_PLACES, low):
        return None
    what = build_what_from_text(low)
    if what:
        return {"type": "construction", "what": what}
    for bt, extra, pat in PLACE_WORDS:
        if _has(pat, low):
            return dict({"type": bt}, **extra)
    return None


def upgrade_place(sc, bg, text, fixes):
    """A scene on a plain or generic background whose narration (or main prop) is about a place where something
    happens gets that place as its full background; a prop that the new background already shows big is removed."""
    els = sc.get("elements") or []
    if bg["type"] not in GENERIC_BGS or any(e.get("type") in DIAGRAMS for e in els):
        _drop_duplicate_props(bg, els, fixes)
        return
    place = activity_place(text)
    if place is None:
        return
    if bg["type"] == "field" and place["type"] not in ("battlefield", "farm", "camp", "construction"):
        return                      # an outdoor scene keeps its field unless the action happens outdoors too
    old = bg["type"]
    keep = {k: v for k, v in bg.items() if k in ("time", "items", "clouds")}
    if place["type"] in INDOORS:
        keep.pop("time", None)
    bg.clear()
    bg.update(keep)
    bg.update(place)
    fixes.append(f"bg {old!r} -> {place['type']!r}: the narration happens there")
    _drop_duplicate_props(bg, els, fixes)


def _drop_duplicate_props(bg, els, fixes):
    """A small factory prop in front of a whole factory background is a leftover: remove it."""
    dup = [k for k, e in enumerate(els) if e.get("type") == "prop" and not e.get("do") and
           bg["type"] in SAME_AS_PLACE.get(resolve_prop(e.get("name")) or "", ())]
    for k in reversed(dup):
        fixes.append(f"removed the small {els[k].get('name')!r}: the background shows it")
        els.pop(k)
