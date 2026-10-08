"""The scene composer: a pattern + a few slot values -> a complete scene in the studio's scene language.

The AI (or the retriever, when no AI is used) says WHAT the scene is ("a document is signed, by Madison, the
Constitution, witnessed by Washington"); this module decides HOW it looks: where everyone stands, what is on the
document, when each thing pops in (on the narrator's own words), what the camera does. It only uses things the
engine already draws, so a composed scene is always valid and cheap to render.

compose(pattern_id, beat, analysis, slots, ctx) -> scene dict (or None if the pattern can't be built here).
"""
import random
import re

from ..engine.pen import resolve_kind
from ..engine.registry import PROPS, PROP_ALIASES
from ..engine.schema import cast_member, nearest, BG_TYPES, BG_ALIASES
from ..engine.timing import norm_word
from . import people as PE, propindex as PX, props_intel as PI

W, H = 1920, 1080
FEET = 890
LEFT, MID, RIGHT = 450, 960, 1490
NATION_COLOR = {"america": "#B22234", "britain": "#C8302B", "france": "#2B3F8C", "germany": "#303030", "ussr": "#C8302B",
                "japan": "#FFFFFF", "italy": "#2F8F4F", "china": "#C8302B", "army": "#6B6B3A", "navy": "#1F2A5C"}


class Ctx:
    """What the composer knows about the video so far (the continuity state) and the video's cast."""

    def __init__(self, cast=(), idx=0, state=None, themes=(), title=""):
        self.cast = [c for c in (cast or []) if isinstance(c, dict)]
        self.idx = idx
        self.state = state if state is not None else {}
        self.themes = themes
        self.title = title
        self.rnd = random.Random(idx * 7919 + 13)


class Words:
    """The narration's words, so elements can pop in exactly when the narrator says them."""

    def __init__(self, text):
        self.tokens = [norm_word(t) for t in str(text or "").split()]
        self.raw = str(text or "").split()

    def at(self, *cands, default=None):
        for c in cands:
            k = norm_word(str(c).split()[0] if str(c).split() else "")
            if k and k in self.tokens:
                return "word:" + k
        return default

    def after(self, key, n=1, default=None):
        k = norm_word(key)
        if k in self.tokens:
            i = self.tokens.index(k)
            return self.tokens[min(len(self.tokens) - 1, i + n)] and "word:" + self.tokens[min(len(self.tokens) - 1, i + n)]
        return default


STRICT = False                  # tests set this so a bug in a layout raises instead of quietly using another scene


def off(at, secs):
    """`at` plus `secs` seconds: a word anchor gets '+secs', a fraction moves by secs/6 of the scene."""
    if isinstance(at, str):
        return at + f"+{secs}"
    return min(0.95, float(at) + secs / 6.0)


def slot(s, key, default=None):
    v = (s or {}).get(key)
    return default if v in (None, "", [], {}) else v


def _first_name_token(name):
    parts = [p for p in re.split(r"\s+", str(name or "")) if p]
    return parts[-1] if parts else ""


# ------------------------------------------------------------------ characters
def person(c, who, x, y=FEET, scale=1.0, **kw):
    """A stickman for `who`: a cast member, a known historical person, or a nation/group word ("the French")."""
    who = str(who or "").strip()
    el = {"type": "char", "x": x, "y": y, "scale": scale}
    m = cast_member(c.cast, who) if who else None
    year = kw.pop("year", None) or c.state.get("year")      # the world's year when the beat names none
    if m is not None:
        el["who"] = m.get("name") or who
        el["kind"] = resolve_kind(m.get("kind"))
        for k in ("hat_color", "coat"):
            if m.get(k):
                el[k] = m[k]
        if m.get("look") in ("beard", "mustache"):
            el["extras"] = [m["look"]]
    else:
        e = PE.find(who, year) if who else None
        if e:
            lk = PE.look(e)
            el.update(who=e["name"], kind=resolve_kind(lk["kind"]))
            for k in ("hat_color", "coat"):
                if lk.get(k):
                    el[k] = lk[k]
            if lk.get("look") in ("beard", "mustache"):
                el["extras"] = [lk["look"]]
        else:
            el["kind"] = resolve_kind(who) if who else "civ"
            if who:
                el["who"] = who
    el.update(kw)
    return el


def side(c, who, default="civ"):
    """(kind, coat) for a whole group: 'the French' -> france hat + blue coat."""
    m = cast_member(c.cast, who) if who else None
    if m is not None:
        return resolve_kind(m.get("kind")), m.get("coat") or ""
    k = resolve_kind(who) if who else default
    return (k if k != "civ" else default), ""


def crowd(c, who, x, y, count=14, width=800, scale=0.55, rows=2, **kw):
    kind, coat = side(c, who)
    el = {"type": "crowd", "kind": kind, "count": count, "rows": rows, "x": x, "y": y, "width": width, "scale": scale}
    if who:
        el["who"] = str(who)[:30]                     # who they are, so the review can tell the picture shows them
    if coat:
        el["coat"] = coat
    m = cast_member(c.cast, who) if who else None
    if m and m.get("hat_color"):
        el["hat_color"] = m["hat_color"]
    el.update(kw)
    return el


def text(t, x, y, size=70, color="navy", at=None, font=None, **kw):
    el = {"type": "text", "text": str(t), "x": x, "y": y, "size": size, "color": color}
    if at is not None:
        el["at"] = at
    if font:
        el["font"] = font
    el.update(kw)
    return el


def prop(name, x, y, scale=1.0, at=None, params=None, **kw):
    el = {"type": "prop", "name": name, "x": x, "y": y, "scale": scale}
    if at is not None:
        el["at"] = at
    if params:
        el["params"] = params
    el.update(kw)
    return el


def plate(x, y, w, h, at=None, fill="#FFFFFF", stroke="#2B2B33", **kw):
    """A rounded card behind text so it stays readable on a busy background (a name card, a label)."""
    el = {"type": "shape", "shape": "rect", "x": x, "y": y, "w": w, "h": h, "fill": fill, "stroke": stroke, "width": 6,
          "radius": 26, "enter": "pop"}
    if at is not None:
        el["at"] = at
    el.update(kw)
    return el


def short_role(role):
    """'first US president and Revolutionary War general' -> 'FIRST US PRESIDENT' (fits a name card)."""
    r = str(role or "").strip()
    first = re.split(r",| and | who | of the ", r)[0].strip()
    first = first if len(first) >= 8 else r
    return first.upper()[:30]


def say(t, at=None):
    return {"text": str(t)[:40], **({"at": at} if at else {})}


def prop_in_text(text_, skip=()):
    """A prop the narration names or means ('cannon', 'newspaper', 'troops' -> helmet), or None. A word that is itself a
    prop wins; otherwise the local prop index (studio/knowledge/propindex.py) answers, with the year in the text as a guard."""
    return PX.pick(text_, skip=skip)


# ------------------------------------------------------------------ backgrounds and banners
INDOOR = ("palace", "parliament", "interior", "courtroom", "prison", "classroom", "lab", "mine", "dark")


def bg_for(c, a, s=None, default="interior", time=None, force=None, indoor=False, allow=()):
    """The painted place: the director's choice, else what the narration says, else `default`. `force` pins the place
    for patterns that always happen in one kind of place (an election is on a street); `indoor` keeps the scene in a
    room even when a city is named. The same place as the previous scene keeps the same look (and time of day), so a
    conversation doesn't change rooms between beats."""
    want = str(slot(s, "place", "") or "").lower().replace(" ", "_")
    kind = BG_ALIASES.get(want, want)
    if kind not in BG_TYPES:
        if force:
            kind = force
        else:
            kind = a.get("place_type") or ""
            if not kind:
                cities = [p for p in a.get("places") or [] if p.get("kind") == "city"]
                kind = "city" if (cities and not indoor) else default
            if indoor and kind not in INDOOR and kind not in allow:
                kind = default
    kind = nearest(kind, BG_TYPES, default)
    bg = {"type": kind}
    prev = (c.state or {}).get("bg") or {}
    if prev.get("type") == kind:
        bg = dict(prev)                                    # same room as the last scene
    elif kind in ("field", "hills", "desert", "snow", "city", "battlefield", "street", "harbor", "beach", "jungle",
                  "mountains", "palace"):
        bg["time"] = time or ("dusk" if a.get("mood") in ("somber", "tense") else "day")
    if kind == "city":
        city = next((p for p in a.get("places") or [] if p.get("kind") == "city" and p.get("skyline")), None)
        if city:
            bg["skyline"] = city["skyline"]
    if time and kind not in ("paper", "sunburst", "dark", "interior", "map"):
        bg["time"] = time
    c.state["bg"] = dict(bg)
    return bg


