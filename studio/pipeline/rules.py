"""No-AI fallbacks: a crude script from a transcript/topic, and rule-based scenes from keywords.

Used by the "Basic (no AI)" writer and as the last-resort fallback when an LLM scene can't be repaired.
"""
import random
import re

from ..engine.pen import HATS, KIND_ALIASES, resolve_kind

SOMBER_WORDS = ("massacre", "genocide", "killed", "murdered", "famine", "holocaust", "slaughter", "executed",
                "died", "dead", "deaths", "bombing", "atrocit", "starv", "slaves", "slavery", "tragedy", "victims")
TENSE_WORDS = ("war", "battle", "attack", "invade", "invasion", "crisis", "threat", "army", "siege", "revolt",
               "revolution", "collapse", "enemy", "fight", "conquer", "danger", "panic", "desperate")

KEYWORD_PROPS = [
    (("oil", "fuel", "petrol"), "barrel"), (("money", "tax", "gold", "rich", "economy", "debt", "broke", "trade"), "moneybag"),
    (("king", "queen", "emperor", "crown", "throne", "royal", "monarch"), "crown"), (("ship", "navy", "fleet", "sail", "sea"), "ship"),
    (("plane", "air force", "bomber", "flight"), "plane"), (("factory", "industr", "steel", "build"), "factory"),
    (("city", "capital", "town"), "skyline"), (("treaty", "law", "constitution", "decree", "letter"), "scroll"),
    (("idea", "plan", "invent", "genius"), "lightbulb"), (("castle", "knight", "medieval", "lord"), "castle"),
    (("church", "temple", "senate", "rome", "greek"), "temple"), (("egypt", "pharaoh", "pyramid"), "pyramid"),
    (("train", "railway", "rail"), "train"), (("tank", "armored"), "tank"), (("bomb", "explo", "blast", "boom"), "explosion"),
    (("time", "years", "decade", "century", "clock"), "hourglass"), (("book", "write", "wrote", "history"), "book"),
    (("world", "global", "planet", "empire"), "globe"), (("vote", "election", "democra"), "ballot"),
    (("win", "victory", "won", "champion"), "trophy"), (("rocket", "space", "moon"), "rocket"),
    (("flag", "nation", "independen"), "flag"), (("chart", "percent", "grow", "fell", "rise", "drop"), "line_chart"),
]


def mood_for(text):
    t = text.lower()
    if any(w in t for w in SOMBER_WORDS):
        return "somber"
    if any(w in t for w in TENSE_WORDS):
        return "tense"
    return "fun"


def clean_text(t):
    t = re.sub(r"\[[^\]]*\]", "", t)              # [Music] etc.
    t = re.sub(r"\s+", " ", t).replace(" —", ",").replace("—", ", ").replace("–", "-")
    return t.strip()


def split_beats(text, lo=15, hi=30):
    sents = re.split(r"(?<=[.!?])\s+", clean_text(text))
    beats, cur = [], []
    for s in sents:
        words = s.split()
        if not words:
            continue
        while len(words) > hi:
            beats.append(" ".join(words[:hi - 5]) + ".")
            words = words[hi - 5:]
        if len(cur) + len(words) > hi and len(cur) >= lo:
            beats.append(" ".join(cur))
            cur = []
        cur += words
        if len(cur) >= lo:
            beats.append(" ".join(cur))
            cur = []
    if cur:
        if beats and len(cur) < 8:
            beats[-1] += " " + " ".join(cur)
        else:
            beats.append(" ".join(cur))
    return beats


def offline_script(topic, minutes, source=None):
    """Very basic script. With a source transcript it reuses the text (testing only)."""
    n = max(6, int(round(minutes * 8)))
    if source and source.get("segments"):
        text = " ".join(s["text"] for s in source["segments"])
        beats = split_beats(text)[:n]
        title = source.get("title") or topic or "Untitled"
    else:
        title = topic or "History"
        beats = [f"{title} sounds boring, until you hear what actually happened.",
                 f"So what was {title}? Short version: a big chapter of history where rivals, mistakes and a few lucky breaks changed the world.",
                 "In this video we'll see how it started, how it got out of hand, and how it ended.",
                 f"First, picture the world before {title}. Kingdoms, rivals, and a lot of people with big plans.",
                 "Then things start to change, slowly at first, and then all at once.",
                 "Rivals notice, alliances shift, and suddenly everyone is watching the same map.",
                 f"And that's why {title} still matters today."]
    beats = [dict(mood=mood_for(b), text=b) for b in beats if b.strip()]
    if beats:
        beats[-1]["mood"] = "fun"
    if not (source and source.get("segments")) and len(beats) >= 3:
        beats[0]["part"] = "hook"
        beats[1]["part"] = beats[2]["part"] = "intro"
        beats[-1]["part"] = "payoff"
    return dict(title=title, topic=topic or title, beats=beats, facts=[], cast=[], generated_by="offline")


