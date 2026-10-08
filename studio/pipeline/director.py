"""The director: the AI decides WHAT each scene is, the local engine decides HOW it looks.

Instead of asking the AI to write full scene JSON for every beat (about 600 output tokens each, plus a 13,000-token
manual in every request), the director asks for a compact PLAN: per beat one pattern from the pattern library and a few
slot values (who, the document's real title and lines, a quote, a label...). knowledge/composer.py then builds the
scene. Beats no pattern fits are marked CUSTOM and still go to the full storyboard writer, so nothing is lost.

Plans are cached per beat (knowledge/patterns version + cast + beat text), so editing one line re-plans one line.
Without an AI (Basic writer, fast mode on confident beats) the retriever's best pattern is composed directly.
"""
import copy
import json
import re

from .. import cache as CA, usage as UG
from ..config import load_settings
from ..engine.schema import BG_TYPES
from ..knowledge import composer as CO, patterns as PT, semantics as SM
from ..knowledge.analysis import analyze
from . import characters as CH, continuity as CT, coverage as CV

CONFIDENT_LOCAL = 6.5          # a local match this strong needs no AI in fast mode
EASY_COVERAGE = 0.9            # normal mode: a beat is "easy" when the locally built scene also shows 90% of what it says
PLAN_TOK_PER_BEAT = 190        # what planning one beat costs (the estimator's numbers): used for the savings meter
PLACE_NAMES = ", ".join(t for t in BG_TYPES if t not in ("paper", "sunburst", "ground", "sea", "night", "map", "dark"))
SYSTEM = ("You are the director of a funny stickman history YouTube channel. For each narration beat you choose ONE scene "
          "pattern and fill in its details. A local animation engine draws the scene from your choice, so you decide WHAT "
          "happens and never write coordinates or scene code. You only answer with JSON.")


def analyses_for(beats, cast, topic=""):
    """Local analysis of every beat, plus the meaning layer (named regions, the famous document or event behind the
    sentence, the story-fitted map). `topic` (the video's title/topic) decides what an ambiguous phrase like 'the colonies' means."""
    seen, out = set(), []
    for b in beats:
        a = analyze(b.get("text", ""), b.get("mood", "fun"), cast, seen)
        out.append(SM.enrich(a, b.get("text", ""), topic))
    return out


def cast_sig(registry):
    return [(e["name"], e["kind"], e.get("hat_color"), e.get("coat"), e.get("look")) for e in registry]


def plan_key(beat, registry):
    return CA.key("plan", beat.get("text"), beat.get("mood"), cast_sig(registry), PT.version())


def hint_line(a, recent):
    bits = []
    cands = [p["id"] for p, _ in PT.match(a, recent, 3)]
    if cands:
        bits.append("candidates: " + ", ".join(cands))
    if a.get("people"):
        bits.append("people: " + ", ".join(p["name"] for p in a["people"][:4]))
    if a.get("documents"):
        bits.append("document: " + (a["documents"][0]["name"] or a["documents"][0]["kind"]))
    if a.get("numbers"):
        bits.append("number: " + a["numbers"][0]["shown"])
    pl = [p["name"] for p in a.get("places") or []][:3]
    if pl:
        bits.append("places: " + ", ".join(pl))
    if a.get("years"):
        bits.append("year: " + str(a["years"][0]))
    if a.get("place_type"):
        bits.append("setting: " + a["place_type"])
    pin = SM.pattern_hint(a)
    if pin:
        bits.append(f"meaning pins this to {pin}")
    must = [r["value"] for r in SM.requirements(a, a.get("text", "")) if r["need"] == "must"][:4]
    if must:
        bits.append("must show: " + ", ".join(must))
    return " | ".join(bits)