def banner(a, c, s=None, force=False):
    """'Philadelphia, 1787' at the top when the story changes place or year (not on every scene)."""
    place = None
    for p in a.get("places") or []:
        if p.get("kind") == "city":
            place = p["name"]
            break
    if place is None:
        for p in a.get("places") or []:
            place = p["name"]
            break
    year = (a.get("years") or [None])[0]
    label = ", ".join(str(x) for x in (place, year) if x)
    custom = slot(s, "banner")
    if custom:
        label = str(custom)
    key = (place, year)
    if not label or (not force and c.state.get("banner") == key):
        return []
    c.state["banner"] = key
    return [text(label, MID, 105, 76, "navy", at=0.0)]


# ------------------------------------------------------------------ maps
def geo_view(points):
    """(center, width) for a list of (lon, lat), like rules.map_scene does."""
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 1.6)
    width = max(18.0, min(span * 1.9 + 14, 110.0))
    return [round(sum(lons) / len(lons), 1), round(max(-55, min(65, sum(lats) / len(lats))), 1)], round(width, 1)


def _country_point(name):
    from ..engine import geo
    from ..pipeline.rules import ANCHOR_POINTS
    g = geo.countries_geom([name])
    if g is None:
        return None
    p = ANCHOR_POINTS.get(name) or g.representative_point()
    return (p.x, p.y)


def map_elements(c, a, w, s=None, move=False):
    """Territories for the countries named, city markers for the cities, and (for movement) an arrow between the first
    two places with little marching units. Returns (bg, elements) or None when there is nothing to map."""
    pts, els = [], []
    palette = ["#C8302B", "#2B3F8C", "#3C8C4A", "#B07A1F"]
    named = []
    for k, p in enumerate(a.get("places") or []):
        if p.get("kind") == "country":
            pt = _country_point(p["name"])
            if pt:
                named.append((p["name"], pt, "country", None))
        elif p.get("kind") == "city" and p.get("lon") is not None:
            named.append((p["name"], (p["lon"], p["lat"]), "city", p))
    if not named:
        return None
    for k, (name, pt, kind, p) in enumerate(named[:4]):
        pts.append(pt)
        at = w.at(name.split()[0], default=0.05 + 0.1 * k)
        if kind == "country":
            els.append({"type": "territory", "countries": [name], "color": palette[k % 4], "at": at})
            els.append({"type": "text", "text": name.upper()[:16], "lon": round(pt[0], 1), "lat": round(pt[1], 1),
                        "size": 46, "color": "white", "at": at})
        else:
            els.append({"type": "city", "name": name, "lon": round(pt[0], 1), "lat": round(pt[1], 1),
                        "capital": name.lower() in ("paris", "london", "moscow", "berlin", "washington d.c.", "rome", "vienna"),
                        "at": at})
    if move and len(pts) >= 2:
        verb = next((v for v in ("marched", "sailed", "crossed", "advanced", "retreated", "fled", "invaded", "traveled",
                                 "headed", "attacked") if w.at(v)), None)
        who = slot(s, "who") or ((a.get("groups") or [None])[0]) or ((a.get("people") or [{}])[0].get("name"))
        kind, coat = side(c, who, default="army")
        arrow = {"type": "arrow", "from": {"lon": round(pts[0][0], 1), "lat": round(pts[0][1], 1)},
                 "to": {"lon": round(pts[1][0], 1), "lat": round(pts[1][1], 1)}, "color": "red", "curve": -50,
                 "units": slot(s, "units") or (kind if kind != "civ" else "army"), "count": 4,
                 "at": w.at(verb or "", default=0.2)}
        if coat:
            arrow["unit_color"] = coat
        els.append(arrow)
    year = (a.get("years") or [None])[0]
    if year:
        els.append(text(str(year), MID, 105, 84, "white", at=w.at(str(year), default=0.0)))
    center, width = geo_view(pts) if len(pts) > 1 else ([round(pts[0][0], 1), round(pts[0][1], 1)], 30.0)
    return {"type": "map", "style": "dark", "center": center, "width": width}, els


# ------------------------------------------------------------------ the layouts
def L_intro_person(c, a, s, w):
    ppl = a.get("people") or []
    who = slot(s, "who") or (ppl[0]["name"] if ppl else None)
    if not who:
        return None
    year = (a.get("years") or [None])[0]
    e = PE.find(who, year)
    role = short_role(slot(s, "role") or (ppl[0].get("role") if ppl else "") or (e or {}).get("role") or "")
    bg = bg_for(c, a, s, default="palace" if re.search(r"king|queen|emperor|tsar|pharaoh", role.lower()) else "interior", indoor=True)
    nm = (e or {}).get("name") or who
    at_name = w.at(_first_name_token(who), who, default=0.05)
    els = banner(a, c, s) + [
        person(c, who, 640, FEET, 1.25, enter="slide_left", at=at_name, pose="hips" if not e or e["id"] != "napoleon" else "hand_in_coat",
               mouth="smile", year=year,
               **({"say": [say(slot(s, "say"), w.at(_first_name_token(who)) or 0.3)]} if slot(s, "say") else {})),
        plate(1330, 425, 820, 210 if role else 140, at=at_name),
        text(nm.upper()[:26], 1330, 395 if role else 425, 72 if len(nm) < 18 else 56, "navy", at=at_name),
    ]
    if role:
        els.append(text(role, 1330, 480, 46, "red", at=w.after(_first_name_token(who), 1, 0.3), font="hand"))
    sig = PI.signature_prop(role, a.get("text"))
    if sig and sig in PROPS:
        els.append(prop(sig, 1420, 860, 0.85 if sig not in ("flag", "podium") else 1.0, at=w.at(sig, default=0.4)))
    others = [p["name"] for p in ppl if p["name"] != who][:2] + list(slot(s, "with", []) or [])[:2]
    for k, o in enumerate(others[:2]):
        els.append(person(c, o, 1650 + k * 200, FEET, 0.88, flip=True, at=w.at(_first_name_token(o), default=0.5)))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def L_speech(c, a, s, w):
    ppl = a.get("people") or []
    who = slot(s, "who") or (ppl[0]["name"] if ppl else None)
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="field")
    audience = slot(s, "crowd") or (a.get("groups") or [None])[0] or (ppl[1]["name"] if len(ppl) > 1 else None)
    quote = slot(s, "quote")
    sp = person(c, who or "", 520, 860, 1.2, pose="point_right", mouth="open", at=0.0, year=year,
                do=[{"act": "point", "at": w.at("promised", "told", "said", "speech", "declared", default=0.3)}])
    if quote:
        sp["say"] = [say(quote, w.at(*re.findall(r"[A-Za-z]+", quote)[:1], default=0.35))]
    flag_col = NATION_COLOR.get(sp.get("kind"), "#C8302B")
    els = banner(a, c, s) + [prop("podium", 520, 905, 1.0, at=0.0, z=4), sp,
                                prop("flag", 250, 880, 1.0, at=0.1, color=flag_col),
                                crowd(c, audience, 1330, 930, 20, 940, 0.55, rows=3, flip=True, at=w.at("crowd", "people", "cheered", default=0.15),
                                      mouth="open", do=[{"act": "cheer", "at": w.at("cheered", "cheer", "promised", "believe", default=0.55)}])]
    pic = prop_in_text(a.get("text"), skip=("flag", "podium", "crowd"))
    if pic and not ppl[1:2]:
        els.append(prop(pic, 1000, 700, 0.8, at=w.at(pic, default=0.4)))
    focus = [520, 560]
    cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": w.at("promised", "said", "speech", "declared", "told", default=0.3),
                                              "zoom": 1.6, "focus": focus, "move": "cut"},
                     {"at": 0.8, "zoom": 1.0, "move": "pan"}]}
    return {"bg": bg, "elements": els, "camera": cam}


