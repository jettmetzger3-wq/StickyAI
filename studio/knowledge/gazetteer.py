"""Named cities and battle sites with their map position, so the studio can mark them on a map, draw the right
skyline, and tell "New York" from a person's name."""
import functools
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SKYLINE_KEYS = {"amsterdam": "amsterdam", "athens": "athens", "beijing": "beijing", "peking": "beijing", "berlin": "berlin",
                "cairo": "cairo", "delhi": "delhi", "constantinople": "istanbul", "istanbul": "istanbul", "london": "london",
                "moscow": "moscow", "new york": "newyork", "paris": "paris", "rome": "rome", "san francisco": "sanfrancisco",
                "sydney": "sydney", "tokyo": "tokyo", "washington d.c.": "washington", "kremlin": "moscow"}


@functools.lru_cache(maxsize=1)
def load():
    with open(os.path.join(HERE, "gazetteer.json"), encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def _index():
    idx = {}
    for e in load():
        for n in [e["name"].lower()] + list(e.get("aliases") or []):
            idx[n] = e
    return idx


@functools.lru_cache(maxsize=1)
def _rx():
    names = sorted(_index(), key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z])", re.I)


def find(name):
    return _index().get(str(name or "").strip().lower())


def find_in_text(text):
    """Each named place in the text once, in order: dicts with name, lon, lat, country, skyline."""
    seen, out = set(), []
    for m in _rx().finditer(str(text or "")):
        e = _index()[m.group(1).lower()]
        if e["name"] not in seen:
            seen.add(e["name"])
            out.append(dict(e, skyline=SKYLINE_KEYS.get(e["name"].lower()) or SKYLINE_KEYS.get(m.group(1).lower()),
                            shown=m.group(1)))
    return out