# ------------------------------------------------------------------ rule-based scenes
def _cast_hits(text, cast):
    hits = []
    low = text.lower()
    for c in cast or []:
        name = str(c.get("name", "")).strip()
        if name and name.lower() in low:
            hits.append((low.index(name.lower()), c))
    hits.sort(key=lambda h: h[0])
    return [c for _, c in hits]


def _theme_bg(themes, idx, mood, rnd):
    from .themes import THEMES
    places = []
    for k in themes[:2]:
        places += [dict(p) for p in THEMES[k]["places"] if p.get("type") != "map"]
    if not places:
        return None
    bg = dict(places[idx % len(places)])
    if mood == "somber":
        if bg["type"] in ("palace", "space", "underwater", "interior", "trench"):
            return {"type": "dark"} if idx % 2 else {"type": "field", "time": "dusk"}
        bg["time"] = "dusk"
    elif mood == "tense" and bg["type"] not in ("palace", "interior", "space", "underwater", "trench"):
        bg["time"] = rnd.choice(["storm", "night", "dusk"])
    return bg


def rule_scene(beat, idx=0, cast=None, themes=()):
    """A simple scene from keywords and the video's topic kit (used without AI, and as the last-resort fallback)."""
    from .themes import THEMES, beat_themes, line_for, REACTIONS
    text, mood = beat["text"], beat.get("mood", "fun")
    rnd = random.Random(idx * 7 + len(text))
    low = text.lower()
    ths = beat_themes(text, themes)
    # countries and borders -> a map; several dates -> a timeline (with a character reacting)
    m = map_scene(text, mood, rnd)
    if m is not None:
        return m
    all_years = list(dict.fromkeys(re.findall(r"\b(1\d{3}|20\d{2})\b", text)))
    if len(all_years) >= 3:
        sc = timeline_scene(text, mood, all_years)
        kind = THEMES[ths[0]]["kinds"][0] if ths else "civ"
        sc["elements"].append({"type": "char", "kind": resolve_kind(kind), "x": 960, "y": 470, "scale": 0.55,
                               "pose": "point_right" if mood != "somber" else "down", "at": 0.02})
        return sc
    els = []
    from ..engine.schema import activity_place
    bg = activity_place(text)                     # "he built a factory" -> the construction site, full screen
    if bg is not None and mood == "somber" and bg["type"] not in ("prison", "courtroom", "parliament", "mine",
                                                                    "classroom", "lab"):
        bg["time"] = "dusk"
    if bg is None:
        bg = _theme_bg(ths, idx, mood, rnd)
    if bg is None:
        if mood == "somber":
            bg = rnd.choice([{"type": "dark"}, {"type": "field", "time": "dusk"}, {"type": "snow", "time": "storm"}])
        elif mood == "tense":
            bg = rnd.choice([{"type": "battlefield"}, {"type": "field", "time": "storm"}, {"type": "city", "time": "night"},
                             {"type": "dark"}])
        else:
            bg = rnd.choice([{"type": "paper"}, {"type": "sunburst"}, {"type": "field"}, {"type": "hills"},
                             {"type": "interior"}, {"type": "city"}, {"type": "street"}, {"type": "desert"},
                             {"type": "paper", "color": "#F6F0E2"}])
    years = re.findall(r"\b(1\d{3}|20\d{2}|\d{3,4} ?(?:BC|AD))\b", text)
    if years:
        els.append({"type": "text", "text": years[0], "x": 960, "y": 130, "size": 100, "at": f"word:{years[0].split()[0]}"})
    hits = _cast_hits(text, cast)
    default_kind = THEMES[ths[0]]["kinds"][0] if ths else "civ"
    chars = hits[:2] if hits else [{"name": "", "kind": default_kind}]
    xs = [480, 1440] if len(chars) == 2 else [520]
    for k, (c, x) in enumerate(zip(chars, xs)):
        pose = "down" if mood == "somber" else rnd.choice(["cheer", "shrug", "hips", "point_right", "think", "wave"])
        mouth = "flat" if mood == "somber" else rnd.choice(["smile", "grin", "open", "smirk", "frown"])
        eyes = "sad" if mood == "somber" else rnd.choice(["dot", "dot", "wide", "happy", "angry"])
        el = {"type": "char", "kind": resolve_kind(c.get("kind")), "x": x, "y": 900, "scale": 1.0 if k == 0 else 1.15,
              "pose": pose, "mouth": mouth, "eyes": eyes, "flip": k == 1,
              "at": f"word:{c['name'].split()[0]}" if c.get("name") else 0.0}
        if c.get("hat_color"):
            el["hat_color"] = c["hat_color"]
        if c.get("name"):
            el["who"] = c["name"]
        els.append(el)
        if c.get("name"):
            els.append({"type": "text", "text": c["name"].upper()[:18], "x": x, "y": round(900 - 375 * el["scale"] - 110),
                        "size": 54,
                        "color": "red" if k == 0 else "navy", "at": el["at"]})
    prop = None
    for words, name in KEYWORD_PROPS:
        if any(w in low for w in words):
            if mood == "somber" and name in ("explosion", "trophy"):
                continue
            prop = (name, next(w for w in words if w in low))
            break
    if prop is None and ths and mood != "somber":
        from ..engine.places import SKYLINES
        shown = {n for n, _, _ in SKYLINES.get(bg.get("skyline"), [])}
        tprops = [p for p in THEMES[ths[0]]["props"] if p not in shown] or ["flag"]
        named = [p for p in tprops if p.replace("_", " ") in low]
        pick = named[0] if named else tprops[idx % len(tprops)]
        prop = (pick, pick.replace("_", " ") if named else None)
    act = action_prop(text, mood)
    if act is not None:
        prop = None                                   # the action moment takes the prop's place
        act["x"] = 960 if len(chars) == 2 else 1300
        els.append(act)
    cnt = number_counter(text)
    if cnt is not None and not years:
        els.append(cnt)
    if mood == "somber":
        for i, x in enumerate((760, 960, 1160)):
            els.append({"type": "prop", "name": "candle", "x": x, "y": 860, "scale": 1.1, "enter": "fade", "at": 0.2 + i * 0.1})
    elif prop:
        name, word = prop
        params = {"points": [[0, 0.2], [0.5, 0.6], [1, 0.95]]} if name == "line_chart" else {}
        x = 960 if len(chars) == 2 else 1300
        center = name in ("explosion", "plane", "bomb", "biplane", "zeppelin", "helicopter", "satellite", "planet",
                          "sun", "moon", "star", "eagle", "dragon", "seagull", "hot_air_balloon")
        els.append({"type": "prop", "name": name, "x": x, "y": 520 if center else 860,
                    "scale": 0.8 if name not in ("line_chart",) else 1.0, "params": params,
                    "at": f"word:{word.split()[0]}" if word else 0.3})
    work = {"mine": "dig", "farm": "dig"}.get(bg.get("type"))
    if work and mood != "somber":
        main = next(e for e in els if e["type"] == "char")
        main["do"] = [{"act": work, "at": 0.15, "dur": 2.4}]
        main["prop"] = "pickaxe" if bg["type"] == "mine" else "shovel"
    line = line_for(text, mood, ths, idx)
    if line is None and mood != "somber" and rnd.random() < 0.55:
        line = rnd.choice(REACTIONS[mood])
    if line:
        speaker = next(e for e in els if e["type"] == "char")
        speaker["say"] = [line]
    return {"bg": bg, "elements": els, "camera": {"zoom": [1.0, 1.04]}}