def _doc_el(d, x, y, scale, at, **kw):
    params = {"title": d["title"], "text": d["lines"]}
    if d.get("stamp"):
        params["stamp"] = d["stamp"]
    if d["prop"] == "scroll":
        return prop("scroll", x, y, scale, at=at, params=params, **kw)
    if d["prop"] == "newspaper":
        return prop("newspaper", x, y, scale, at=at, params={"title": "THE DAILY NEWS", "label": d["title"] or "NEWS"}, **kw)
    params["wide"] = len(d["title"]) > 14
    return prop("document", x, y, scale, at=at, params=params, **kw)


def L_document(c, a, s, w):
    d = PI.doc_for(a, s)
    ctx_ = a.get("context") if (a.get("context") or {}).get("kind") == "document" else None
    ppl = [p["name"] for p in a.get("people") or []]
    if ctx_ and not ppl:
        ppl = list(ctx_.get("who") or [])           # the people who really made it ("the Constitution" -> Madison, Washington...)
    signer = slot(s, "signer") or (ppl[0] if ppl else None)
    wit = list(slot(s, "witnesses", []) or []) or ppl[1:3]
    year = (a.get("years") or [None])[0] or (ctx_ or {}).get("year")
    bg = bg_for(c, a, dict(s or {}, place=(s or {}).get("place") or (ctx_ or {}).get("bg") or ""), default="palace", indoor=True)
    at_doc = w.at(*(d["title"].split()[-1:] or ["document"]), "document", "treaty", "constitution", "law", "declaration", default=0.12)
    sign_at = w.at("signed", "signs", "sign", "ratified", "wrote", "drafted", default=0.45)
    where = [text(ctx_["banner"], MID, 105, 70, "navy", at=0.0)] if (ctx_ and ctx_.get("banner")) else banner(a, c, s)
    els = where + [
        _doc_el(d, MID, 450, 2.5 if d["prop"] == "document" else 2.3, at_doc, enter="grow"),
        prop("quill", 1250, 780, 0.95, at=sign_at, idle="bob"),
        prop("check", 1150, 330, 1.0, at=off(sign_at, 0.5)),
    ]
    if ctx_ and ctx_.get("group"):                  # the room full of the people who made it
        els.append(crowd(c, ctx_["group"].title(), 1130, 930, 8, 520, 0.46, rows=1, at=0.18, kind="tricorn", coat="#3A3A4A"))
    if signer:
        els.append(person(c, signer, 390, FEET, 1.1, pose="point_right", year=year, at=0.02,
                          do=[{"act": "lean", "amount": 18, "at": sign_at, "dur": 1.4}]))
    for k, n in enumerate(wit[:3]):
        els.append(person(c, n, 1560 + k * 190, FEET, 0.85 - 0.05 * k, flip=True, year=year, at=w.at(_first_name_token(n), default=0.2 + 0.1 * k),
                          do=[{"act": "cheer" if a.get("emotion") != "tension" else "surprise", "at": off(sign_at, 0.8)}]))
    cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": sign_at, "zoom": 1.6, "focus": [MID, 610], "move": "cut"},
                     {"at": 0.85, "zoom": 1.0, "move": "pan"}]}
    return {"bg": bg, "elements": els, "camera": cam}


def L_treaty(c, a, s, w):
    d = PI.doc_for(a, s, want="treaty")
    ppl = [p["name"] for p in a.get("people") or []]
    groups = list(a.get("groups") or [])
    A = slot(s, "side_a") or (groups[0] if groups else (ppl[0] if ppl else None))
    B = slot(s, "side_b") or (groups[1] if len(groups) > 1 else (ppl[1] if len(ppl) > 1 else None))
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="palace", indoor=True)
    sign_at = w.at("signed", "signs", "agreed", "surrendered", "peace", "treaty", default=0.4)
    els = banner(a, c, s) + [
        person(c, A or "", 470, FEET, 1.15, pose="shrug" if a.get("emotion") == "tragedy" else "hips", mouth="frown" if a.get("emotion") == "tragedy" else "smile",
               year=year, at=0.02),
        person(c, B or "", 1450, FEET, 1.15, flip=True, pose="hips", year=year, mouth="smirk", at=0.06),
        _doc_el(d, MID, 560, 2.0 if d["prop"] == "scroll" else 2.2, w.at("treaty", "peace", "armistice", "terms", default=0.12), enter="grow"),
    ]
    if slot(s, "dove", True) and a.get("emotion") != "tragedy":
        els.append(prop("dove", MID, 215, 0.8, at=w.at("peace", "agreed", default=0.5), idle="float"))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def L_chamber(c, a, s, w):
    d = PI.doc_for(a, s, want="law")
    ppl = [p["name"] for p in a.get("people") or []]
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="parliament", force="parliament")
    spk = slot(s, "speaker") or (ppl[0] if ppl else None)
    vote_at = w.at("voted", "vote", "passed", "approved", "ratified", default=0.55)
    els = banner(a, c, s)
    els.append(crowd(c, slot(s, "left_side") or "civ", 520, 925, 8, 640, 0.52, rows=2, at=0.05, mouth="open"))
    els.append(crowd(c, slot(s, "right_side") or "civ", 1400, 925, 8, 640, 0.52, rows=2, flip=True, at=0.08, mouth="frown"))
    if spk:
        els.append(person(c, spk, MID, FEET, 1.05, pose="point_right", year=year, at=0.02, mouth="open"))
    els.append(_doc_el(d, 1600, 400, 1.6, w.at("law", "act", "bill", "constitution", "amendment", default=0.2), enter="grow"))
    yes, no = slot(s, "yes"), slot(s, "no")
    try:
        yes_n, no_n = int(float(str(yes).replace(",", ""))) if yes is not None else None, int(float(str(no).replace(",", ""))) if no is not None else None
    except ValueError:
        yes_n = no_n = None
    if yes_n is not None and no_n is not None:
        els.append({"type": "counter", "from": 0, "to": yes_n, "x": 480, "y": 250, "size": 70, "prefix": "YES ", "color": "green", "at": vote_at, "dur": 1.4, "format": "number"})
        els.append({"type": "counter", "from": 0, "to": no_n, "x": 1000, "y": 250, "size": 70, "prefix": "NO ", "color": "red", "at": vote_at, "dur": 1.4, "format": "number"})
    else:
        els.append(prop("check", 1700, 300, 1.0, at=vote_at))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_debate(c, a, s, w):
    ppl = [p["name"] for p in a.get("people") or []] + list(a.get("groups") or [])
    L = slot(s, "left") or (ppl[0] if ppl else "")
    R = slot(s, "right") or (ppl[1] if len(ppl) > 1 else "")
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="parliament", indoor=True)
    l_line, r_line = slot(s, "left_line"), slot(s, "right_line")
    issue = slot(s, "issue") or prop_in_text(a.get("text"), skip=("crowd",)) or "document"
    issue = issue if issue in PROPS else "document"
    left = person(c, L, 560, FEET, 1.15, pose="point_right", mouth="open", year=year, at=0.02)
    right = person(c, R, 1360, FEET, 1.15, flip=True, pose="angry_fists", mouth="frown", eyes="angry", year=year, at=0.05)
    if l_line:
        left["say"] = [say(l_line, w.at("argued", "wanted", "said", "demanded", default=0.2))]
    if r_line:
        right["say"] = [say(r_line, w.at("but", "while", "opposed", "refused", "hated", default=0.55))]
    right["do"] = [{"act": "angry", "at": 0.6}]
    els = banner(a, c, s) + [left, right, prop(issue, MID, 600, 1.2 if issue != "document" else 1.4, at=w.at(issue, default=0.3), idle="bob")]
    cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": 0.2, "zoom": 1.5, "focus": [560, 600], "move": "cut"},
                     {"at": 0.55, "zoom": 1.5, "focus": [1360, 600], "move": "whip"}, {"at": 0.85, "zoom": 1.0, "move": "pan"}]}
    return {"bg": bg, "elements": els, "camera": cam}


