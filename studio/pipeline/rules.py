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
        beats = [f"Today we're talking about {title}, and trust me, it's a wild story with a twist nobody expected.",
                 f"So how did {title} actually happen? Let's start at the very beginning.",
                 f"First, picture the world before {title}. Kingdoms, rivals, and a lot of people with big plans.",
                 "Then things start to change, slowly at first, and then all at once.",
                 "Rivals notice, alliances shift, and suddenly everyone is watching the same map.",
                 f"And that's {title} in a nutshell. If you liked this one, subscribe for more history!"]
    beats = [dict(mood=mood_for(b), text=b) for b in beats if b.strip()]
    if beats:
        beats[-1]["mood"] = "fun"
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


def rule_scene(beat, idx=0, cast=None):
    text, mood = beat["text"], beat.get("mood", "fun")
    rnd = random.Random(idx * 7 + len(text))
    low = text.lower()
    els = []
    if mood == "somber":
        bg = rnd.choice([{"type": "dark"}, {"type": "field", "time": "dusk"}, {"type": "snow", "time": "storm"}])
    elif mood == "tense":
        bg = rnd.choice([{"type": "battlefield"}, {"type": "field", "time": "storm"}, {"type": "city", "time": "night"},
                         {"type": "dark"}])
    else:
        bg = rnd.choice([{"type": "paper"}, {"type": "sunburst"}, {"type": "field"}, {"type": "hills"},
                         {"type": "interior"}, {"type": "city"}, {"type": "desert"}, {"type": "paper", "color": "#F6F0E2"}])
    years = re.findall(r"\b(1\d{3}|20\d{2}|\d{3,4} ?(?:BC|AD))\b", text)
    if years:
        els.append({"type": "text", "text": years[0], "x": 960, "y": 130, "size": 100, "at": f"word:{years[0].split()[0]}"})
    hits = _cast_hits(text, cast)
    chars = hits[:2] if hits else [{"name": "", "kind": "civ"}]
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
        els.append(el)
        if c.get("name"):
            els.append({"type": "text", "text": c["name"].upper()[:18], "x": x, "y": 470, "size": 54,
                        "color": "red" if k == 0 else "navy", "at": el["at"]})
    prop = None
    for words, name in KEYWORD_PROPS:
        if any(w in low for w in words):
            if mood == "somber" and name in ("explosion", "trophy"):
                continue
            prop = (name, next(w for w in words if w in low))
            break
    if mood == "somber":
        for i, x in enumerate((760, 960, 1160)):
            els.append({"type": "prop", "name": "candle", "x": x, "y": 860, "scale": 1.5, "enter": "fade", "at": 0.2 + i * 0.1})
    elif prop:
        name, word = prop
        params = {"points": [[0, 0.2], [0.5, 0.6], [1, 0.95]]} if name == "line_chart" else {}
        x = 960 if len(chars) == 2 else 1250
        els.append({"type": "prop", "name": name, "x": x, "y": 820 if name not in ("explosion", "plane") else 520,
                    "scale": 0.9 if name not in ("line_chart",) else 1.0, "params": params, "at": f"word:{word}"})
    else:
        quote = " ".join(text.split()[:5]).rstrip(",.;:") + "..."
        els.append({"type": "bubble", "text": quote, "x": 1250 if len(chars) == 1 else 960, "y": 360, "size": 44,
                    "tail": "left", "at": 0.15})
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
