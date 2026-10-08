"""Props that say something. A document gets its real name and the lines actually written on it, a newspaper gets a
headline that fits the event, a protest sign gets a slogan, a number gets shown as a number, and weapons and tools
match the era. Everything here is local text logic: no AI call.

prop_card(...) returns the full "prop intelligence" record for an important prop:
  name, context, text (title + lines), purpose, visual details, who interacts with it, when it appears and leaves.
"""
import contextlib
import contextvars
import re

# famous documents: title shown on the paper + the real gist as short lines (never more than 4 lines of ~24 characters)
FAMOUS = {
    "declaration of independence": ("DECLARATION OF INDEPENDENCE", ["We hold these truths to be", "self-evident, that all men", "are created equal..."], "scroll"),
    "constitution": ("THE CONSTITUTION", ["We the People of the", "United States, in Order", "to form a more perfect", "Union..."], "document"),
    "bill of rights": ("BILL OF RIGHTS", ["Congress shall make", "no law respecting", "speech or religion..."], "document"),
    "magna carta": ("MAGNA CARTA", ["No free man shall be", "seized or imprisoned", "except by law of", "the land."], "scroll"),
    "emancipation proclamation": ("EMANCIPATION PROCLAMATION", ["All persons held as", "slaves shall be", "thenceforward free."], "document"),
    "treaty of versailles": ("TREATY OF VERSAILLES", ["Germany accepts blame", "Germany pays", "Army limited to", "100,000 men"], "scroll"),
    "treaty of paris": ("TREATY OF PARIS", ["Britain recognizes the", "United States as", "independent."], "scroll"),
    "communist manifesto": ("THE COMMUNIST MANIFESTO", ["Workers of the world,", "unite!"], "document"),
    "monroe doctrine": ("MONROE DOCTRINE", ["No new European", "colonies in the", "Americas."], "document"),
    "truman doctrine": ("TRUMAN DOCTRINE", ["The US will help", "nations resisting", "communism."], "document"),
    "stamp act": ("THE STAMP ACT", ["A tax on every", "printed paper in", "the colonies."], "document"),
    "tea act": ("THE TEA ACT", ["The East India Co.", "may sell tea", "tax-free."], "document"),
    "edict of nantes": ("EDICT OF NANTES", ["Protestants may", "worship in France."], "scroll"),
    "treaty of tordesillas": ("TREATY OF TORDESILLAS", ["Spain and Portugal", "split the New World."], "scroll"),
    "peace of westphalia": ("PEACE OF WESTPHALIA", ["The Thirty Years'", "War is over."], "scroll"),
    "zimmermann telegram": ("ZIMMERMANN TELEGRAM", ["Germany offers Mexico", "an alliance against", "the United States."], "document"),
}
_EXTRA = contextvars.ContextVar("studio_extra_docs", default=None)


@contextlib.contextmanager
def docs_scope(extra):
    """Documents from this video's research brief (real names and lines) for the scenes built inside the block."""
    tok = _EXTRA.set(extra or None)
    try:
        yield
    finally:
        _EXTRA.reset(tok)


GENERIC = {  # kind -> (title, lines, prop)
    "treaty": ("TREATY", ["The war is over.", "Both sides agree", "to these terms."], "scroll"),
    "declaration": ("DECLARATION", ["We hereby declare", "our independence", "and our demands."], "scroll"),
    "law": ("THE LAW", ["Be it enacted that", "from this day on", "this is the rule."], "document"),
    "telegram": ("TELEGRAM", ["URGENT", "MESSAGE FOLLOWS", "STOP"], "document"),
    "letter": ("DEAR SIR,", ["I write to tell you", "what has happened."], "document"),
    "newspaper": ("", [], "newspaper"),
    "contract": ("CONTRACT", ["The parties agree", "to the terms below."], "document"),
    "map_doc": ("THE PLAN", ["Step 1", "Step 2", "Step 3"], "document"),
}
HEADLINES = [  # (event, template). {who} = the main person's surname, {place} = the first place
    ("war_declaration", "WAR DECLARED"), ("treaty", "PEACE AT LAST"), ("election", "{who} WINS"), ("death", "{who} DEAD"),
    ("crisis", "MARKET CRASH"), ("riot", "RIOTS SPREAD"), ("invention", "NEW INVENTION"), ("disaster", "DISASTER!"),
    ("battle", "BATTLE RAGES"), ("law", "NEW LAW PASSED"), ("celebration", "VICTORY!"), ("plot", "PLOT UNCOVERED"),
    ("social", "CHANGE COMES"), ("protest", "CROWDS DEMAND"), ("migration", "FAMILIES LEAVE"),
]
SLOGANS = [  # (regex on the beat, slogan)
    (r"\btax", "NO MORE TAXES!"), (r"\bbread|hungry|famine|starv", "BREAD!"), (r"\bjobs?\b|unemploy|wages?|workers?|strike", "FAIR WAGES!"),
    (r"women|suffrage", "VOTES FOR WOMEN"), (r"slave|abolish", "FREE THEM ALL"), (r"\bpeace\b", "PEACE NOW"),
    (r"\bwar\b", "NO MORE WAR"), (r"\bfreedom|liberty|independence", "LIBERTY!"), (r"\brights?\b|equal", "EQUAL RIGHTS"),
    (r"\bking\b|\btsar\b|\bempire", "DOWN WITH THE KING"), (r"\bland\b|\bpeasants?", "LAND FOR ALL"),
]
SIGNATURE = [  # (regex on role/trait/beat, prop)
    (r"president|capitol|congress", "flag"), (r"king|queen|emperor|monarch|crown|pharaoh|tsar|sultan", "crown"),
    (r"general|commander|army|soldier|warlord|conquer", "sword"), (r"admiral|navy|fleet|naval", "anchor"),
    (r"inventor|invent|engineer", "lightbulb"), (r"scientist|physic|naturalist|chemist", "flask"),
    (r"explorer|voyage|sailed", "compass"), (r"writer|author|wrote|philosopher", "quill"),
    (r"oil|tycoon|banker|baron|money", "moneybag"), (r"dictator|nazi|fascist", "megaphone"),
    (r"speaker|orator|leader of the", "podium"), (r"revolution|rebel", "torch"),
]