def L_election(c, a, s, w):
    ppl = [p["name"] for p in a.get("people") or []]
    cands = list(slot(s, "candidates", []) or []) or ppl[:2]
    winner = slot(s, "winner") or (cands[0] if cands else None)
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="street", force="street")
    els = banner(a, c, s) + [prop("ballot", 760, 890, 1.2, at=w.at("ballot", "vote", "election", default=0.1)),
                             crowd(c, "civ", 330, 925, 6, 520, 0.55, rows=1, at=0.08, do=[{"act": "walk", "to": [650, 925], "at": 0.1}])]
    for k, n in enumerate(cands[:2]):
        win = n == winner
        els.append(person(c, n, 1340 + k * 330, FEET, 1.05 if win else 0.95, year=year, flip=bool(k), at=w.at(_first_name_token(n), default=0.2 + 0.1 * k),
                          pose="cheer" if win else "down", mouth="grin" if win else "frown",
                          do=[{"act": "celebrate" if win else "cry", "at": w.at("won", "elected", "landslide", "victory", default=0.65)}]))
    nums = a.get("numbers") or []
    if nums and nums[0]["kind"] in ("percent", "count"):
        n0 = nums[0]
        els.append({"type": "counter", "from": 0, "to": round(n0["value"] if n0["kind"] == "count" else float(n0["shown"].rstrip("%").replace(",", ""))), "x": MID, "y": 240,
                    "size": 110, "suffix": "%" if n0["kind"] == "percent" else " votes", "format": "number", "at": w.at(n0["text"].split()[0].replace(",", ""), default=0.4), "dur": 1.5})
    else:
        els.append(prop("trophy", 960, 470, 0.9, at=w.at("won", "elected", "victory", "landslide", default=0.65), enter="pop"))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_war_declaration(c, a, s, w):
    maps = map_elements(c, a, w, s, move=True)
    year = (a.get("years") or [None])[0]
    ppl = [p["name"] for p in a.get("people") or []]
    msg = str(slot(s, "message") or "WAR!").upper()[:20]
    if maps and len([p for p in a.get("places") or []]) >= 2:
        bg, els = maps
        els.append(text(msg, MID, 255, 100, "red", at=w.at("declared", "war", "ultimatum", default=0.1)))
        return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}
    bg = bg_for(c, a, s, default="palace", indoor=True)
    leader = slot(s, "aggressor") or (ppl[0] if ppl else (a.get("groups") or [""])[0])
    tgt = slot(s, "target") or (a.get("groups") or [None, None])[1:2] or [None]
    tgt = tgt[0] if isinstance(tgt, list) else tgt
    els = banner(a, c, s) + [
        person(c, leader, 520, FEET, 1.2, pose="point_right", mouth="open", year=year, at=0.02, do=[{"act": "point", "at": w.at("declared", "war", default=0.2)}]),
        prop("envelope", 1200, 520, 1.7, at=w.at("declared", "telegram", "ultimatum", default=0.15), enter="drop"),
        text(msg, 1200, 330, 96, "red", at=w.at("declared", "war", "ultimatum", default=0.25)),
        crowd(c, tgt or "civ", 1500, 930, 8, 560, 0.55, rows=2, flip=True, at=0.3, mouth="o", do=[{"act": "surprise", "at": w.at("declared", "war", default=0.35)}]),
    ]
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def _army(c, who, x, count, flip, scale=0.55, at=0.05, **kw):
    return crowd(c, who, x, 915, count, 720, scale, rows=3, flip=flip, at=at, **kw)


def L_battle_wide(c, a, s, w):
    groups = list(a.get("groups") or []) + [p["name"] for p in a.get("people") or []]
    A = slot(s, "side_a") or (groups[0] if groups else "")
    B = slot(s, "side_b") or (groups[1] if len(groups) > 1 else "")
    style = slot(s, "place", "") if slot(s, "place", "") in ("river", "open", "ruins") else None
    year = (a.get("years") or [None])[0]
    bg = {"type": "battlefield", "style": style or c.rnd.choice(["river", "open"]), "time": "dawn"}
    c.state["bg"] = dict(bg)
    ppl = [p["name"] for p in a.get("people") or []]
    battle = slot(s, "battle") or next((p["name"] for p in a.get("places") or [] if p.get("kind") == "city"), "")
    label = (f"{battle}, {year}" if battle and year else battle or (str(year) if year else ""))
    els = ([text(label.upper(), MID, 110, 80, "white", at=0.0, stroke=6)] if label else []) + [
        _army(c, A, 520, 15, False), _army(c, B, 1400, 15, True, at=0.08),
        person(c, ppl[0] if ppl else A, 250, 880, 1.0, pose="point_right", year=year, at=0.1),
        person(c, ppl[1] if len(ppl) > 1 else B, 1700, 880, 1.0, flip=True, pose="point_left", year=year, at=0.12),
    ]
    nums = [n for n in a.get("numbers") or [] if n["kind"] in ("count", "casualty")]
    for k, n in enumerate(nums[:2]):
        els.append({"type": "counter", "from": 0, "to": int(n["value"]), "x": 520 + k * 880, "y": 330, "size": 70, "format": "number",
                    "color": "white", "at": w.at(n["text"].split()[0].replace(",", ""), default=0.3 + 0.1 * k), "dur": 1.4})
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.07]}}


def L_battle_clash(c, a, s, w):
    groups = list(a.get("groups") or []) + [p["name"] for p in a.get("people") or []]
    A = slot(s, "side_a") or (groups[0] if groups else "")
    B = slot(s, "side_b") or (groups[1] if len(groups) > 1 else "")
    year = (a.get("years") or [None])[0]
    style = slot(s, "place", "") if slot(s, "place", "") in ("river", "open", "ruins") else None
    bg = {"type": "battlefield", "style": style or ("ruins" if year and year > 1900 else "open"), "time": "dusk" if a.get("mood") == "somber" else "day"}
    c.state["bg"] = dict(bg)
    hit = w.at("charged", "attacked", "clashed", "bombed", "stormed", "fired", "shelled", "fought", "exploded", "cannon", default=0.35)
    weapon = slot(s, "weapon") or PI.weapon_for_year(year)
    until = off(hit, 1.0)
    els = [crowd(c, A, 560, 915, 12, 640, 0.55, rows=3, at=0.05, do=[{"act": "run", "at": hit, "dur": 1.2}],
                 move={"dx": 330, "dy": 0, "from": hit, "to": until}),
           crowd(c, B, 1360, 915, 12, 640, 0.55, rows=3, flip=True, at=0.06, do=[{"act": "run", "at": hit, "dur": 1.2}],
                 move={"dx": -330, "dy": 0, "from": hit, "to": until}),
           prop("explosion", MID, 600, 1.3, at=hit, enter="pop"),
           prop("smoke", 1250, 840, 1.3, at=hit)]
    if weapon in PROPS and weapon not in ("sword", "pointer"):
        els.append(prop(weapon, 300, 900, 0.9, at=0.1))
    cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": hit, "zoom": 1.5, "focus": [MID, 640], "move": "cut"}, {"at": 0.85, "zoom": 1.0, "move": "pan"}]}
    return {"bg": bg, "elements": els + banner(a, c, s), "camera": cam}


def _geo_words(name):
    from ..engine import geo
    return [k for k, v in geo.ALIASES.items() if v == name or (isinstance(v, list) and name in v)]


