"""The local prop index: the words of a narration -> the prop that shows them. No AI, no network.

The props themselves are registered in `engine/registry.PROPS` (about 230 drawn in code, plus the shared library from
`engine/prop_library.py`). This module answers the question the composer, the scene repair and the coverage check keep
asking: "which of all these props shows this word?".

  1. A word that IS a prop (or a known alias) wins: "cannon" -> cannon. This is what the composer always did.
  2. Otherwise the meaning table (`prop_words.json`, concrete nouns only: "troops" -> helmet, "treaty" -> scroll,
     "gunpowder" -> keg) and the tags of the library props ("duel" -> pistol).
  3. The year narrows it: nothing is picked that did not exist yet (ERA_FIRST, and a library prop's own `frm`).
  4. What no prop answers is written to `data/prop_gaps.json`, so `python -m studio props gaps` can say what is missing and
     the one AI call that draws props only draws those.
"""
import json
import os
import re

from ..engine import registry as R, prop_library as PL

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS_FILE = os.path.join(HERE, "prop_words.json")
NEVER = ("custom", "crowd", "puppet")

# the first year a prop can appear in a story without being an anachronism (the storyboard review reads this too)
ERA_FIRST = {"tank": 1915, "plane": 1903, "biplane": 1903, "helicopter": 1936, "rocket": 1944, "satellite": 1957,
             "computer": 1946, "tv": 1927, "radio": 1895, "telephone": 1876, "car": 1886, "carrier": 1918,
             "mini_carrier": 1918, "mushroom_cloud": 1945, "zeppelin": 1900, "skyscraper": 1885, "submarine": 1620,
             "periscope": 1854, "dynamite": 1867, "musket": 1400, "cannon": 1326, "bike": 1817, "train": 1804,
             "tanker": 1886, "ocean_liner": 1838, "microphone": 1876, "camera": 1826, "barbed_wire": 1867,
             "tank_ship": 1886, "speed_lines": 0, "lightbulb": 1879, "statue_of_liberty": 1886, "eiffel_tower": 1889,
             "big_ben": 1859, "brandenburg_gate": 1791, "arc_de_triomphe": 1836, "white_house": 1800, "capitol": 1800}
ERA_SLACK = 8            # a narration may talk about something a few years before it appears

# words that are a prop in one sentence and a verb in the next: they count only as a noun, i.e. right after "a", "the" or an
# adjective ("a red rose", "the cross"), never after a subject ("prices rose", "they cross the river")
NOUN_ONLY = {"rose": {"a", "an", "the", "red", "white", "yellow", "single", "wild", "one"},
             "cross": {"a", "the", "wooden", "christian", "holy", "large", "great", "giant", "burning", "red"},
             "saw": {"a", "the", "rusty", "hand"}}

# in a narration these words mean something other than the scene-writer alias of the same name ("cross" -> an X mark there)
NARRATION = {"cross": "christian_cross"}

_cache = {}


# ---------------------------------------------------------------- the tables
def _norm(w):
    return re.sub(r"\s+", " ", str(w or "").lower().strip())


def words():
    """word or phrase -> prop name. The meaning table first, then library tags and variant words (they win: they were
    written for exactly that prop). Entries pointing at a prop that does not exist are dropped."""
    if "words" in _cache:
        return _cache["words"]
    out = {}
    try:
        with open(WORDS_FILE, encoding="utf-8") as f:
            table = (json.load(f) or {}).get("words") or {}
    except (OSError, ValueError):
        table = {}
    for w, target in table.items():
        if target in R.PROPS and target not in NEVER:
            out[_norm(w)] = target
    for name, d in PL.LIBRARY.items():
        for t in d.get("tags") or []:
            if t not in R.PROPS or R.PROPS.get(t) is None:         # a tag never replaces a word that is itself a prop name
                out[_norm(t)] = name
    for name, v in PL.VARIANTS.items():
        for w in v.get("words") or []:
            out[_norm(w)] = name
    _cache["words"] = out
    return out


