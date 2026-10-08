"""The world state: one persistent picture of "where and when are we, and who is here" that every scene updates and the
next scene inherits, so the video behaves like one continuous world instead of unrelated slides.

Tracked after every scene: the period (year and era), the location (name, kind of place, region), who is on stage and
where, which props and groups are around, the event in progress, the camera state and the narrative purpose. The
snapshots go to projects/<slug>/world_state.json; the director prompt gets the last few as "story so far", the composer
inherits the year (so "Roosevelt" means the right Roosevelt) and the review flags time jumps nothing explained.
"""
import copy
import re

FLASHBACK = re.compile(r"\b(earlier|before that|back in|years before|rewind|flashback|ago|long before|previously|had been)\b", re.I)
TIME_PASSES = re.compile(r"\b(later|years|decades?|century|centuries|after|then|by the time|eventually|finally|next|following|until)\b", re.I)


def blank():
    return dict(period=dict(year=None, era=""), location=dict(name="", kind="", region=""), characters=[], props=[], groups=[],
                event="", camera="wide", narrative=dict(purpose="", visual=""), pattern="", style="doodle")


def era(year):
    if year is None:
        return ""
    y = int(year)
    return ("antiquity" if y < 500 else "the Middle Ages" if y < 1500 else "the early modern era" if y < 1800 else
            "the 19th century" if y < 1900 else "the early 20th century" if y < 1945 else "the mid 20th century" if y < 1990 else
            "the late 20th century" if y < 2000 else "the 21st century")


def _side(x):
    return "left" if x < 700 else "right" if x > 1220 else "center"


def update(prev, scene, a, beat, pattern=""):
    """The world after `scene` (a new dict; `prev` is the world before it)."""
    w = copy.deepcopy(prev) if prev else blank()
    a = a or {}
    beat = beat or {}
    ctx = a.get("context") or {}
    years = a.get("years") or []
    year = years[0] if years else ctx.get("year") or w["period"].get("year")
    w["period"] = dict(year=year, era=era(year))
    bg = (scene or {}).get("bg") or {}
    els = (scene or {}).get("elements") or []
    banner = next((e.get("text") for e in els if e.get("type") == "text" and e.get("y", 999) < 200 and e.get("text")), "")
    name = beat.get("location") or (banner if banner and not re.fullmatch(r"\d{3,4}", str(banner).strip()) else "") or \
        next((p["name"] for p in a.get("places") or [] if p.get("role") != "origin"), "") or w["location"].get("name")
    mp = a.get("map") or {}
    w["location"] = dict(name=name, kind=bg.get("type") or "", region=mp.get("region") or w["location"].get("region") or "")
    w["characters"] = [dict(name=e.get("who") or e.get("kind"), kind=e.get("kind"), side=_side(float(e.get("x") or 960)))
                       for e in els if e.get("type") == "char" and not e.get("narrator")][:8]
    w["props"] = [e.get("name") for e in els if e.get("type") == "prop"][:8]
    crowds = [e.get("who") for e in els if e.get("type") == "crowd" and e.get("who")]
    groups = list(dict.fromkeys(crowds + list(a.get("groups") or []) + [g for g in w.get("groups", [])]))[:6]
    w["groups"] = groups
    w["event"] = ctx.get("id") or next(iter(a.get("frames") or []), "") or w.get("event", "")
    w["camera"] = "map" if bg.get("type") == "map" else "close-up" if ((scene or {}).get("camera") or {}).get("shots") else "wide"
    w["narrative"] = dict(purpose=beat.get("purpose", ""), visual=beat.get("visual", ""))
    w["pattern"] = pattern
    return w


def line(world_by_beat, i, n=2):
    """'Story so far' for the director prompt."""
    out = []
    for k in range(max(0, i - n), i):
        w = world_by_beat.get(k) or world_by_beat.get(str(k))
        if w:
            out.append(f"[{k}] {w['location'].get('name') or w['location'].get('kind') or '?'}"
                       + (f", {w['period']['year']}" if w["period"].get("year") else "")
                       + (f"; with {', '.join(str(c['name']) for c in w['characters'][:3])}" if w["characters"] else "")
                       + (f"; {w['event'].replace('_', ' ')}" if w.get("event") else ""))
    return "\n".join(out)


def check(worlds, beats, scenes):
    """Time jumps nothing explained. worlds {i: world}. Returns issue dicts (merged into the review)."""
    issues = []
    last_year, last_i = None, None
    for i in sorted(worlds):
        if i >= len(beats) or beats[i].get("host"):
            continue
        y = worlds[i]["period"].get("year")
        text = beats[i].get("text", "")
        if y is not None and last_year is not None and y != last_year:
            shows_year = str(y) in " ".join(str(e.get("text", "")) for e in (scenes.get(i) or {}).get("elements", []))
            if y < last_year - 5 and not FLASHBACK.search(text) and not shows_year:
                issues.append(dict(beat=i, check="continuity", severity="medium", fixed=False,
                                   msg=f"the story jumps back from {last_year} to {y} with nothing saying it is a flashback"))
            elif y > last_year + 40 and not TIME_PASSES.search(text) and not shows_year:
                issues.append(dict(beat=i, check="continuity", severity="low", fixed=False,
                                   msg=f"{y - last_year} years pass between this scene and the one before with no date or phrase saying so"))
        if y is not None:
            last_year, last_i = y, i
    return issues