def L_map_story(c, a, s, w):
    """A map that tells the sentence: the region the story is about highlighted (the 13 colonies on the Atlantic coast),
    where the people came from (England) with a ship crossing to it, and the camera closing in on the region."""
    m = a.get("map")
    if not m:
        return None
    bg = {"type": "map", "style": "dark", "center": m["center"], "width": m["width"]}
    key = w.at("colonies", "colony", "colonial", "coast", "territory", "stretched", default=0.3)
    els = []
    o = m.get("origin")
    if o:
        at_o = w.at(*(_geo_words(o["name"])[:3] or [o["name"].split()[0]]), default=0.05)
        els.append({"type": "territory", "countries": [o["name"]], "color": "#C8302B", "at": at_o})
        label = (_geo_words(o["name"])[:1] or [o["name"]])[0].upper()
        els.append({"type": "text", "text": label[:14], "lon": o["lon"], "lat": o["lat"] - 1.5, "size": 40, "color": "white", "at": at_o})
    if m.get("territory"):
        els.append({"type": "territory", "region": m["territory"], "color": "#3C8C4A", "at": key})
    if m.get("label"):
        lon, lat = m.get("label_at") or m["center"]
        els.append({"type": "text", "text": m["label"], "lon": lon, "lat": lat, "size": 38, "color": "white", "at": key})
    names = {r.get("id") for r in a.get("regions") or []}
    if "atlantic_coast" in names:
        sea = [-56, 37]
        if o and m.get("label_at"):                 # between England and the colonies, not on top of the colonies' label
            sea = [round((o["lon"] + m["label_at"][0]) / 2, 1), round((o["lat"] + m["label_at"][1]) / 2 + 2.5, 1)]
        els.append({"type": "text", "text": "ATLANTIC OCEAN", "lon": sea[0], "lat": sea[1], "size": 40, "color": "#9DB4D8", "at": w.at("atlantic", default=0.15)})
        els.append({"type": "text", "text": "ATLANTIC COAST", "lon": -70.5, "lat": 32.5, "size": 34, "color": "white", "at": w.at("coast", "atlantic", default=0.3)})
    if o and m.get("territory") and m.get("ship"):
        tgt = m.get("label_at") or m["center"]
        els.append({"type": "arrow", "from": {"lon": o["lon"], "lat": o["lat"]}, "to": {"lon": tgt[0] + 7.5, "lat": tgt[1] + 1.5},
                    "color": "red", "curve": -40, "units": "ship", "count": 3, "at": w.at("established", "founded", "settled", "sailed", default=0.2)})
    year = (a.get("years") or [None])[0]
    if year:
        els.append(text(str(year), MID, 105, 84, "white", at=w.at(str(year), default=0.0)))
    cam = {"zoom": [1.0, 1.05]}
    if o and m.get("territory") and m.get("ship"):
        cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": 0.55, "zoom": 1.5, "region": m["territory"], "move": "pan"}]}
    return {"bg": bg, "elements": els, "camera": cam}


def L_event_scene(c, a, s, w):
    """A famous event as a tableau: its real place and date, the people and the things that were there."""
    e = a.get("context")
    if not e or e.get("kind") != "event":
        return None
    bg = dict(e.get("bg") or {"type": "field"})
    c.state["bg"] = dict(bg)
    first = (re.findall(r"[A-Za-z]{4,}", e.get("label", "")) or ["event"])[0]
    lab_x = MID + 290 if e.get("people") else MID           # a speaker stands under the middle: keep the bubble's tail clear of the label
    els = [text(e["banner"], MID, 105, 70, "navy", at=0.0), text(e["label"], lab_x, 225, 62, "red", at=w.at(first, default=0.1), enter="pop")]
    for k, cr in enumerate(e.get("crowds") or []):
        els.append(crowd(c, cr["who"], cr["x"], 930, cr.get("count", 10), cr.get("width", 600), 0.55, rows=2,
                         at=0.05 + 0.08 * k, flip=bool(cr.get("flip")), kind=cr.get("kind", "civ"), coat=cr.get("coat", "#555555")))
    for k, who in enumerate(e.get("people") or []):             # a name, or {"name", "x"} when the spot matters
        name, px = (who["name"], who.get("x", 560 + 330 * k)) if isinstance(who, dict) else (who, 560 + 330 * k)
        els.append(person(c, name, px, FEET, 1.15, at=0.04, year=e.get("year"), pose="point_right" if k == 0 else "hips"))
    for k, pr in enumerate(e.get("props") or []):
        if pr["name"] in PROPS:
            els.append(prop(pr["name"], pr["x"], pr["y"], pr.get("scale", 1.0), at=w.at(pr["name"], default=0.12 + 0.1 * k), enter="grow"))
    n = next(iter(a.get("numbers") or []), None)
    if n:                                           # a figure the narrator gives ("342 chests of tea") is shown too
        els.append(text(str(n.get("shown") or n.get("value"))[:18], 1250, 390, 70, "red", at=w.at(str(n.get("shown") or "").split(" ")[0], default=0.3), enter="pop"))
    say_ = slot(s, "say")
    if say_ and any(el.get("type") == "char" for el in els):
        next(el for el in els if el.get("type") == "char")["say"] = [say(str(say_)[:36], 0.3)]
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def L_map_region(c, a, s, w):
    if a.get("map"):
        return L_map_story(c, a, s, w)
    m = map_elements(c, a, w, s, move=False)
    if not m:
        return None
    bg, els = m
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_map_move(c, a, s, w):
    if a.get("map"):
        return L_map_story(c, a, s, w)
    m = map_elements(c, a, w, s, move=True)
    if not m:
        return None
    bg, els = m
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def L_country_est(c, a, s, w):
    if a.get("map"):
        return L_map_story(c, a, s, w)
    m = map_elements(c, a, w, s, move=False)
    if not m:
        return None
    bg, els = m
    country = next((p["name"] for p in a.get("places") or [] if p.get("kind") == "country"), "")
    bg["width"] = min(bg.get("width", 40), 40.0)
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_city_est(c, a, s, w):
    cities = [p for p in a.get("places") or [] if p.get("kind") == "city"]
    if not cities and not slot(s, "city"):
        return None
    bg = bg_for(c, a, dict(s or {}, place=(s or {}).get("place") or ("city" if cities and cities[0].get("skyline") else "street")), default="city")
    name = slot(s, "city") or cities[0]["name"]
    year = (a.get("years") or [None])[0]
    label = f"{name}, {year}" if year else name
    c.state["banner"] = (name, year)
    ppl = [p["name"] for p in a.get("people") or []]
    els = [text(label, MID, 120, 92, "navy", at=0.0, stroke=6)]
    walkers = ppl[:2] or ["", ""]
    for k, n in enumerate(walkers):
        els.append(person(c, n, 500 + k * 380, FEET, 0.75, at=0.1 + 0.05 * k, do=[{"act": "walk", "to": [700 + k * 400, FEET], "at": 0.1}]))
    pic = slot(s, "detail") or prop_in_text(a.get("text"), skip=("crowd",))
    if pic in PROPS:
        els.append(prop(pic, 1500, 880, 0.9, at=w.at(pic, default=0.4)))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def L_crowd(c, a, s, w, protest=False, riot=False):
    who = slot(s, "crowd") or (a.get("groups") or [None])[0] or ((a.get("people") or [{}])[0].get("name") if a.get("people") else None)
    bg = bg_for(c, a, s, default="street", time="dusk" if riot else None, force="street")
    react = str(slot(s, "reaction", "cheer")).lower()
    act = {"cheer": "cheer", "boo": "angry", "gasp": "surprise", "panic": "tremble", "silence": "look"}.get(react, "cheer")
    key = w.at("cheered", "booed", "gasped", "panicked", "celebrated", "roared", "rioted", "stormed", "burned", "demanded", "protested", default=0.4)
    els = banner(a, c, s)
    mouth = "scream" if riot else "open"
    eyes = "angry" if (riot or protest or react == "boo") else "wide"
    els.append(crowd(c, who, 880, 930, 26 if (protest or riot) else 22, 1400, 0.6, rows=3, at=0.05, mouth=mouth, eyes=eyes,
                     **({"prop": "torch"} if riot else {}), do=[{"act": "angry" if (protest or riot) else act, "at": key}]))
    line = slot(s, "line")
    shout = person(c, "", 520, FEET, 1.05, at=0.1, mouth="open", eyes="angry" if protest or riot else "wide", pose="up")
    if line:
        shout["say"] = [say(line, key)]
    els.append(shout)
    cause = slot(s, "cause") or prop_in_text(a.get("text"), skip=("crowd", "flag"))
    if protest:
        slog = PI.slogan_for(a, s)
        els += [{"type": "sign", "text": slog, "x": 900, "y": 640, "size": 48, "at": w.at("demanded", "protest", "protested", "strike", default=0.2)},
                {"type": "sign", "text": "ENOUGH!", "x": 1250, "y": 700, "size": 44, "at": 0.35},
                prop("megaphone", 650, 780, 0.8, at=0.15),
                crowd(c, slot(s, "against") or "army", 1700, 925, 5, 300, 0.6, rows=1, flip=True, at=0.2, mouth="flat")]
    elif riot:
        target = slot(s, "target") if slot(s, "target") in PROPS else (cause if cause in ("castle", "palace", "house", "factory", "fort", "church", "cathedral", "barn") else "castle")
        els += [prop(target, 1560, 880, 1.2, at=0.1), prop("fire", 1560, 880, 1.6, at=key), prop("smoke", 1400, 820, 1.4, at=key),
                crowd(c, slot(s, "against") or "army", 1800, 925, 4, 240, 0.6, rows=1, flip=True, at=0.2, mouth="o")]
    elif cause in PROPS:
        els.append(prop(cause, 1560, 820, 0.9, at=w.at(cause, default=0.2)))
    cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": key, "zoom": 1.4, "focus": [880, 640], "move": "pan"}, {"at": 0.85, "zoom": 1.0, "move": "pan"}]}
    return {"bg": bg, "elements": els, "camera": cam}