def plan_prompt(batch, beats, analyses, registry, title, story_so_far="", recent=(), examples=0, hints=None):
    pats = PT.catalog_text()
    cast = "\n".join("- " + CH.describe(e) for e in registry[:14]) or "- (no recurring characters)"
    lines = []
    rec = list(recent)
    for i in batch:
        a = analyses[i]
        h = hint_line(a, rec)
        lines.append(f"[{i}] ({beats[i].get('mood', 'fun')}) {beats[i]['text']}" + (f"\n     -> {h}" if h else "")
                     + (f"\n     (source video showed: {hints[i]})" if hints and hints.get(i) else ""))
        best = PT.best(a, rec)[0]
        rec.append(best)
    ex = ""
    if examples:
        ex = ("\nEXAMPLE ANSWER:\n" + json.dumps({"plan": [
            {"beat": 7, "pattern": "DOCUMENT_SIGNING", "slots": {"doc_title": "THE CONSTITUTION", "doc_lines": ["We the People of the", "United States..."],
                                                                "signer": "Madison", "witnesses": ["Washington"], "place": "parliament"},
             "say": [{"who": "Madison", "text": "My hand hurts."}]},
            {"beat": 8, "pattern": "STATISTIC_VISUALIZATION", "slots": {"number": "55 delegates", "unit": "delegates"},
             "say": [{"who": "Franklin", "text": "Only 55?"}]}]}, separators=(",", ":")) + "\n")
    return f"""PATTERNS (id: when to use it  [slots you can fill]):
{pats}
CUSTOM: use ONLY for a scene that needs special choreography the patterns can't express (the scene is then drawn
separately, which is slower). For an ordinary story moment use STORY_MOMENT.

HOW TO CHOOSE
- One pattern per beat. Don't use the same pattern in two beats in a row; follow each beat's "candidates" unless you see a better fit.
- Fill only the slots that matter. Use EXACT cast names for people. Slot text is short: doc_title is the document's real name
  (max 22 characters), doc_lines are 2-4 lines of at most 24 characters that are really written on it, a quote is at most 6 words,
  a label at most 28 characters. "place" is one of: {PLACE_NAMES}.
- "needs" is what the viewer must SEE to understand the beat (max 5 short phrases: places, regions, people, documents, objects, numbers).
  Start from the studio's "must show" list; fix it if it is wrong, and add what it missed. Think about what the narrator MEANS, not
  which words appear: "England founded colonies on the Atlantic coast" is about the colonies on the coast of North America.
- "say" is for jokes and in-character lines (at most 2 per beat, 4 words each); nobody speaks unless the beat has a reason.
- Somber beats: no jokes, no parades; tragedy patterns (death, disaster, battle action) with respectful lines.
{ex}
VIDEO: {title}
CAST (their looks are fixed by the studio; just use the names):
{cast}
{('STORY SO FAR (what the last scenes looked like):' + chr(10) + story_so_far) if story_so_far else ''}
BEATS (hints from the studio's own analysis after ->):
{chr(10).join(lines)}

Answer with JSON only: {{"plan": [{{"beat": <index>, "pattern": "<ID or CUSTOM>", "needs": ["<what must be seen>"], "slots": {{...}}, "say": [{{"who": "<name>", "text": "<line>"}}]}}]}}"""


def parse_plan(data, wanted):
    """{beat: {pattern, slots, say}} from the AI's answer, tolerant about the shape."""
    items = data.get("plan") if isinstance(data, dict) else data
    out = {}
    for k, it in enumerate(items or []):
        if not isinstance(it, dict):
            continue
        bi = it.get("beat")
        if not isinstance(bi, int) or bi not in wanted:
            bi = wanted[k] if k < len(wanted) else None
        if bi is None:
            continue
        pid = str(it.get("pattern") or PT.CUSTOM).upper().replace(" ", "_")
        if pid != PT.CUSTOM and not PT.get(pid):
            pid = PT.CUSTOM
        slots = it.get("slots") if isinstance(it.get("slots"), dict) else {}
        say = [s for s in (it.get("say") or []) if isinstance(s, dict) and s.get("text")][:2]
        needs = [str(x).strip()[:60] for x in (it.get("needs") or []) if isinstance(x, (str, int)) and str(x).strip()][:6]
        out[bi] = dict(pattern=pid, slots=slots, say=say, needs=needs)
    return out


def apply_say(scene, says, text):
    """Attach the director's lines to the matching characters (by name; else the biggest one)."""
    if not says:
        return scene
    chars = [e for e in scene.get("elements") or [] if e.get("type") == "char" and not e.get("narrator")]
    if not chars:
        return scene
    w = CO.Words(text)
    for k, s in enumerate(says[:2]):
        who = str(s.get("who") or "").lower()
        tgt = next((c for c in chars if who and who in str(c.get("who") or "").lower()), None) \
            or next((c for c in chars if who and who.split()[-1:] and who.split()[-1] in str(c.get("who") or "").lower()), None) \
            or max(chars, key=lambda c: float(c.get("scale") or 1))
        if tgt.get("say"):
            continue
        tgt["say"] = [CO.say(str(s["text"])[:36], 0.28 + 0.3 * k)]
    return scene


def compose_one(entry, beat, a, ctx, local_best):
    """The scene for one beat from the director's entry (or the local best match). (scene, pattern id) or (None, id)."""
    pid = entry["pattern"] if entry else local_best[0]
    slots = (entry or {}).get("slots") or {}
    if pid == PT.CUSTOM:
        if entry:
            return None, PT.CUSTOM                      # the director asked for the full scene writer
        pid = "STORY_MOMENT"                            # no AI plan and no confident pattern: the catch-all
    sc = CO.compose(PT.get(pid), beat, a, slots, ctx)
    if sc is None and local_best[0] not in (PT.CUSTOM, pid) and local_best[1] >= PT.CONFIDENT:
        pid = local_best[0]
        sc = CO.compose(PT.get(pid), beat, a, {}, ctx)
    if sc is None:
        return None, pid
    if entry and entry.get("say"):
        apply_say(sc, entry["say"], beat.get("text", ""))
    return sc, pid


def _clone_tracker(tracker):
    """A copy of the continuity state to rehearse on (the project and its files are shared, never written)."""
    if tracker is None:
        return None
    t = copy.copy(tracker)
    t.states = copy.deepcopy(tracker.states)
    t.worlds = copy.deepcopy(tracker.worlds)
    return t


