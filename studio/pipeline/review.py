"""Storyboard QC: check every scene BEFORE the expensive part (voice and rendering), and fix what can be fixed locally.

Checks: narration match, historical match, continuity, character consistency, prop quality, action, camera, pacing,
emotional match, redundancy, and AI usage. Each issue is {beat, check, severity (low|medium|high), msg, fixed}.
Almost everything is fixed here with plain code (no AI): a document with no text gets its real text, a missing number
gets a counter, a tank in 1776 is removed. What is left unfixed is listed in review.json, and (deep mode only) can be
handed back to the writer for just those scenes.
"""
import re

from ..engine import layout as LY
from ..engine.registry import PROPS
from ..knowledge import composer as CO, propindex as PX, props_intel as PI
from . import continuity as CT

CHECKS = ("narration", "coverage", "history", "continuity", "characters", "props", "action", "camera", "layout", "pacing", "emotion",
          "redundancy", "usage")
# the first year a prop can appear in a story without being an anachronism (the table lives with the prop index)
ERA_PROPS = PX.ERA_FIRST
ERA_KINDS = {"astronaut": 1961, "pilot": 1903, "hardhat": 1890, "headphones": 1958, "student": 1700, "marine": 1775}
SOMBER_BAD = ("trophy", "dove_party", "cheer")


def texts_of(sc):
    out = []
    for el in (sc or {}).get("elements") or []:
        for k in ("text", "title", "label"):
            if el.get(k):
                out.append(str(el[k]))
        for k in ("lines",):
            out += [str(x) for x in el.get(k) or []]
        for s in el.get("say") or []:
            out.append(str(s.get("text") if isinstance(s, dict) else s))
        p = el.get("params") or {}
        for k in ("title", "label", "sub"):
            if p.get(k):
                out.append(str(p[k]))
        t = p.get("text")
        out += [str(x) for x in (t if isinstance(t, list) else [t])] if t else []
        for it in el.get("items") or []:
            out.append(str(it.get("label", "")))
        for ev in el.get("events") or []:
            out.append(str(ev.get("year", "")) + " " + str(ev.get("label", "")))
        if el.get("type") == "counter":
            out.append(f"{el.get('prefix', '')}{el.get('to')}{el.get('suffix', '')}")
    return " ".join(out).lower()


def has_type(sc, *types):
    return any(e.get("type") in types for e in (sc or {}).get("elements") or [])


def props_of(sc):
    return [e.get("name") for e in (sc or {}).get("elements") or [] if e.get("type") == "prop"]


def issue(out, beat, check, severity, msg, fixed=False):
    out.append(dict(beat=beat, check=check, severity=severity, msg=msg, fixed=fixed))


def _words(s):
    return [w for w in re.findall(r"[a-z]{4,}", str(s).lower())]


# ------------------------------------------------------------------ the per-scene checks
FREE_X = (1700, 260, 1450, 1000, 700)


def _taken(sc):
    """x ranges already used by characters and crowds."""
    spans = []
    for e in sc.get("elements") or []:
        if e.get("type") == "char":
            spans.append((e.get("x", 960) - 160, e.get("x", 960) + 160))
        elif e.get("type") == "crowd":
            w = e.get("width", 600) / 2
            spans.append((e.get("x", 960) - w, e.get("x", 960) + w))
    return spans


def _free_x(sc):
    spans = _taken(sc)
    for x in FREE_X:
        if not any(a_ <= x <= b_ for a_, b_ in spans):
            return x
    return None


def add_person(sc, p, registry, a, label=True):
    """Put a missing person (or group) into the scene at a free spot, small, with a name tag when it is their first time."""
    x = _free_x(sc)
    if x is None or len([e for e in sc.get("elements") or [] if e.get("type") in ("char", "crowd")]) >= 5:
        return False
    cast = [{k: e.get(k, "") for k in ("name", "kind", "hat_color", "coat", "look")} for e in registry or []]
    c = CO.Ctx(cast=cast)
    group = p.get("kind") not in (None, "civ", "") and not p.get("known") and p["name"].lower().endswith("s")
    if group:
        el = CO.crowd(c, p["name"], x, 925, 6, 380, 0.5, rows=1, at=0.25, flip=x > 960)
    else:
        el = CO.person(c, p["name"], x, CO.FEET, 0.8, flip=x > 960, at=0.25, year=(a.get("years") or [None])[0])
    sc.setdefault("elements", []).append(el)
    if label and not group and p["name"] in (a.get("intro") or []):
        sc["elements"].append(CO.text(p["name"].upper()[:22], x, 640, 44, "navy", at=0.3))
    return True


PROP_SPOTS = ((1560, 860), (360, 860), (960, 880), (1700, 700), (220, 700), (1250, 760))