def L_protest(c, a, s, w):
    return L_crowd(c, a, s, w, protest=True)


def L_riot(c, a, s, w):
    return L_crowd(c, a, s, w, riot=True)


def L_stat(c, a, s, w):
    nums = a.get("numbers") or []
    if not nums:
        return None
    n0 = nums[0]
    dark = a.get("mood") in ("somber", "tense") or n0["kind"] == "casualty"
    bg = {"type": "dark"} if dark else {"type": "sunburst", "color": "#FFE7A8", "ray": "#FFD36B"}
    c.state["bg"] = dict(bg)
    v = n0["value"]
    big = v >= 1e6
    shown = v / (1e9 if v >= 1e9 else 1e6) if big else v
    prefix = {"dollars": "$", "pounds": "£", "euros": "€"}.get(n0.get("unit"), "$" if n0["kind"] == "money" else "")
    if n0["kind"] == "percent":
        shown, prefix = float(n0["shown"].rstrip("%").replace(",", "")), ""
    key = w.at(n0["text"].split()[0].replace(",", ""), "million", "billion", "thousand", "percent", default=0.2)
    col = "white" if dark else "navy"
    unit_label = ""
    if n0["kind"] in ("casualty", "count") and n0.get("unit"):
        unit_label = n0["unit"].upper() + (" KILLED" if re.search(r"kill|die|dead|death", str(a.get("text") or "").lower()) else "")
    elif n0["kind"] == "casualty":
        unit_label = "DEAD"
    elif n0["kind"] == "count" and n0.get("unit") == "":
        unit_label = ""
    suffix = (" billion" if v >= 1e9 else " million" if big else "")
    if n0["kind"] == "percent":
        suffix = "%"
    els = [{"type": "counter", "from": 0, "to": round(shown, 1) if (big or n0["kind"] == "percent") else round(shown), "x": MID, "y": 385, "size": 150,
            "prefix": prefix, "suffix": suffix, "format": "number", "decimals": 1 if (big and shown != int(shown)) else 0,
            "at": key, "dur": 1.8, "color": col}]
    if unit_label:
        els.append(text(unit_label[:26], MID, 565, 62, "red" if n0["kind"] == "casualty" else col, at=w.at(n0["text"].split()[0].replace(",", ""), default=0.3) if False else key))
    if len(nums) > 1 and nums[1]["kind"] == n0["kind"]:
        n1 = nums[1]
        els.append({"type": "compare", "items": [{"label": n0["text"][:12], "value": n0["value"]}, {"label": n1["text"][:12], "value": n1["value"]}],
                    "x": MID, "y": 640, "size": 40, "at": 0.55})
    elif n0["kind"] == "casualty":
        els.append({"type": "icons", "icon": "gravestone", "count": 24, "per_row": 12, "x": MID, "y": 760, "scale": 0.35, "at": 0.4})
    elif n0["kind"] in ("count",) and v >= 1000:
        els.append({"type": "icons", "icon": "helmet", "count": 20, "per_row": 10, "x": MID, "y": 760, "scale": 0.4, "at": 0.4})
    ppl = a.get("people") or []
    els.append(person(c, ppl[0]["name"] if ppl else "", 1650, FEET, 0.75, flip=True, at=0.5, pose="shrug", mouth="o", eyes="wide",
                      do=[{"act": "surprise", "at": min(0.9, 0.5)}]))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_timeline(c, a, s, w):
    evs = slot(s, "events")
    ys = list(dict.fromkeys(a.get("years") or []))
    if not evs and len(ys) < 2:
        return None
    if not evs:
        evs = [{"year": y, "label": ""} for y in ys[:6]]
    out = []
    for e in evs[:6]:
        try:
            yv = int(e.get("year"))
        except (TypeError, ValueError):
            continue
        out.append({"year": yv, "label": str(e.get("label") or "")[:18], "at": w.at(str(yv), default=min(0.9, 0.1 + 0.15 * len(out)))})
    if len(out) < 2:
        return None
    bg = {"type": "paper"}
    c.state["bg"] = dict(bg)
    return {"bg": bg, "elements": [{"type": "timeline", "events": out, "y": 540, "color": "navy"}], "camera": {"zoom": [1.0, 1.04]}}


def _arrow(x0, x1, y, at, color="#E0453A"):
    return {"type": "shape", "shape": "poly", "points": [[x0, y - 28], [x1 - 70, y - 28], [x1 - 70, y - 70], [x1, y], [x1 - 70, y + 70], [x1 - 70, y + 28], [x0, y + 28]],
            "fill": color, "stroke": "#7A1E18", "width": 6, "at": at, "enter": "wipe_right"}


def L_cause_effect(c, a, s, w):
    bg = {"type": "sunburst", "color": "#DDF0FF", "ray": "#B8E0FF"} if a.get("mood") != "somber" else {"type": "dark"}
    c.state["bg"] = dict(bg)
    ppl = a.get("people") or []
    cause = slot(s, "cause") if slot(s, "cause") in PROPS else (prop_in_text(a.get("text")) or "moneybag")
    effect = slot(s, "effect") if slot(s, "effect") in PROPS else (next((p for p in ("explosion", "fire", "crowd", "xmark", "trophy") if p in str(a.get("text") or "").lower()), None) or "explosion")
    key = w.at("because", "caused", "led", "so", "result", "meant", "sparked", "triggered", default=0.4)
    els = [prop(cause, 520, 820, 1.2, at=0.05, enter="pop"), text(str(slot(s, "cause_label") or cause).replace("_", " ").upper()[:16], 520, 300, 54, "navy", at=0.1),
           _arrow(780, 1140, 560, key), text(str(slot(s, "link") or "SO...")[:10].upper(), 960, 430, 52, "red", at=key),
           prop(effect, 1450, 820 if effect not in ("explosion", "fire") else 640, 1.5, at=w.at("then", "boom", "war", "angry", default=0.65), enter="pop"),
           text(str(slot(s, "effect_label") or effect).replace("_", " ").upper()[:16], 1450, 300, 54, "red", at=0.7)]
    if ppl:
        els.append(person(c, ppl[0]["name"], 1750, FEET, 0.6, flip=True, at=0.7, do=[{"act": "surprise", "at": 0.72}]))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_before_after(c, a, s, w):
    ys = a.get("years") or []
    left = str(slot(s, "left") or (ys[0] if ys else "BEFORE")).upper()[:12]
    right = str(slot(s, "right") or (ys[1] if len(ys) > 1 else "AFTER")).upper()[:12]
    ppl = a.get("people") or []
    who = ppl[0]["name"] if ppl else ""
    pic = prop_in_text(a.get("text"), skip=("crowd",)) or "house"
    els = [{"type": "split", "left": left, "right": right, "tint": "none", "at": 0.0},
           person(c, who, 480, FEET, 1.0, pose="down", mouth="frown", eyes="sad", at=0.05),
           prop(pic, 760, 860, 0.8, at=0.1),
           person(c, who, 1440, FEET, 1.0, flip=True, pose="cheer", mouth="grin", eyes="happy", at=w.at("now", "after", "today", "then", default=0.55)),
           prop(pic, 1700, 860, 1.2, at=w.at("now", "after", "today", "then", default=0.55))]
    return {"bg": {"type": "paper"}, "elements": els, "camera": {"zoom": [1.0, 1.04]}}