def phrases():
    """'rosetta stone' -> rosetta_stone: a prop whose name is several words is matched as a phrase (aliases too)."""
    if "phrases" not in _cache:
        out = {k.replace("_", " "): v for k, v in R.PROP_ALIASES.items() if "_" in k and v in R.PROPS}
        out.update({n.replace("_", " "): n for n in R.PROPS if "_" in n and n not in NEVER})
        _cache["phrases"] = out
    return _cache["phrases"]


def reset():
    """Forget the tables (after the library grew)."""
    _cache.clear()


def first_year(name):
    """The first year `name` fits a story, or None when it is timeless."""
    if name in ERA_FIRST:
        return ERA_FIRST[name]
    d = PL.LIBRARY.get(name)
    if d and d.get("frm", -3000) > -3000:
        return d["frm"]
    v = PL.VARIANTS.get(name)
    return first_year(v["prop"]) if v else None


def fits(name, year, slack=ERA_SLACK):
    fy = first_year(name)
    return year is None or fy is None or fy <= year + slack


def year_in(text):
    m = re.search(r"\b(1[0-9]{3}|20[0-3][0-9])\b", str(text or ""))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- finding props in text
def _noun_ok(tokens, i):
    before = NOUN_ONLY.get(tokens[i])
    return before is None or (tokens[i - 1] if i else "") in before


def _singular(t):
    return [t] + ([t[:-1]] if t.endswith("s") and len(t) > 3 else []) + ([t[:-2]] if t.endswith("es") and len(t) > 4 else [])


def find(text, skip=(), year=None, names=True, limit=6):
    """Props the narration points at, best first: [{name, word, at, kind}]. kind 'name' = the word is a prop (or alias);
    'word' = found through the meaning table. `year` (or a year written in the text) removes props that did not exist."""
    low = str(text or "").lower()
    toks = re.findall(r"[a-z0-9']+", low)
    year = year if year is not None else year_in(low)
    skip = set(skip) | set(NEVER)
    found, seen = [], set()
    if names:
        covered = set()
        ph = phrases()
        for i in range(len(toks)):                           # "rosetta stone", "printing press", "statue of liberty"
            for n in (4, 3, 2):
                name = ph.get(" ".join(toks[i:i + n])) if i + n <= len(toks) else None
                if name and name not in skip and name not in seen and not covered & set(range(i, i + n)):
                    seen.add(name)
                    covered |= set(range(i, i + n))
                    found.append(dict(name=name, word=" ".join(toks[i:i + n]), at=i, kind="name"))
                    break
        for i, tok in enumerate(toks):
            if i in covered:
                continue
            for cand in _singular(tok)[:2]:
                name = NARRATION.get(cand) or R.PROP_ALIASES.get(cand, cand)
                if name in R.PROPS and name not in skip and _noun_ok(toks, i) and name not in seen:
                    seen.add(name)
                    found.append(dict(name=name, word=tok, at=i, kind="name"))
                    break
        found.sort(key=lambda h: h["at"])
    table = words()
    hits = []
    for i in range(len(toks)):
        for n in (3, 2, 1):
            if i + n > len(toks):
                continue
            gram = " ".join(toks[i:i + n])
            cands = [gram] + ([gram[:-1]] if n == 1 and gram.endswith("s") and len(gram) > 3 else [])
            for g in cands:
                name = table.get(g)
                if name and name not in skip and name not in seen and fits(name, year) and _noun_ok(toks, i):
                    seen.add(name)
                    hits.append(dict(name=name, word=g, at=i, kind="word", n=n))
                    break
    hits.sort(key=lambda h: (h["at"], -h["n"]))
    return (found + [{k: v for k, v in h.items() if k != "n"} for h in hits])[:limit]


def pick(text, skip=(), year=None, names=True):
    """The one prop that best shows `text`, or None. Exact prop names come first (in the order they appear), then meaning."""
    got = find(text, skip=skip, year=year, names=names, limit=1)
    return got[0]["name"] if got else None