def add_prop(sc, name, text=""):
    """Put a prop the narration needs into the scene at the first free spot where it creates no new medium/high layout
    problem. Returns True when it was added. Never makes a scene worse: if every spot clashes, nothing is added."""
    if name not in PROPS or len(sc.get("elements") or []) >= 12:
        return False
    ctx = dict(text=text)
    base = len([x for x in LY.audit(sc, ctx) if x["sev"] in ("high", "medium")])
    anchor = PROPS[name][0]
    for x, y in PROP_SPOTS:
        el = CO.prop(name, x, y if anchor == "bottom" else y - 200, 0.8, at=0.3)
        trial = dict(sc, elements=list(sc.get("elements") or []) + [el])
        if len([f for f in LY.audit(trial, ctx) if f["sev"] in ("high", "medium")]) <= base:
            sc.setdefault("elements", []).append(el)
            return True
    return False


def check_narration(i, sc, a, out, registry=None):
    """Does every important narration point have a visual? Returns (matched, expected)."""
    txt = texts_of(sc)
    chars = [e for e in sc.get("elements") or [] if e.get("type") in ("char", "crowd")]
    expect = matched = 0
    for p in (a.get("people") or [])[:3]:
        expect += 1
        keys = {p["name"].lower()} | {w for w in _words(p["name"])}
        kinds = {str(c.get("kind")) for c in chars}
        if any(str(c.get("who") or "").lower() in keys or any(k in str(c.get("who") or "").lower() for k in keys) for c in chars) \
                or any(k in txt for k in keys) or (p.get("cast") and p.get("kind") not in (None, "civ", "") and p.get("kind") in kinds):
            matched += 1
        else:
            issue(out, i, "narration", "medium", f"{p['name']} is in the narration but not in the picture")
            if add_person(sc, p, registry, a):
                out[-1]["fixed"] = True
                out[-1]["msg"] += ": added them to the scene"
    for d in (a.get("documents") or [])[:1]:
        expect += 1
        names = set(_words(d["name"])) if d["name"] else set()
        if any(n in txt for n in names) or (not names and any(x in props_of(sc) for x in ("document", "scroll", "newspaper", "envelope"))):
            matched += 1
        else:
            issue(out, i, "narration", "medium", f"the {d['name'] or d['kind']} is mentioned but not shown")
            if len(sc.get("elements") or []) <= 8:
                dd = PI.doc_for(a)
                sc.setdefault("elements", []).append(CO._doc_el(dd, 1500, 480, 1.8, 0.2))
                out[-1]["fixed"] = True
    for n in (a.get("numbers") or [])[:1]:
        expect += 1
        digits = re.sub(r"\D", "", n["shown"])
        if has_type(sc, "counter", "chart", "compare", "icons") or (digits and digits[:3] in re.sub(r"\D", "", txt)):
            matched += 1
        else:
            issue(out, i, "narration", "medium", f"the number {n['shown']} is mentioned but never shown")
            if len(sc.get("elements") or []) <= 9:
                v = n["value"]
                big = v >= 1e6
                sc.setdefault("elements", []).append(
                    {"type": "counter", "from": 0, "to": round(v / (1e9 if v >= 1e9 else 1e6), 1) if big else round(v), "x": 960, "y": 230,
                     "size": 90, "format": "number", "prefix": "$" if n["kind"] == "money" else "",
                     "suffix": (" billion" if v >= 1e9 else " million" if big else "") + ("%" if n["kind"] == "percent" else ""),
                     "at": 0.3, "dur": 1.5, "color": "red" if n["kind"] == "casualty" else "navy"})
                out[-1]["fixed"] = True
    for pl in [p for p in (a.get("places") or []) if p["kind"] == "city"][:1]:
        expect += 1
        bg = sc.get("bg") or {}
        if bg.get("type") == "map" or pl["name"].lower() in txt or (bg.get("skyline") and pl.get("skyline") == bg.get("skyline")) \
                or has_type(sc, "city"):
            matched += 1
        else:
            issue(out, i, "narration", "low", f"{pl['name']} is mentioned but nothing says where we are")
            if not any(e.get("type") == "text" and e.get("y", 999) < 200 for e in sc.get("elements") or []):
                yr = (a.get("years") or [None])[0]
                sc.setdefault("elements", []).insert(0, CO.text(", ".join(str(x) for x in (pl["name"], yr) if x), 960, 105, 70, "navy", at=0.0))
                out[-1]["fixed"] = True
    return matched, expect


def check_history(i, sc, a, year, out):
    if year is None:
        return
    els = sc.get("elements") or []
    for e in list(els):
        if e.get("type") == "prop" and (PX.first_year(e.get("name")) or 0) > year + 8:
            issue(out, i, "history", "high", f"a {e['name']} did not exist yet in {year}: removed", fixed=True)
            els.remove(e)
        elif e.get("type") in ("char", "crowd") and ERA_KINDS.get(e.get("kind"), 0) > year + 8:
            issue(out, i, "history", "medium", f"a '{e['kind']}' outfit is out of place in {year}: made a plain person", fixed=True)
            e["kind"] = "civ"


