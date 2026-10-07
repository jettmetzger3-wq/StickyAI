"""The scene pattern library and its retriever.

patterns.json holds reusable scene templates ("a document is signed", "an army marches across a map", ...): when they
apply, which slots they take (who, doc title, quote...), the visual sequence, camera, timing and transitions. The
retriever scores them against a beat's local analysis, so the studio can say "this narration resembles a signing
scene" without asking an AI, and so the director prompt only has to list the few candidates that fit each beat.

The artwork itself is made by composer.py; patterns carry the production LOGIC, never anyone's frames or characters.
"""
import functools
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOM = "CUSTOM"           # "none of these fit": the full storyboard writer (or a rule scene) draws it
CONFIDENT = 3.0             # a pattern scoring at least this is used without asking the AI


@functools.lru_cache(maxsize=1)
def load():
    """The built-in patterns plus the ones you added with `python -m studio research learn` (same id = yours wins)."""
    with open(os.path.join(HERE, "patterns.json"), encoding="utf-8") as f:
        data = json.load(f)
    try:
        from ..config import DATA_DIR
        with open(os.path.join(DATA_DIR, "knowledge", "patterns_user.json"), encoding="utf-8") as f:
            mine = {p["id"]: p for p in json.load(f).get("patterns", []) if p.get("id") and p.get("layout")}
        if mine:
            data = dict(data, patterns=[mine.pop(p["id"], p) for p in data["patterns"]] + list(mine.values()))
    except (OSError, ValueError):
        pass
    return data


def version():
    return int(load().get("version", 1))


@functools.lru_cache(maxsize=1)
def by_id():
    return {p["id"]: p for p in load()["patterns"]}


def get(pid):
    return by_id().get(str(pid or "").upper())


def ids():
    return list(by_id())


def _need_ok(need, a):
    """(met, weight): whether the beat has what the pattern needs."""
    places = a.get("places") or []
    return {
        "person": bool(a.get("people")),
        "person_new": bool(a.get("intro")),
        "two_people": len(a.get("people") or []) + len(a.get("groups") or []) >= 2,
        "document": bool(a.get("documents")),
        "number": bool(a.get("numbers")),
        "country": any(p.get("kind") == "country" for p in places),
        "city": any(p.get("kind") == "city" for p in places),
        "two_places": len(places) >= 2,
        "years2": len(a.get("years") or []) >= 2,
        "place_or_year": bool(places or a.get("years")),
    }.get(need, True)


def score(pattern, a, recent=()):
    t = pattern["triggers"]
    low = str(a.get("text") or "").lower()
    s = 0.0
    for ev in t.get("events", []):
        if ev in (a.get("events") or []):
            s += 3.0
    for w in t.get("words", []):
        if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
            s += 1.6 if " " in w else 1.1
    kinds = {d.get("kind") for d in a.get("documents") or []}
    for d in t.get("docs", []):
        if d in kinds:
            s += 2.0
    for need in t.get("needs", []):
        s += 0.8 if _need_ok(need, a) else -4.0
    if a.get("emotion") in pattern.get("tone", []) or (a.get("mood") == "somber" and "tragedy" in pattern.get("tone", [])):
        s += 0.7
    if a.get("mood") == "somber" and "tragedy" not in pattern.get("tone", []) and "tension" not in pattern.get("tone", []):
        s -= 1.0                                  # no jokes or parades on a somber beat
    if pattern["id"] in list(recent)[-2:]:
        s -= 1.6                                  # don't repeat the same picture twice in a row
    elif recent and by_id().get(list(recent)[-1], {}).get("layout") == pattern["layout"]:
        s -= 0.8
    return s * float(pattern.get("prior", 1.0)) * (1.1 if pattern.get("verified") else 1.0)     # checked patterns win ties


def match(a, recent=(), k=3):
    """[(pattern, score)] best first, only those that actually have some evidence."""
    scored = [(p, score(p, a, recent)) for p in load()["patterns"]]
    scored = [(p, s) for p, s in scored if s > 0.9]
    scored.sort(key=lambda ps: -ps[1])
    return scored[:k]


def best(a, recent=()):
    """(pattern id, score) for the best pattern, or (CUSTOM, 0)."""
    m = match(a, recent, 1)
    return (m[0][0]["id"], m[0][1]) if m else (CUSTOM, 0.0)


def catalog_text(only=None, with_slots=True):
    """The pattern list as it goes into the director prompt (one short line each)."""
    lines = []
    for p in load()["patterns"]:
        if only is not None and p["id"] not in only:
            continue
        slots = ", ".join(p["slots"]) if with_slots else ""
        lines.append(f"{p['id']}: {p['when']}" + (f"  [slots: {slots}]" if slots else ""))
    return "\n".join(lines)