def L_economic(c, a, s, w):
    bg = bg_for(c, a, s, default="street", time="dusk", force="street")
    key = w.at("crashed", "doubled", "tripled", "collapsed", "soared", "fell", "plunged", "skyrocketed", "prices", "inflation", default=0.3)
    falling = bool(re.search(r"crash|fell|plunge|collapse|lost|drop|bankrupt|depress", str(a.get("text") or "").lower()))
    pts = [[0, 0.85], [0.35, 0.8], [0.6, 0.4], [1, 0.05]] if falling else [[0, 0.1], [0.4, 0.2], [0.7, 0.55], [1, 0.95]]
    ppl = a.get("people") or []
    sufferer = person(c, ppl[0]["name"] if ppl else "", 520, FEET, 1.1, pose="shrug", mouth="o", eyes="worried", extras=["sweat"], at=0.05,
                      do=[{"act": "cry" if falling else "surprise", "at": key}])
    if slot(s, "line"):
        sufferer["say"] = [say(slot(s, "line"), key)]
    els = banner(a, c, s) + [prop("line_chart", 1300, 700, 1.4, at=key, params={"points": pts}), sufferer,
                             prop("moneybag", 780, 880, 0.9, at=0.1)]
    nums = a.get("numbers") or []
    if nums:
        els.append(text(nums[0]["shown"], 1300, 250, 100, "red", at=w.at(nums[0]["text"].split()[0].replace(",", ""), default=0.35)))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_invention(c, a, s, w):
    ppl = a.get("people") or []
    who = slot(s, "who") or (ppl[0]["name"] if ppl else "")
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="interior", indoor=True, allow=("factory", "construction", "farm"))
    thing = slot(s, "thing") if slot(s, "thing") in PROPS else (prop_in_text(a.get("text"), skip=("crowd", "lightbulb")) or "gear")
    idea = w.at("invented", "idea", "discovered", "inventor", "patent", "built", default=0.2)
    els = banner(a, c, s) + [
        person(c, who, 500, FEET, 1.15, year=year, pose="think", at=0.02, do=[{"act": "think", "at": idea}]),
        prop("lightbulb", 500, 380, 1.0, at=idea, enter="pop"),
        prop(thing, 1250, 860, 1.5 if thing not in ("gear", "lightbulb") else 1.8, at=w.at(thing, "machine", "engine", default=0.45), enter="grow"),
        text(thing.replace("_", " ").upper()[:20] + (f" {year}" if year else ""), 1250, 250, 60, "navy", at=w.at(thing, default=0.5)),
    ]
    for k, o in enumerate([p["name"] for p in ppl[1:3]]):
        els.append(person(c, o, 1700 + 120 * k, FEET, 0.85, flip=True, at=0.6, do=[{"act": "surprise", "at": 0.65}]))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


def L_death(c, a, s, w):
    ppl = a.get("people") or []
    who = slot(s, "who") or (ppl[0]["name"] if ppl else "")
    year = (a.get("years") or [None])[0]
    e = PE.find(who, year)
    bg = {"type": "dark"} if a.get("mood") == "somber" else bg_for(c, a, s, default="interior", time="dusk")
    c.state["bg"] = dict(bg)
    verb = w.at("died", "killed", "shot", "assassinated", "executed", "poisoned", "murdered", "death", default=0.35)
    els = [person(c, who, 640, FEET, 1.2, year=year, at=0.02, pose="down", mouth="flat", eyes="sad", do=[{"act": "faint", "at": verb}])]
    for k, n in enumerate([p["name"] for p in ppl[1:3]] or [""]):
        els.append(person(c, n, 1300 + k * 240, FEET, 0.9, flip=True, at=0.5 + 0.05 * k, mouth="frown", eyes="sad", extras=["tear"]))
    els += [prop("gravestone", 1560, 880, 1.2, at=w.at("buried", "funeral", "grave", default=0.7), params={"label": "RIP"}),
            prop("candle", 380, 880, 1.0, at=0.5), prop("candle", 480, 880, 1.0, at=0.55)]
    life = f"{e['born']} - {e['died']}" if e else ""
    if life:
        els.append(text(life, 1560, 640, 44, "white", at=w.at("buried", "funeral", "grave", default=0.7), font="hand"))
    if year:
        els.append(text(str(year), MID, 120, 80, "white", at=0.0))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.08]}, "transition": "fade"}


def L_migration(c, a, s, w):
    maps = map_elements(c, a, w, s, move=True) if len([p for p in a.get("places") or []]) >= 2 else None
    if maps:
        bg, els = maps
        return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}
    who = slot(s, "who") or (a.get("groups") or [None])[0]
    bg = bg_for(c, a, s, default="harbor" if re.search(r"sail|ship|boat|ocean|sea", str(a.get("text") or "").lower()) else "field")
    key = w.at("sailed", "fled", "left", "migrated", "crossed", "moved", "journey", default=0.2)
    els = banner(a, c, s) + [crowd(c, who, 520, 925, 10, 700, 0.55, rows=2, at=0.05, mouth="flat", eyes="sad",
                                   do=[{"act": "walk", "at": key, "dur": 3.0}],
                                   move={"dx": 650, "dy": 0, "from": key, "to": off(key, 3.0)})]
    veh = slot(s, "vehicle", "")
    if veh in PROPS or bg["type"] == "harbor":
        els.append(prop(veh if veh in PROPS else "sailboat", 1450, 800, 1.1, at=0.15, move={"dx": 120, "dy": 0}))
    nums = a.get("numbers") or []
    if nums:
        els.append({"type": "counter", "from": 0, "to": int(nums[0]["value"]), "x": MID, "y": 275, "size": 100, "format": "number", "suffix": " people", "at": w.at(nums[0]["text"].split()[0].replace(",", ""), default=0.3), "dur": 1.6})
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_social_change(c, a, s, w):
    bg = bg_for(c, a, s, default="street", force="street")
    old = str(slot(s, "old") or "OLD RULES").upper()[:20]
    new = str(slot(s, "new") or PI.slogan_for(a, s)).upper()[:24]
    key = w.at("abolished", "won", "ended", "passed", "finally", "granted", "banned", default=0.55)
    els = banner(a, c, s) + [
        prop("barricade", 560, 890, 1.3, at=0.05, do=[{"act": "collapse", "at": key}]),
        {"type": "sign", "text": old, "x": 560, "y": 640, "size": 46, "at": 0.08},
        crowd(c, slot(s, "who") or "civ", 1300, 930, 18, 900, 0.58, rows=3, flip=True, at=0.1, mouth="open", do=[{"act": "cheer", "at": key}]),
        {"type": "sign", "text": new, "x": 1300, "y": 620, "size": 46, "at": key},
    ]
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_two_talk(c, a, s, w):
    ppl = [p["name"] for p in a.get("people") or []] + list(a.get("groups") or [])
    A = slot(s, "a") or (ppl[0] if ppl else "")
    B = slot(s, "b") or (ppl[1] if len(ppl) > 1 else "")
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="interior", indoor=True)
    la, lb = slot(s, "a_line"), slot(s, "b_line")
    left = person(c, A, 660, FEET, 1.15, pose="point_right", mouth="open", year=year, at=0.02)
    right = person(c, B, 1260, FEET, 1.15, flip=True, pose="shrug", mouth="smirk", year=year, at=0.06)
    if la:
        left["say"] = [say(la, w.at("said", "told", "asked", "wanted", "offered", "warned", default=0.2))]
    if lb:
        right["say"] = [say(lb, w.at("replied", "answered", "but", default=0.6))]
    pic = slot(s, "prop") or prop_in_text(a.get("text"), skip=("crowd",))
    els = banner(a, c, s) + [left, right] + ([prop(pic, MID, 760, 0.8, at=w.at(pic, default=0.3))] if pic in PROPS else [])
    cam = {"shots": [{"at": 0, "zoom": 1.0}, {"at": 0.25, "zoom": 1.35, "focus": [660, 600], "move": "cut"}, {"at": 0.6, "zoom": 1.35, "focus": [1260, 600], "move": "cut"}, {"at": 0.9, "zoom": 1.0, "move": "pan"}]}
    return {"bg": bg, "elements": els, "camera": cam}