def check_props(i, sc, a, out):
    for e in sc.get("elements") or []:
        if e.get("type") != "prop":
            continue
        p = e.setdefault("params", {}) if e.get("name") in ("document", "scroll", "newspaper") else e.get("params") or {}
        name = e.get("name")
        if name in ("document", "scroll") and not (p.get("title") or p.get("text")) and float(e.get("scale") or 1) >= 1.2:
            d = PI.doc_for(a)
            p.update(title=d["title"], text=d["lines"])
            issue(out, i, "props", "medium", f"the {name} was blank: wrote its text ({d['title']})", fixed=True)
        elif name == "newspaper" and not p.get("label"):
            p.update(label=PI.headline_for(a), title=p.get("title") or "THE DAILY NEWS")
            issue(out, i, "props", "medium", f"the newspaper had no headline: wrote '{p['label']}'", fixed=True)
        elif name in ("crate", "gravestone", "podium") and not p.get("label") and name == "crate" and float(e.get("scale") or 1) >= 0.8:
            pass


def check_action(i, sc, a, out):
    chars = [e for e in sc.get("elements") or [] if e.get("type") == "char" and not e.get("narrator")]
    if not chars:
        return
    moving = any(e.get("do") or e.get("say") or e.get("act") for e in sc.get("elements") or [] if e.get("type") in ("char", "crowd"))
    movers = any(e.get("do") or e.get("idle") or e.get("move") for e in sc.get("elements") or [] if e.get("type") == "prop")
    if not moving and not movers:
        main = max(chars, key=lambda e: float(e.get("scale") or 1))
        act = {"tragedy": "cry", "triumph": "cheer", "shock": "surprise", "tension": "angry", "humor": "laugh"}.get(a.get("emotion"), "point")
        main["do"] = [{"act": act, "at": 0.3}]
        issue(out, i, "action", "low", f"everyone was standing still: gave the main character a '{act}'", fixed=True)


def check_camera(i, sc, a, out):
    cam = sc.get("camera")
    key = has_type(sc, "counter") or any(n in ("document", "scroll", "newspaper") for n in props_of(sc))
    if key and not cam:
        sc["camera"] = {"zoom": [1.0, 1.08]}
        issue(out, i, "camera", "low", "an important number or document had no camera move: added a slow push-in", fixed=True)
    fixes = []
    LY.fix_camera(sc, None, fixes)                      # a punch-in must never leave a label or speech bubble half cut off
    for f in fixes:
        issue(out, i, "camera", "medium", f, fixed=True)


def layout_ctx(beat, reqs_i):
    return dict(text=(beat or {}).get("text", ""), needs=[r.get("value") for r in reqs_i or [] if isinstance(r, dict)])


def check_layout(i, sc, ctx, out):
    """Collisions, margins, sizes, hierarchy and bubbles: repaired locally, cheapest change first (studio/engine/layout.py)."""
    _, fixes, _ = LY.fix_scene(sc, ctx)
    for f in fixes:
        issue(out, i, "layout", "low", f, fixed=True)


def layout_report(scenes, beats, reqs, only, out):
    """After every scene was repaired and the video-wide consistency pass ran: what is still wrong, and the score per scene."""
    per, open_, esc = {}, [], []
    for i in sorted(scenes):
        sc, beat = scenes[i], (beats[i] if i < len(beats) else {})
        if not isinstance(sc, dict) or beat.get("host") or not (only is None or i in only):
            continue
        left = LY.audit(sc, layout_ctx(beat, (reqs or {}).get(i)))
        per[str(i)] = LY.score(left)
        for x in left:
            if x["sev"] in ("high", "medium"):
                issue(out, i, "layout", x["sev"], x["msg"] + (f" ({x['fix']})" if x.get("fix") else ""), fixed=False)
                open_.append(dict(beat=i, sev=x["sev"], kind=x["kind"], msg=x["msg"]))
        if any(x["sev"] == "high" for x in left):
            esc.append(i)
    vals = list(per.values())
    return dict(per_beat=per, mean=round(sum(vals) / len(vals), 3) if vals else 1.0, open=open_, escalate=esc,
                blocked=[i for i in esc])


