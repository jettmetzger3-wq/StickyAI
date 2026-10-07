"""Historical people: who they were and how a stickman version of them looks.

The look (hat, hat color, coat, beard) is chosen once and reused in every scene of a video AND in every later video, so
Washington is the same blue-coated stickman in a tricorn hat everywhere. people.json has the starting looks of ~85 well
known figures. The first time a video uses a person the look it used is remembered in the cache, so a look you edited
in a script's cast survives into the next video.
"""
import json
import os
import re
import functools

from .. import cache

HERE = os.path.dirname(os.path.abspath(__file__))


@functools.lru_cache(maxsize=1)
def load():
    with open(os.path.join(HERE, "people.json"), encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def _index():
    """lower-case name -> [entries]; longer names first when matching text."""
    idx = {}
    for e in load():
        for n in e["names"]:
            idx.setdefault(n.lower(), []).append(e)
    return idx


def norm(name):
    return re.sub(r"[^a-z0-9. ]+", "", str(name or "").lower()).strip()


def _by_year(entries, year):
    """Among people who share a name (the two Roosevelts), the one who was in his prime around `year`."""
    if year is None or len(entries) == 1:
        return entries[0]

    def score(e):
        if e["born"] + 20 <= year <= e["died"] + 5:
            return abs(year - (e["born"] + 45))
        return 1000 + min(abs(year - e["born"]), abs(year - e["died"]))
    return min(entries, key=score)


def find(name, year=None):
    """The known person a name refers to ("Washington", "General Washington", "Napoleon Bonaparte"), or None."""
    n = norm(name)
    if not n:
        return None
    idx = _index()
    if n in idx:
        return _by_year(idx[n], year)
    # "President Lincoln" / "King Louis XVI": try every suffix of the words, e.g. "lincoln"
    words = n.split()
    for i in range(1, len(words)):
        tail = " ".join(words[i:])
        if tail in idx:
            return _by_year(idx[tail], year)
    for i in range(1, len(words)):
        head = " ".join(words[:-i])
        if head in idx and len(head) > 5:
            return _by_year(idx[head], year)
    return None


@functools.lru_cache(maxsize=1)
def _name_regex():
    names = sorted({n for n in _index() if len(n) >= 4}, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.I)


def find_in_text(text, year=None):
    """[(entry, matched text)] for every known person mentioned in `text`, in order, each person once."""
    seen, out = set(), []
    for m in _name_regex().finditer(str(text or "")):
        e = find(m.group(1), year)
        if e and e["id"] not in seen:
            seen.add(e["id"])
            out.append((e, m.group(1)))
    return out


def look(entry):
    """The stickman look for a person: the remembered one if a video changed it, else the default."""
    saved = cache.get("people", cache.key("look", entry["id"]))
    base = {k: entry.get(k, "") for k in ("kind", "hat_color", "coat", "look")}
    if isinstance(saved, dict):
        base.update({k: v for k, v in saved.items() if k in base})
    return base


def remember(entry_id, look_dict):
    """Keep the look a video ended up using for this person (so the next video starts from it)."""
    keep = {k: look_dict.get(k, "") for k in ("kind", "hat_color", "coat", "look")}
    return cache.put("people", cache.key("look", entry_id), keep, dict(id=entry_id))


def cast_entry(entry, name=None):
    """A script-cast / character-registry entry for a known person."""
    lk = look(entry)
    return dict(id=entry["id"], name=name or entry["name"], kind=lk["kind"], hat_color=lk["hat_color"], coat=lk["coat"],
                look=lk["look"], role=entry["role"], period=f"{entry['born']} to {entry['died']}",
                trait=entry["trait"], known=True)