def surname(name):
    parts = [p for p in re.split(r"\s+", str(name or "").strip()) if p]
    skip = {"the", "of", "von", "de", "i", "ii", "iii", "iv", "vi", "vii", "viii", "xiv", "xvi"}
    for p in reversed(parts):
        if p.lower().strip(".") not in skip:
            return p.upper()
    return str(name or "").upper()


def doc_for(a, slots=None, want=None):
    """{title, lines, stamp, prop} for the main document of a beat. Slots from the director win."""
    slots = slots or {}
    docs = a.get("documents") or []
    d = docs[0] if docs else {"kind": want or "law", "name": ""}
    key = d["name"].lower()
    title, lines, prop = None, None, None
    for k, v in list((_EXTRA.get() or {}).items()) + list(FAMOUS.items()):
        if k in key or (key and key in k and len(key) > 8):
            title, lines, prop = v
            break
    if title is None:
        g = GENERIC.get(d["kind"], GENERIC["law"])
        title, lines, prop = (d["name"].upper() or g[0]), g[1], g[2]
    title = str(slots.get("doc_title") or title).upper()[:34]
    got = slots.get("doc_lines")
    if isinstance(got, str):
        got = [t.strip() for t in re.split(r"[|\n]", got) if t.strip()]
    lines = [str(x)[:28] for x in (got or lines)][:4]
    return dict(title=title, lines=lines, stamp=str(slots.get("stamp") or "").upper()[:10], prop=prop,
                kind=d["kind"], named=bool(d["name"]))


def headline_for(a, slots=None):
    slots = slots or {}
    if slots.get("headline"):
        return str(slots["headline"]).upper()[:26]
    who = surname((a.get("people") or [{}])[0].get("name")) if a.get("people") else "HE"
    for ev, tpl in HEADLINES:
        if ev in (a.get("events") or []):
            return tpl.format(who=who)[:26]
    if a.get("numbers"):
        return (a["numbers"][0]["shown"] + " " + (a["numbers"][0].get("unit") or "")).upper().strip()[:26]
    return "BIG NEWS!"


def slogan_for(a, slots=None):
    slots = slots or {}
    for k in ("demand", "slogan"):
        if slots.get(k):
            return str(slots[k]).upper()[:30]
    for rx, sl in SLOGANS:
        if re.search(rx, str(a.get("text") or "").lower()):
            return sl
    return "WE WANT CHANGE!"


def signature_prop(role="", text=""):
    blob = f"{role} {text}".lower()
    for rx, prop in SIGNATURE:
        if re.search(rx, blob):
            return prop
    return None


def weapon_for_year(year):
    """The props and tools that fit the era (so no muskets in ancient Rome and no swords in 1944)."""
    if year is None:
        return "sword"
    if year < 1400:
        return "sword"
    if year < 1870:
        return "musket"
    if year < 1945:
        return "cannon"
    return "tank"


def held_for_year(year):
    return "sword" if (year is None or year < 1500) else "pointer"


def prop_card(name, a, slots=None, context="", purpose="", who=(), appears="", leaves=""):
    """The record that explains an important prop (kept in the project's plan so reviews can check it)."""
    slots = slots or {}
    d = doc_for(a, slots) if name in ("document", "scroll") else None
    text = None
    if d:
        text = dict(title=d["title"], lines=d["lines"])
    elif name == "newspaper":
        text = dict(title="THE DAILY NEWS", headline=headline_for(a, slots))
    elif name in ("sign", "board"):
        text = dict(text=slogan_for(a, slots))
    return dict(name=name, context=context or ", ".join(str(y) for y in a.get("years") or []), text=text,
                purpose=purpose, visual="", who=list(who), appears=appears or "on its name", leaves=leaves or "end of scene")