def check_emotion(i, sc, a, beat, out):
    bg = sc.get("bg") or {}
    if beat.get("mood") == "somber":
        if bg.get("type") in ("sunburst",) or (bg.get("type") in CT.PAINTED and bg.get("time") in (None, "day")):
            if bg.get("type") == "sunburst":
                sc["bg"] = {"type": "dark"}
            else:
                bg["time"] = "dusk"
            issue(out, i, "emotion", "medium", "a somber moment had a bright background: darkened it", fixed=True)
        els = sc.get("elements") or []
        for e in list(els):
            if e.get("type") == "prop" and e.get("name") in ("trophy", "dove", "star") and a.get("emotion") == "tragedy" and e.get("name") == "trophy":
                els.remove(e)
                issue(out, i, "emotion", "medium", "a trophy in a tragic moment: removed", fixed=True)


def sig_of(sc):
    bg = sc.get("bg") or {}
    return (bg.get("type"), bg.get("style"), tuple(sorted(str(p) for p in props_of(sc))),
            tuple(sorted(str(e.get("kind")) for e in sc.get("elements") or [] if e.get("type") in ("char", "crowd"))))


# ------------------------------------------------------------------ the whole storyboard
def run(scenes, beats, analyses, registry=None, durations=None, patterns=None, usage=None, only=None, reqs=None):
    """Review `scenes` ({index: scene}) in place. Returns the report dict. `only` limits the per-scene fixes to those
    beats (the others are still read for the redundancy and pacing checks)."""
    from . import coverage as CV
    from ..knowledge import semantics as SM
    out = []
    covs = {}
    year = None
    score_n = {k: [0, 0] for k in CHECKS}
    last_sig = None
    streak = 0
    for i in sorted(scenes):
        sc = scenes[i]
        beat = beats[i] if i < len(beats) else {}
        a = analyses[i] if i < len(analyses) else {}
        if a.get("years"):
            year = a["years"][0]
        if not isinstance(sc, dict) or beat.get("host"):
            last_sig = None
            continue
        mine = only is None or i in only
        local = []
        if mine:
            m, e = check_narration(i, sc, a, local, registry)
            score_n["narration"][0] += m
            score_n["narration"][1] += e
            check_history(i, sc, a, year, local)
            check_props(i, sc, a, local)
            check_action(i, sc, a, local)
            check_camera(i, sc, a, local)
            check_layout(i, sc, layout_ctx(beat, (reqs or {}).get(i)), local)
            check_emotion(i, sc, a, beat, local)
            if reqs and reqs.get(i) is not None:
                covs[i] = CV.check(i, sc, a, reqs[i], registry, local)
        elif reqs and reqs.get(i) is not None:
            covs[i] = SM.coverage(reqs[i], sc)
        out += local
        sig = sig_of(sc)
        if sig == last_sig:
            streak += 1
            issue(out, i, "redundancy", "medium" if streak > 1 else "low", "this scene looks the same as the one before it")
        else:
            streak = 0
        last_sig = sig
    # the same style and the same sizes across the whole video
    for row in LY.consistency({i: s for i, s in scenes.items() if isinstance(s, dict) and not (beats[i] if i < len(beats) else {}).get("host")}, only=only):
        issue(out, row["beat"], "layout", "low", row["msg"], fixed=row["fixed"])
    lay = layout_report(scenes, beats, reqs, only, out)
    # continuity and character consistency
    cont = CT.check({i: s for i, s in scenes.items() if (only is None or i in only)}, analyses, registry, beats)
    out += cont
    # pacing
    if durations:
        for i, d in enumerate(durations):
            if i >= len(beats) or beats[i].get("host"):
                continue
            if d < 1.8:
                issue(out, i, "pacing", "low", f"this scene is only {d:.1f} s long: too quick to read")
            elif d > 16:
                issue(out, i, "pacing", "medium", f"this scene is {d:.0f} s long: add a second picture or split the line")
    if usage:
        t = usage.get("total", {})
        if t.get("calls", 0) > 25:
            issue(out, -1, "usage", "low", f"this video made {t['calls']} AI calls ({t.get('tokens', 0):,} tokens)")
    by = {k: [x for x in out if x["check"] == k] for k in CHECKS}
    scores = {}
    for k in CHECKS:
        total = max(1, len(scenes))
        bad = len([x for x in by[k] if not x["fixed"]])
        scores[k] = round(max(0.0, 1.0 - bad / total), 2)
    if score_n["narration"][1]:
        scores["narration"] = round(score_n["narration"][0] / score_n["narration"][1], 2)
    cov_sum = CV.summary(covs)
    if covs:
        scores["coverage"] = cov_sum["mean"]
    return dict(scores=scores, issues=out, layout=lay, fixed=len([x for x in out if x["fixed"]]),
                open=len([x for x in out if not x["fixed"] and x["severity"] in ("medium", "high")]),
                coverage=dict(cov_sum, per_beat={str(i): c["score"] for i, c in covs.items()},
                              missing={str(i): [f"{m['value']} ({m['kind']})" for m in c["must_missing"]] for i, c in covs.items() if c["must_missing"]}))
