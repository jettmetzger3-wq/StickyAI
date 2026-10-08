"""The muted-video test: could a viewer follow the story with the sound off?

For every scene it asks five plain questions about the picture alone: WHO is in it, WHERE are we, WHAT is happening,
WHEN is it, and what CHANGED since the scene before. The answers come from what the scene JSON actually contains (named
characters and labelled groups, the place or map, props/arrows/counters/actions, a date, how different it is from the
previous picture), so it costs no AI call. A scene that answers fewer than three of the five is flagged. The visuals do
not have to repeat every word, but they must not be unrelated to the narration.
"""
from ..knowledge import semantics as SM

GENERIC_BG = ("paper", "sunburst", "dark", "ground")


def _who(sc, a):
    els = sc.get("elements") or []
    named = [e for e in els if e.get("type") in ("char", "crowd") and (e.get("who") or e.get("narrator"))]
    labelled = [e for e in els if e.get("type") in ("territory", "city") or (e.get("type") == "text" and (e.get("lon") is not None or e.get("y", 999) < 260))]
    nobody_needed = not (a.get("people") or a.get("groups")) and sc.get("bg", {}).get("type") == "map"
    return bool(named or labelled or nobody_needed)


def _where(sc):
    bg = sc.get("bg") or {}
    els = sc.get("elements") or []
    if bg.get("type") == "map":
        return bool(bg.get("labels") or any(e.get("type") in ("territory", "city", "arrow") or e.get("lon") is not None for e in els))
    if bg.get("type") not in GENERIC_BG:
        return True
    return any(e.get("type") in ("text", "board", "sign") and e.get("y", 999) < 260 for e in els)


def _what(sc):
    els = sc.get("elements") or []
    if any(e.get("type") in ("arrow", "counter", "chart", "timeline", "battle", "compare", "front", "route", "territory") for e in els):
        return True
    if any(e.get("type") == "prop" and e.get("name") not in ("check",) for e in els):
        return True
    return any(e.get("do") or e.get("say") or e.get("pose") not in (None, "stand", "down") for e in els if e.get("type") in ("char", "crowd"))


def _when(sc, world, prev_world):
    els = sc.get("elements") or []
    txt = " ".join(str(e.get("text", "")) for e in els if e.get("type") in ("text", "note", "board")) + " ".join(
        str(it.get("year", "")) for e in els if e.get("type") == "timeline" for it in e.get("events") or [])
    y = world["period"].get("year") if world else None
    if y is not None and str(y) in txt:
        return True
    prev_y = prev_world["period"].get("year") if prev_world else None
    return y is None or (prev_y is not None and abs(y - prev_y) <= 5)        # the viewer already knows the year


def _changed(S, prevS, i):
    if prevS is None:
        return True
    union = S | prevS
    return not union or (1 - len(S & prevS) / len(union)) >= 0.3


def run(scenes, analyses, beats, worlds=None, coverage=None):
    """Returns dict(score, per_scene={i: {who,where,what,when,change,score}}, weak=[beats]) over the non-host scenes."""
    worlds = worlds or {}
    per, prevS, prev_i = {}, None, None
    for i in sorted(scenes):
        sc = scenes[i]
        if not isinstance(sc, dict) or i >= len(beats) or beats[i].get("host"):
            continue
        a = analyses[i] if i < len(analyses) else {}
        S = SM.scene_concepts(sc)
        ans = dict(who=_who(sc, a), where=_where(sc), what=_what(sc), when=_when(sc, worlds.get(i), worlds.get(prev_i) if prev_i is not None else None),
                   change=_changed(S, prevS, i))
        score = sum(ans.values()) / 5
        if coverage and str(i) in coverage and coverage[str(i)] < SM.COVERAGE_FAIL:
            score = min(score, 0.4)                      # a picture that doesn't match the narration can't tell the story
        per[i] = dict(ans, score=round(score, 2))
        prevS, prev_i = S, i
    vals = [v["score"] for v in per.values()]
    return dict(score=round(sum(vals) / len(vals), 3) if vals else 1.0, per_scene={str(k): v for k, v in per.items()},
                weak=[k for k, v in per.items() if v["score"] < 0.6],
                questions=["who is in it", "where are we", "what is happening", "when is it", "what changed since the last scene"])