def best(word, year=None):
    """The prop for a short phrase ("gunpowder", "a pair of duelling pistols"), or None."""
    return pick(word, year=year)


def covers(phrase, year=None):
    """The prop that really SHOWS `phrase`, or None. Stricter than `best`: a named object ("the Rosetta Stone", "Napoleon's
    bicorne") is covered only when its proper name is known to the index, so "stone" -> rocks does not stand in for it.
    This decides whether an AI drawing is still needed, and what the coverage check may add."""
    name = best(phrase, year=year)
    if not name:
        return None
    known = words()
    for proper in re.findall(r"\b[A-Z][a-z]{2,}\b", str(phrase or "")):
        low = proper.lower()
        if low not in known and R.PROP_ALIASES.get(low, low) not in R.PROPS and low not in STOP_PROPER:
            return None
    return name


STOP_PROPER = {"the", "his", "her", "their", "our", "your", "its", "king", "queen", "emperor", "great", "new", "old", "first",
               "second", "last", "american", "british", "french", "german", "spanish", "english", "roman", "greek"}


def for_word(word):
    return words().get(_norm(word)) or words().get(_norm(word).rstrip("s"))


def nearest(name):
    """Last resort for a prop name the writer made up: 'colonial_musketeer' -> musket. Looks at each part, then the pairs."""
    parts = [p for p in re.split(r"[_\s-]+", str(name or "").lower()) if p]
    for n in (2, 1):
        for i in range(len(parts) - n, -1, -1):
            gram = " ".join(parts[i:i + n])
            hit = for_word(gram)
            if hit and len(gram) >= 4:
                return hit
    return None


def words_for(prop, limit=12):
    """The words that mean `prop` (for the coverage check: a keg satisfies 'gunpowder')."""
    key = ("rev", prop)
    if key not in _cache:
        _cache[key] = [w for w, p in words().items() if p == prop and " " not in w][:limit]
    return _cache[key]


def concepts(prop):
    return [prop.replace("_", " ")] + words_for(prop)


# ---------------------------------------------------------------- what the library could not answer
def gaps_path():
    from ..config import DATA_DIR
    return os.path.join(DATA_DIR, "prop_gaps.json")


def _read_gaps():
    try:
        with open(gaps_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def note_gap(word, context=""):
    """Remember that a story wanted an object no prop shows. Never raises: this is bookkeeping."""
    w = _norm(re.sub(r"[^A-Za-z0-9' -]+", " ", str(word or "")))[:50]
    if len(w) < 3 or best(w):
        return False
    try:
        d = _read_gaps()
        e = d.setdefault(w, dict(n=0, seen=[]))
        e["n"] = int(e.get("n", 0)) + 1
        ctx = re.sub(r"\s+", " ", str(context or "")).strip()[:100]
        if ctx and ctx not in e["seen"] and len(e["seen"]) < 3:
            e["seen"].append(ctx)
        os.makedirs(os.path.dirname(gaps_path()), exist_ok=True)
        tmp = gaps_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, gaps_path())
        return True
    except OSError:
        return False


def gaps(limit=40):
    """[(word, times wanted, example sentence)] for objects no prop answers yet, most wanted first. A word the library
    learned about since is not listed."""
    d = _read_gaps()
    rows = [(w, int(e.get("n", 0)), (e.get("seen") or [""])[0]) for w, e in d.items() if not best(w)]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows[:limit]


def clear_gaps(done=()):
    d = _read_gaps()
    for w in done:
        d.pop(w, None)
    try:
        with open(gaps_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def stats():
    """Counts for the setup check and the website."""
    return dict(builtin=len(R.PROPS) - len(PL.LIBRARY) - len(PL.VARIANTS) - 1, shipped=sum(1 for d in PL.LIBRARY.values() if d["source"] == "shipped"),
                drawn=sum(1 for d in PL.LIBRARY.values() if d["source"] == "user"), variants=len(PL.VARIANTS), words=len(words()),
                gaps=len(gaps(1000)))