def L_plot(c, a, s, w):
    ppl = [p["name"] for p in a.get("people") or []] + list(a.get("groups") or [])
    bg = {"type": "dark"}
    c.state["bg"] = dict(bg)
    obj = slot(s, "object") if slot(s, "object") in PROPS else (prop_in_text(a.get("text"), skip=("crowd",)) or "document")
    els = [prop("candle", 960, 880, 1.2, at=0.0, idle="float"), prop(obj, 960, 640, 1.3, at=w.at(obj, "secret", "plan", "plot", default=0.3), idle="bob"),
           person(c, ppl[0] if ppl else "", 640, FEET, 1.1, pose="think", mouth="smirk", eyes="angry", at=0.05),
           person(c, ppl[1] if len(ppl) > 1 else "", 1280, FEET, 1.1, flip=True, pose="think", mouth="smirk", at=0.1),
           prop("folding_screen", 1700, 890, 1.2, at=0.05), person(c, "", 1790, FEET, 0.8, flip=True, at=0.5, eyes="wide", extras=["!"])]
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.07]}}


def L_celebration(c, a, s, w):
    ppl = [p["name"] for p in a.get("people") or []]
    who = slot(s, "winner") or (ppl[0] if ppl else (a.get("groups") or [""])[0])
    loser = slot(s, "loser") or (ppl[1] if len(ppl) > 1 else (a.get("groups") or ["", ""])[1:2][0] if len(a.get("groups") or []) > 1 else None)
    bg = bg_for(c, a, s, default="street", force="street")
    key = w.at("won", "victory", "celebrated", "triumph", "conquered", "parade", default=0.3)
    els = banner(a, c, s) + [crowd(c, who, 1040, 930, 18, 1100, 0.58, rows=3, at=0.05, mouth="grin", do=[{"act": "cheer", "at": key}]),
                             person(c, who, 640, FEET, 1.2, pose="cheer", mouth="grin", eyes="happy", at=0.02, do=[{"act": "celebrate", "at": key}]),
                             prop("trophy", 1040, 520, 1.1, at=key, enter="pop"), prop("flag", 330, 880, 1.0, at=0.1)]
    if loser:
        els.append(person(c, loser, 1780, FEET, 0.85, flip=True, pose="down", mouth="frown", eyes="sad", extras=["tear"], at=0.4))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.05]}}


def L_disaster(c, a, s, w):
    low = str(a.get("text") or "").lower()
    bg = bg_for(c, a, s, default="harbor", time="dusk")
    hit = w.at("sank", "exploded", "crashed", "burned", "collapsed", "erupted", "hit", "struck", "flooded", "fire", default=0.4)
    if re.search(r"sank|ship|titanic|iceberg|ocean|sea", low):
        thing, act = ("ocean_liner" if "titanic" in low or "liner" in low else "ship"), "sink"
    elif re.search(r"exploded|explosion|bomb", low):
        thing, act = "factory", "explode"
    elif re.search(r"fire|burn", low):
        thing, act = "house", "fire"
    else:
        thing, act = "house", "collapse"
    els = banner(a, c, s) + [prop(thing, 1150, 860, 1.1 if thing != "ocean_liner" else 0.9, at=0.05, do=[{"act": act, "at": hit}]),
                             person(c, "", 460, FEET, 0.9, flip=False, at=0.2, mouth="o", eyes="wide", do=[{"act": "surprise", "at": hit}]),
                             person(c, "", 700, FEET, 0.8, at=0.25, mouth="o", eyes="wide", do=[{"act": "tremble", "at": hit}])]
    nums = a.get("numbers") or []
    if nums:
        els.append(text(nums[0]["shown"] + (" DEAD" if nums[0]["kind"] == "casualty" or re.search(r"died|killed|dead", low) else ""), MID, 275, 80, "red",
                        at=w.at(nums[0]["text"].split()[0].replace(",", ""), default=0.7)))
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


EMOTION_FACE = {"triumph": ("cheer", "grin", "happy"), "tragedy": ("down", "frown", "sad"), "shock": ("shrug", "o", "wide"),
                "tension": ("angry_fists", "frown", "angry"), "humor": ("shrug", "smirk", "dot"), "neutral": ("point_right", "smile", "dot")}
ACT_WORDS = {"walk": ("walked", "went", "left", "arrived"), "run": ("ran", "fled", "rushed", "escaped"), "fight": ("fought", "attacked", "struck"),
             "dig": ("dug", "mined", "farmed"), "hammer": ("built", "constructed", "forged"), "cheer": ("won", "celebrated", "cheered"),
             "cry": ("cried", "wept", "mourned", "lost"), "think": ("thought", "planned", "wondered", "decided"), "point": ("pointed", "ordered", "told", "demanded")}


def L_story_moment(c, a, s, w):
    """The catch-all: one or two characters, the one prop that matters, a label, a feeling that matches the line."""
    ppl = [p["name"] for p in a.get("people") or []] + list(a.get("groups") or [])
    who = slot(s, "who") or (ppl[0] if ppl else "")
    other = (list(slot(s, "with", []) or []) if isinstance(slot(s, "with"), list) else [slot(s, "with")]) if slot(s, "with") else ppl[1:2]
    year = (a.get("years") or [None])[0]
    bg = bg_for(c, a, s, default="interior" if a.get("mood") == "somber" else "field")
    pose, mouth, eyes = EMOTION_FACE.get(a.get("emotion"), EMOTION_FACE["neutral"])
    act = slot(s, "action")
    if act not in ACT_WORDS:
        act = next((k for k, ws in ACT_WORDS.items() if any(w.at(x) for x in ws)), None)
    main = person(c, who, 620 if other else 700, FEET, 1.2, pose=pose, mouth=mouth, eyes=eyes, year=year, at=0.02)
    if act:
        main["do"] = [{"act": act, "at": w.at(*ACT_WORDS[act], default=0.3), "dur": 1.8}]
    els = banner(a, c, s) + [main]
    if other and other[0]:
        els.append(person(c, other[0], 1380, FEET, 1.05, flip=True, mouth="o" if a.get("emotion") == "shock" else "smile", eyes="wide",
                          year=year, at=w.at(_first_name_token(other[0]), default=0.2)))
    obj = slot(s, "object") if slot(s, "object") in PROPS else prop_in_text(a.get("text"), skip=("crowd", "puppet", "custom"))
    if obj:
        els.append(prop(obj, 1000 if other else 1250, 830 if PROPS[obj][0] == "bottom" else 640, 0.9, at=w.at(obj, default=0.35)))
    if slot(s, "label"):
        els.append(text(str(slot(s, "label"))[:28], MID, 250, 66, "navy", at=w.at(*re.findall(r"[A-Za-z]{4,}", str(slot(s, "label")))[:1], default=0.3)))
    if slot(s, "say"):
        main["say"] = [say(slot(s, "say"), 0.3)]
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.06]}}


LAYOUTS = {
    "intro_person": L_intro_person, "speech": L_speech, "document": L_document, "treaty": L_treaty, "chamber": L_chamber,
    "debate": L_debate, "election": L_election, "war_declaration": L_war_declaration, "battle_wide": L_battle_wide,
    "battle_clash": L_battle_clash, "map_region": L_map_region, "map_move": L_map_move, "country_est": L_country_est,
    "city_est": L_city_est, "crowd": L_crowd, "protest": L_protest, "riot": L_riot, "stat": L_stat, "timeline": L_timeline,
    "cause_effect": L_cause_effect, "before_after": L_before_after, "economic": L_economic, "invention": L_invention,
    "death": L_death, "migration": L_migration, "social_change": L_social_change, "two_talk": L_two_talk, "plot": L_plot,
    "celebration": L_celebration, "disaster": L_disaster, "story_moment": L_story_moment,
    "map_story": L_map_story, "event_scene": L_event_scene,
}


def compose(pattern, beat, analysis, slots=None, ctx=None):
    """The scene for one beat. `pattern` is a pattern dict (or id); None when this beat can't be built from it."""
    from . import patterns as PT
    p = pattern if isinstance(pattern, dict) else PT.get(pattern)
    if not p:
        return None
    fn = LAYOUTS.get(p["layout"])
    if fn is None:
        return None
    ctx = ctx or Ctx()
    a = dict(analysis)
    a.setdefault("text", beat.get("text", ""))
    a["mood"] = beat.get("mood", a.get("mood", "fun"))
    w = Words(beat.get("text", ""))
    try:
        sc = fn(ctx, a, slots or {}, w)
    except Exception:
        if STRICT:
            raise
        return None
    if not sc or not sc.get("elements"):
        return None
    tr = (p.get("transitions") or ["auto"])[0]
    if tr not in ("auto", None) and "transition" not in sc:
        sc["transition"] = tr
    sc["note"] = f"pattern {p['id']}"
    return sc