def easy_beats(todo, beats, analyses, cast, tracker, title, best, floor):
    """Beats the studio can draw well on its own, so the AI need not plan them: a confident local pattern whose scene also
    shows what the narration says (rehearsed on a copy of the continuity state; nothing is kept). Normal mode uses this."""
    t, easy = _clone_tracker(tracker), set()
    for i in todo:
        a = analyses[i]
        try:
            got = CV.choose(None, beats[i], a, SM.requirements(a, beats[i].get("text", "")), cast, i, t.before(i) if t else {}, title, best[i])
        except Exception:
            got = None
        if not got:
            continue
        if t:
            t.record(i, got["scene"], a, got["pattern"], got["state"], beats[i])
        cov = got["coverage"]
        if best[i][1] >= floor and got["pattern"] != PT.CUSTOM and cov["score"] >= EASY_COVERAGE and not cov["must_missing"]:
            easy.add(i)
    return easy


def build(ctx, llm, script, todo, registry, analyses, tracker, profile, call, hints=None, parallel=3, force=False):
    """Plan and compose every beat in `todo`. `call(llm, system, prompt, label)` makes one AI request (the stage passes
    call_llm, so the cache and the usage ledger apply). Returns (scenes {i: scene}, custom [i], info {i: {...}})."""
    import concurrent.futures as cf
    beats = script["beats"]
    title = script.get("title", "")
    todo = sorted(i for i in todo if not beats[i].get("host"))
    plans, need = {}, []
    use_ai = llm is not None and getattr(llm, "id", "offline") != "offline"
    recent = []
    best = {}
    for i in todo:                                         # local retrieval first: free, and it shapes the prompt
        best[i] = PT.best(analyses[i], recent)
        recent.append(best[i][0])
    skipped = []
    if use_ai:
        floor = profile.get("easy_local")
        easy = set()
        if floor and profile["name"] != "fast" and load_settings().get("plan_skip_easy", True) and not force:
            easy = easy_beats(todo, beats, analyses, CH.as_cast(registry), tracker, title, best, floor)
        for i in todo:
            if profile["name"] == "fast" and best[i][1] >= CONFIDENT_LOCAL:
                continue                                    # fast mode: a very confident local match needs no AI
            cached = None if force else CA.get("plans", plan_key(beats[i], registry))
            if cached:
                plans[i] = cached
            elif i in easy:
                skipped.append(i)                           # normal mode: the studio's own scene already shows the narration
            else:
                need.append(i)
        size = max(4, int(profile["plan_batch"]))
        if skipped:
            now = -(-len(need) // size) if need else 0
            was = -(-(len(need) + len(skipped)) // size)
            UG.saved(getattr(ctx, "project", None), "plan", calls=was - now, tokens=len(skipped) * PLAN_TOK_PER_BEAT,
                     note=f"{len(skipped)} of {len(todo)} scenes were easy: drawn by the studio without planning them with the AI")
        batches = [need[k:k + size] for k in range(0, len(need), size)]

        def run_batch(idx):
            story = tracker.line(idx[0]) if tracker else ""
            prompt = plan_prompt(idx, beats, analyses, registry, title, story, [best[j][0] for j in range(max(0, idx[0] - 2), idx[0]) if j in best],
                                 profile.get("plan_examples", 0), hints)
            data = call(llm, SYSTEM, prompt, f"plan {idx[0]}-{idx[-1]}")
            got = parse_plan(data, idx)
            for bi, ent in got.items():
                CA.put("plans", plan_key(beats[bi], registry), ent, dict(beat=bi))
            return got

        if batches:
            with cf.ThreadPoolExecutor(max_workers=max(1, min(parallel, len(batches)))) as ex:
                futs = {ex.submit(run_batch, b): b for b in batches}
                for fut in cf.as_completed(futs):
                    try:
                        plans.update(fut.result())
                    except Exception as e:           # a failed batch just falls back to the local best match
                        ctx.warn(f"plan batch {futs[fut][0]}-{futs[fut][-1]} failed ({str(e)[:140]}): using the studio's own matching for those scenes")
    scenes, custom, info = {}, [], {}
    cast = CH.as_cast(registry)
    for i in todo:
        a = analyses[i]
        cstate = tracker.before(i) if tracker else {}
        entry = plans.get(i)
        reqs = SM.requirements(a, beats[i].get("text", ""), (entry or {}).get("needs"))
        got = CV.choose(entry, beats[i], a, reqs, cast, i, cstate, title, best[i])
        if got is None:
            custom.append(i)
            info[i] = dict(pattern=PT.CUSTOM, source="custom", local=best[i][0], score=round(best[i][1], 1), reqs=reqs)
            continue
        sc, pid = got["scene"], got["pattern"]
        if entry and entry.get("say"):
            apply_say(sc, entry["say"], beats[i].get("text", ""))
        scenes[i] = sc
        info[i] = dict(pattern=pid, source="plan" if entry else "local", local=best[i][0], score=round(best[i][1], 1),
                       coverage=got["coverage"]["score"], reqs=reqs, tried=got.get("tried"),
                       planned=(entry or {}).get("pattern"))
        if tracker:
            tracker.record(i, sc, a, pid, got["state"], beats[i])
    return scenes, custom, info