def offline_package(script, minutes):
    beats = script.get("beats", [])
    n = len(beats)
    k = max(1, n // 6)
    chapters = [dict(beat=i, title=" ".join(beats[i]["text"].split()[:4]).rstrip(",.;:")) for i in range(0, n, k)][:8]
    if chapters:
        chapters[0]["title"] = "Intro"
    title = script.get("title") or script.get("topic") or "History"
    return dict(titles=[f"{title}, Explained", f"The Entire Story of {title}", f"{title} in {max(1, round(minutes))} Minute{'s' if round(minutes) > 1 else ''}"],
                hook=f"How did {title} really happen? Here's the whole story, told with stickmen.",
                chapters=chapters, question=f"What should we cover after {title}?",
                tags=[title, "history", "stickman", "animated history", "explained", "documentary"],
                hashtags=["#history", "#animation", "#explained"],
                thumbnail=dict(line1=title if len(title) <= 18 else " ".join(title.split()[:3]), line2="EXPLAINED", small_kind="civ", big_kind="crown",
                               image_prompt=title))


# ------------------------------------------------------------------ richer fallbacks: maps, numbers, dates, actions
COUNTRY_WORDS = {"britain": "United Kingdom", "england": "United Kingdom", "the uk": "United Kingdom",
                 "great britain": "United Kingdom", "america": "United States of America",
                 "the us": "United States of America", "the usa": "United States of America",
                 "united states": "United States of America", "soviet union": "Russia", "the ussr": "Russia",
                 "prussia": "Germany", "persia": "Iran", "siam": "Thailand", "ottoman": "Turkey", "holland": "Netherlands",
                 "korea": "South Korea", "burma": "Myanmar", "ceylon": "Sri Lanka", "rome": "Italy",
                 "the netherlands": "Netherlands"}
MAP_WORDS = ("invade", "invaded", "invasion", "conquer", "conquered", "border", "annex", "attack", "attacked",
             "empire", "territory", "map", "colony", "colonies", "march", "marched", "expanded", "occupied", "seized",
             "took over", "allied", "alliance")
MOVE_WORDS = ("invade", "invaded", "invasion", "attack", "attacked", "march", "marched", "sailed", "advanced")
NUMBER_RE = re.compile(r"(\$)?\b(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(million|billion|thousand)?\s+"
                       r"(men|soldiers|troops|people|dead|ships|tanks|planes|dollars|pounds|years|days|miles|"
                       r"kilometers|workers|prisoners|refugees|casualties)\b", re.I)


class _Pt:
    def __init__(self, x, y):
        self.x, self.y = x, y


# huge countries: where the story usually happens (not the middle of Siberia or Nunavut)
ANCHOR_POINTS = {"Russia": _Pt(38.0, 55.0), "United States of America": _Pt(-90.0, 38.5), "Canada": _Pt(-90.0, 50.0),
                 "China": _Pt(110.0, 33.0), "Brazil": _Pt(-47.0, -15.0), "Australia": _Pt(140.0, -28.0),
                 "India": _Pt(78.0, 22.0), "France": _Pt(2.5, 46.8), "Norway": _Pt(9.0, 61.0)}


def countries_in(text):
    """Natural Earth country names mentioned in the text, in order of appearance."""
    from ..engine import geo
    low = " " + text.lower() + " "
    found = []
    for name in geo.COUNTRIES.keys():
        n = name.lower()
        if len(n) > 3 and re.search(r"\b" + re.escape(n) + r"\b", low):
            found.append((low.index(n), name, name.split()[0]))
    for word, name in COUNTRY_WORDS.items():
        m = re.search(r"\b" + re.escape(word) + r"\b", low)
        if m:
            found.append((m.start(), name, word.split()[-1]))
    seen, out = set(), []
    for pos, name, word in sorted(found):
        if name not in seen:
            seen.add(name)
            out.append((name, word))
    return out


def map_scene(text, mood, rnd):
    """A map scene when the narration is about countries and borders (invasions, empires, alliances)."""
    from ..engine import geo
    low = text.lower()
    if mood == "somber" or not any(w in low for w in MAP_WORDS):
        return None
    hits = countries_in(text)[:3]
    if not hits:
        return None
    geoms = [(n, w, geo.countries_geom([n])) for n, w in hits]
    geoms = [(n, w, g) for n, w, g in geoms if g is not None]
    if not geoms:
        return None
    pts = [ANCHOR_POINTS.get(n) or g.representative_point() for n, _, g in geoms]
    lons = [p.x for p in pts]
    lats = [p.y for p in pts]
    span = max(max(lons) - min(lons), (max(lats) - min(lats)) * 1.6)
    width = max(18.0, min(span * 1.9 + 14, 110.0))
    center = [round(sum(lons) / len(lons), 1), round(max(-55, min(65, sum(lats) / len(lats))), 1)]
    palette = ["#C8302B", "#2B3F8C", "#3C8C4A"]
    els = []
    for k, ((name, word, g), p) in enumerate(zip(geoms, pts)):
        els.append({"type": "territory", "countries": [name], "color": palette[k % 3], "at": f"word:{word}"})
        els.append({"type": "text", "text": name.upper()[:16] if len(name) < 17 else word.upper(),
                    "lon": round(p.x, 1), "lat": round(p.y, 1), "size": 50, "color": "white", "at": f"word:{word}"})
    if len(geoms) >= 2 and any(w in low for w in MOVE_WORDS):
        a, b = pts[0], pts[1]
        mover = next(w for w in MOVE_WORDS if w in low)
        els.append({"type": "arrow", "from": {"lon": round(a.x, 1), "lat": round(a.y, 1)},
                    "to": {"lon": round(b.x, 1), "lat": round(b.y, 1)}, "color": "red", "curve": -60,
                    "units": "army", "count": 4, "at": f"word:{mover.split()[0]}"})
    if "battle" in low and len(pts) >= 2:
        els.append({"type": "battle", "lon": round((pts[0].x + pts[1].x) / 2, 1),
                    "lat": round((pts[0].y + pts[1].y) / 2, 1), "at": "word:battle"})
    years = re.findall(r"\b(1\d{3}|20\d{2})\b", text)
    if years:
        els.append({"type": "text", "text": years[0], "x": 960, "y": 110, "size": 90, "color": "white",
                    "at": f"word:{years[0]}"})
    return {"bg": {"type": "map", "center": center, "width": round(width, 1), "style": "dark"}, "elements": els,
            "camera": {"zoom": [1.0, 1.05]}}


def number_counter(text):
    """A counter for the first big number with a unit ("600,000 men", "$2 billion")."""
    m = NUMBER_RE.search(text)
    if not m:
        return None
    dollar, num, scale, unit = m.groups()
    try:
        v = float(num.replace(",", "")) * {"thousand": 1e3, "million": 1e6, "billion": 1e9}.get((scale or "").lower(), 1)
    except ValueError:
        return None
    if v < 20 or unit.lower() in ("years", "days"):
        return None
    big = v >= 1e6
    shown = v / (1e9 if v >= 1e9 else 1e6) if big else v
    money = {"dollars": "$", "pounds": "£"}.get(unit.lower(), "$" if dollar else "")
    suffix = (" billion" if v >= 1e9 else " million" if big else "") + ("" if money else f" {unit.lower()}")
    return {"type": "counter", "from": 0, "to": round(shown, 1) if big else round(shown), "x": 960, "y": 200,
            "size": 96, "prefix": money, "suffix": suffix,
            "format": "number", "decimals": 1 if big and shown != int(shown) else 0, "at": f"word:{num.split(',')[0]}",
            "dur": 1.6}


ACTION_RULES = [  # (words, prop, act)
    (("sank", "sunk", "sinking", "torpedoed"), "galleon", "sink"),
    (("exploded", "blew up", "explosion", "bombed"), "explosion", None),
    (("stormed", "destroyed", "collapsed", "torn down", "tore down", "demolished", "razed"), "castle", "collapse"),
    (("fired", "cannon", "bombarded", "artillery"), "cannon", "fire"),
]


def action_prop(text, mood):
    low = text.lower()
    if mood == "somber":
        return None
    for words, prop, act in ACTION_RULES:
        hit = next((w for w in words if w in low), None)
        if hit:
            el = {"type": "prop", "name": prop, "x": 1300, "y": 860 if prop != "explosion" else 480,
                  "scale": 0.9 if prop != "galleon" else 0.6, "at": 0.05}
            if act:
                el["do"] = [{"act": act, "at": f"word:{hit.split()[0]}"}]
            else:
                el["at"] = f"word:{hit.split()[0]}"
            return el
    return None


def timeline_scene(text, mood, years):
    els = [{"type": "timeline", "y": 700, "events": [{"year": int(y), "label": "", "at": f"word:{y}"} for y in years[:5]]}]
    return {"bg": {"type": "paper" if mood != "somber" else "dark"}, "elements": els, "camera": {"zoom": [1.0, 1.03]}}
