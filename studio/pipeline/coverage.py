"""Narration-to-visual coverage: choose the scene that SHOWS what the narrator says, repair it locally, and score it.

The director's plan picks a pattern; the studio's meaning layer (knowledge/semantics.py) says what the picture must
communicate. This module composes the plausible candidates (the plan's pattern, the pattern the meaning pins down, the
local best match), scores each against the requirements and keeps the one that covers most. If even that one falls short
it tries every pattern, then patches what is still missing (a person, a number, a place or date, a group). What is left
is reported as a failed scene: the review blocks it from rendering and, in Normal and Deep modes, hands only those
scenes back to the writer in one batched request.
"""
import copy

from ..knowledge import composer as CO, patterns as PT, propindex as PX, semantics as SM
from . import review as RV

FAIL = SM.COVERAGE_FAIL
BLOCK = SM.COVERAGE_BLOCK


def _compose(pid, beat, a, slots, cast, idx, state, title):
    c = CO.Ctx(cast=cast, idx=idx, state=copy.deepcopy(state or {}), title=title)
    sc = CO.compose(PT.get(pid), beat, a, slots, c)
    return sc, c.state


def choose(entry, beat, a, reqs, cast, idx, state, title, local_best):
    """Compose the candidates and keep the best-covering one.
    Returns dict(scene, pattern, state, coverage, tried=[(pattern, score)]) or None when nothing could be composed."""
    slots = (entry or {}).get("slots") or {}
    order = []
    planned = entry["pattern"] if entry else None
    hint = SM.pattern_hint(a)
    for pid in (planned, hint, local_best[0] if local_best and local_best[1] >= PT.CONFIDENT else None):
        if pid and pid != PT.CUSTOM and pid not in order:
            order.append(pid)
    if planned == PT.CUSTOM and not hint:
        return None                                       # the director wants the full scene writer for this one
    if not order:
        order = ["STORY_MOMENT"]
    tried, best = [], None
    for pid in order:
        sc, st = _compose(pid, beat, a, slots if pid == planned else {}, cast, idx, state, title)
        if sc is None:
            continue
        cov = SM.coverage(reqs, sc)
        tried.append((pid, cov["score"]))
        if best is None or cov["score"] > best["coverage"]["score"] + 1e-9:
            best = dict(scene=sc, pattern=pid, state=st, coverage=cov)
    if (best is None or best["coverage"]["score"] < FAIL) and reqs:
        for p in PT.load()["patterns"]:                   # local search: any pattern that covers the narration better
            pid = p["id"]
            if pid in order or pid in (PT.CUSTOM, "STORY_MOMENT"):
                continue
            sc, st = _compose(pid, beat, a, {}, cast, idx, state, title)
            if sc is None:
                continue
            cov = SM.coverage(reqs, sc)
            tried.append((pid, cov["score"]))
            if best is None or cov["score"] > best["coverage"]["score"] + 1e-9:
                best = dict(scene=sc, pattern=pid, state=st, coverage=cov)
    if best:
        best["tried"] = tried
    return best


# ------------------------------------------------------------------ patching what is still missing
def patch(scene, cov, a, registry):
    """Add what a plain addition can add: a missing person or group, a number, a place/date line. Returns the list of
    things added. (A missing map region or document can't be patched in: a different pattern has to be chosen. A missing
    object is looked up in the prop index; when no prop shows it, it is written to the gap list instead.)"""
    added = []
    people = {SM.canon(p["name"]): p for p in a.get("people") or []}
    for m in cov["missing"]:
        k = m["kind"]
        if k == "person":
            p = people.get(SM.canon(m["value"])) or next((q for c_, q in people.items() if c_ in SM.canon(m["value"]) or SM.canon(m["value"]) in c_), None)
            if p is None:
                p = dict(name=m["value"], kind="civ", known=False)
            if RV.add_person(scene, p, registry, a):
                added.append(f"added {m['value']}")
        elif k == "group":
            if RV.add_person(scene, dict(name=str(m["value"]).title(), kind="army", known=False), registry, a, label=False):
                added.append(f"added {m['value']}")
        elif k == "number":
            n = next(iter(a.get("numbers") or []), None)
            if n and len(scene.get("elements") or []) <= 9:
                v = n["value"]
                big = v >= 1e6
                scene.setdefault("elements", []).append(
                    {"type": "counter", "from": 0, "to": round(v / (1e9 if v >= 1e9 else 1e6), 1) if big else round(v), "x": 960, "y": 230,
                     "size": 90, "format": "number", "prefix": "$" if n["kind"] == "money" else "",
                     "suffix": (" billion" if v >= 1e9 else " million" if big else "") + ("%" if n["kind"] == "percent" else ""),
                     "at": 0.3, "dur": 1.5, "color": "red" if n["kind"] == "casualty" else "navy"})
                added.append(f"showed the number {n['shown']}")
        elif k == "object":
            name = PX.covers(m["value"], year=(a.get("years") or [None])[0])
            if name and RV.add_prop(scene, name, a.get("text", "")):
                added.append(f"showed the {name.replace('_', ' ')} ({m['value']})")
            elif not name:
                PX.note_gap(m["value"], a.get("text", ""))
        elif k in ("time", "place") and not any(e.get("type") == "text" and e.get("y", 999) < 200 for e in scene.get("elements") or []):
            if scene.get("bg", {}).get("type") != "map":
                scene.setdefault("elements", []).insert(0, CO.text(str(m["value"])[:30], CO.MID, 105, 70, "navy", at=0.0))
                added.append(f"added the line '{m['value']}'")
    return added


def check(i, scene, a, reqs, registry, out):
    """The QC step for one scene: score, patch what can be patched, re-score; log it. Returns the final coverage dict."""
    cov = SM.coverage(reqs, scene)
    if cov["missing"]:
        added = patch(scene, cov, a, registry)
        if added:
            cov = SM.coverage(reqs, scene)
            RV.issue(out, i, "coverage", "low", "added to match the narration: " + "; ".join(added), fixed=True)
    if cov["score"] < FAIL:
        gone = "; ".join(f"{m['value']} ({m['kind']})" for m in cov["must_missing"][:4]) or "several details"
        sev = "high" if cov["score"] < BLOCK else "medium"
        RV.issue(out, i, "coverage", sev, f"the picture covers {cov['score']:.0%} of what the narration needs; missing: {gone}")
    return cov


def summary(covs):
    """{scores...} for the review report from {beat: coverage}."""
    vals = [c["score"] for c in covs.values()]
    return dict(mean=round(sum(vals) / len(vals), 3) if vals else 1.0, failed=[i for i, c in covs.items() if c["score"] < FAIL],
                blocked=[i for i, c in covs.items() if c["score"] < BLOCK])
