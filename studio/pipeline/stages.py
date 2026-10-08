"""The seven pipeline stages. Each is re-runnable and only redoes work whose inputs changed."""
import concurrent.futures as cf
import hashlib
import multiprocessing as mp
import json
import os
import re
import shutil
import time

import numpy as np
import soundfile as sf

from .. import providers as P
from .. import config
from ..config import load_settings
from ..engine import (check_scene, plan_timeline, render_segment, render_still, concat_segments, share_copy,
                      prep, word_times_from_alignment, render_thumbnail, LEAD, TAIL)
from ..engine.audio import build_mix, loudnorm, load_audio, SR, ambience_kind, music_style, smooth_styles, \
    find_sting, BASE_MOOD
from ..engine.render import ENGINE_VERSION, pick_transition
from ..engine.pen import resolve_kind
from ..engine import layout as LY
from .. import prompts as PR
from .. import cache as CA, usage as UG
from . import flow as FL, research as RS, director as DR, characters as CH, continuity as CT, review as RV, modes as MD
from . import rules, costs, themes as TH, mascot as MA, writers as WR
from .project import read_json, write_json
from ..engine.custom_props import clean_kit, kit_sheet
from ..knowledge import semantics as SM
from ..research import budget as RB, engine as RE, claims as CL
from . import spec as SP, muted as MU, world as WD, coverage as CVG
from ..knowledge import props_intel as PI
from ..engine.registry import PROPS
from .source import (fetch_meta, transcript_text, download_lowres, extract_frames, thumbnail_frames, contact_sheets,
                     hints_for_beats)


class Cancelled(Exception):
    pass


def h(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def provider(meta, stage, ctx=None, task=None):
    """The provider for a stage. For the writer, `task` (script, factcheck, watch, props, storyboard, package,
    short) picks the AI assigned to that job in Settings > "Who does what", else the video's writer."""
    if stage == "llm":
        settings = load_settings()
        p = P.get("llm", WR.task_writer_id(meta, task, settings))
        if p.id == "claude_cli":
            p = WR.ClaudeTask(p, task, settings)      # the task's Claude model and the plan savers
    else:
        pid = (meta.get("providers") or {}).get(stage) or P.TIERS["free"][stage]
        p = P.get(stage, pid)
    if stage == "llm":
        backup = P.backup_for(p.id)
        if backup is not None:
            # Claude Code first; if the plan runs out mid-video a free writer takes over instead of stopping
            return P.WithBackup(p, backup, (lambda a, b, why: switched_writer(ctx, a, b, why)) if ctx else None)
    return p


def switched_writer(ctx, primary, backup, why):
    ctx.warn(f"Your Claude plan reached its usage limit, so {backup.short} (free) took over for the rest of this "
             f"step. Scenes it draws may be a bit plainer; you can redraw them with Claude later. ({why[:160]})")
    ctx.project.update(lambda m: m.setdefault("writer_switches", []).append(
        dict(stage=ctx.stage, to=backup.id, at=time.time())))


def workers():
    n = int(load_settings().get("render_workers") or 0)
    return n if n > 0 else max(1, (os.cpu_count() or 2) - 1)


def clean_line(t):
    t = re.sub(r"\s*[—–]\s*", ", ", str(t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t


# roughly how long each kind of AI call takes, so the progress bar can keep moving while we wait
EXPECT = {"script": 90, "storyboard": 75, "watch": 45, "package": 30, "short": 25, "fix": 30, "beat": 15, "props": 60,
          "facts": 120}
SAYING = {"script": "{who} is writing the script", "storyboard": "{who} is drawing up the scenes",
          "watch": "{who} is watching the video", "package": "{who} is writing titles and the description",
          "short": "{who} is picking the best moment for the Short", "fix": "{who} is fixing a scene",
          "props": "{who} is designing props for this video", "facts": "{who} is fact-checking the script"}


def _model_of(llm):
    m = getattr(llm, "model", None)
    if callable(m):
        try:
            m = m()
        except Exception:
            m = None
    return str(m or "")


def call_llm(ctx, llm, system, prompt, schema=None, images=(), label="", parse=True, tries=2, until=None, web=False,
             cache=True):
    """One AI request, with the cache in front and the usage ledger behind it.

    An identical request (same writer + model + instructions + prompt + schema + images) is answered from the cache
    and costs nothing; `cache=False` forces a fresh answer (the "redraw this scene" buttons). Every call, cached or
    not, is written to the video's usage ledger."""
    last = None
    kind = label.split()[0] if label else ""
    task = {"facts": "factcheck", "fix": "storyboard", "plan": "storyboard", "flow": "script"}.get(kind, kind)
    for attempt in range(tries):
        ctx.check_cancel()
        who = getattr(llm, "short", "The AI")
        t0 = time.time()
        use_web = bool(web and getattr(llm, "supports_web", False))
        k = CA.key("llm", getattr(llm, "id", ""), _model_of(llm), system, prompt, schema, [CA.file_key(i) for i in images],
                   use_web)
        text = CA.get("llm", k) if cache else None
        usage = {}
        cached = text is not None
        if cached:
            ctx.log(f"{label}: answered from the cache (no AI call)")
        else:
            with ctx.working(ctx.msg if ctx.msg and kind not in SAYING else SAYING.get(kind, ctx.msg or "working").format(who=who),
                             expect=EXPECT.get(kind, 45), until=until):
                text, usage = llm.complete(system, prompt, schema=schema, images=images, label=label,
                                           **({"web": True} if use_web else {}))
        if usage.get("billed_usd"):
            costs.record(ctx.project, ctx.stage, llm.id, usd=usage["billed_usd"],
                         note=f"{label}: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out tokens")
        in_est = UG.tokens(len(system or "") + len(prompt)) + 700 * len(images)
        UG.record(ctx.project, dict(
            stage=ctx.stage, task=task, label=label, provider=getattr(llm, "id", ""), model=_model_of(llm),
            cached=cached, secs=round(time.time() - t0, 1),
            in_tok=int(usage.get("in_tok") or in_est), out_tok=int(usage.get("out_tok") or UG.tokens(len(str(text or "")))),
            measured=bool(usage.get("measured"))))
        if not parse:
            if not cached:
                CA.put("llm", k, text, dict(label=label, provider=getattr(llm, "id", "")))
            return text
        try:
            data = P.extract_json(text)
        except Exception as e:
            last = e
            ctx.log(f"{label}: reply was not valid JSON, retrying ({e})")
            prompt = prompt + "\n\nIMPORTANT: your previous answer was not valid JSON. Reply with valid JSON only."
            continue
        if not cached:
            CA.put("llm", k, text, dict(label=label, provider=getattr(llm, "id", "")))
        return data
    raise P.ProviderError(f"{label}: no valid JSON after {tries} tries ({last})")


def measure_credits(prov):
    """Snapshot the provider balance so we can record what a paid call really used."""
    try:
        b = prov.balance() if prov.paid else None
        return b.get("used") if b else None
    except Exception:
        return None


def record_credits(ctx, prov, before, note):
    if before is None:
        return
    after = measure_credits(prov)
    if after is not None:
        used = max(0, after - before)
        from ..providers.elevenlabs_common import usd_for_credits
        costs.record(ctx.project, ctx.stage, prov.id, usd=usd_for_credits(used) if "eleven" in prov.id else 0.0,
                     credits=used, note=note + " (measured from balance)")


# ================================================================== source
def stage_source(ctx):
    pr, meta = ctx.project, ctx.project.meta()
    opts = meta.get("options") or {}
    url = meta.get("source_url") or opts.get("style_url")
    ctx.progress(0.02, "reading video info")
    m = fetch_meta(url)
    write_json(pr.p("source", "meta.json"), m)
    if not meta.get("title") or meta.get("title") == url:
        pr.update(title=m.get("title") or url)
    ctx.log(f"source: {m.get('title')} by {m.get('channel')} ({int(m.get('duration') or 0) // 60} min)")
    tp = provider(meta, "transcript")
    ok, why = tp.available()
    if not ok:
        raise P.ProviderError(f"{tp.label} is not available: {why}")
    before = measure_credits(tp)
    segs = tp.transcript(url, m, pr.p("source", "tmp"), progress=lambda msg, f: ctx.progress(0.1 + 0.4 * f, msg))
    record_credits(ctx, tp, before, "transcript")
    write_json(pr.p("source", "transcript.json"), segs)
    with open(pr.p("source", "transcript.txt"), "w", encoding="utf-8") as f:
        f.write(transcript_text(segs))
    ctx.log(f"transcript: {len(segs)} segments, {sum(len(s['text'].split()) for s in segs)} words")
    llm = provider(meta, "llm", ctx, task="watch")
    if opts.get("watch", True) and llm.supports_images and llm.id != "offline" and llm.available()[0]:
        try:
            ctx.progress(0.55, "downloading a low-res copy to watch")
            try:
                with ctx.working("downloading a low-res copy to watch", expect=30, until=0.64):
                    video = download_lowres(url, pr.p("source", "tmp"))
                ctx.progress(0.65, "grabbing frames")
                frames = extract_frames(video, float(m.get("duration") or 60), pr.p("source", "frames"))
            except Exception as e:
                # YouTube wouldn't give us the video: its own still frames still show the drawing style
                frames = thumbnail_frames(m.get("video_id") or P.video_id(url), pr.p("source", "frames"))
                if not frames:
                    raise
                hint = "" if config.js_runtimes() else \
                    " Install Node.js or Deno so the downloader can read YouTube (see Troubleshooting in the README)."
                ctx.warn(f"Couldn't download the video ({str(e)[:120]}), so the AI looked at YouTube's "
                         f"{len(frames)} still frames instead.{hint}")
            sheets = contact_sheets(frames, pr.p("source", "sheets"))[:4]
            ctx.progress(0.75, f"watching the video ({len(sheets)} contact sheets)")
            notes = call_llm(ctx, llm, "You analyse video frames and answer with JSON only.",
                             PR.vision_prompt(len(sheets), m.get("title", "")), schema=PR.VISION_SCHEMA,
                             images=sheets, label="watch")
            write_json(pr.p("source", "visual_notes.json"), notes)
            ctx.log(f"watched: style = {str(notes.get('style', ''))[:120]}")
        except Exception as e:
            ctx.warn(f"Couldn't watch the video frames (continuing with the transcript only): {str(e)[:200]}")
        finally:
            shutil.rmtree(pr.p("source", "tmp"), ignore_errors=True)
    ctx.progress(1.0, "source ready")


# ================================================================== script
def normalize_script(data, fallback_title=""):
    beats = []
    for b in data.get("beats") or []:
        if isinstance(b, str):
            b = {"mood": "fun", "text": b}
        t = clean_line(b.get("text"))
        if not t:
            continue
        mood = b.get("mood") if b.get("mood") in ("fun", "tense", "somber") else "fun"
        beat = {"mood": mood, "text": t}
        for k, n_ in (("purpose", 90), ("location", 60), ("visual", 140)):      # the animator's notes (kept, never spoken)
            if isinstance(b.get(k), str) and b[k].strip():
                beat[k] = clean_line(b[k])[:n_]
        if isinstance(b.get("claims"), list):
            beat["claims"] = [str(x)[:12] for x in b["claims"] if isinstance(x, str)][:4]
        if b.get("host") in ("intro", "outro", "end"):          # the channel host's own lines (see mascot.py)
            beat["host"] = b["host"]
        if b.get("part") in ("hook", "intro", "story", "payoff"):
            beat["part"] = b["part"]
        beats.append(beat)
    if not beats:
        raise P.ProviderError("the script came back empty")
    facts = []
    for f in data.get("facts") or []:
        if isinstance(f, dict) and f.get("claim"):
            facts.append(dict(beat=int(f.get("beat") or 0), claim=clean_line(f["claim"]),
                              confidence=f.get("confidence") if f.get("confidence") in ("high", "medium", "low") else "medium",
                              note=clean_line(f.get("note", "")), checked=False))
    cast = []
    for c in data.get("cast") or []:
        if isinstance(c, dict) and c.get("name"):
            ent = dict(name=str(c["name"])[:40], kind=resolve_kind(c.get("kind")), hat_color=c.get("hat_color") or "")
            for k in ("coat", "look", "role", "period", "trait"):      # the look and role survive (they used to be dropped)
                if c.get(k):
                    ent[k] = str(c[k])[:80]
            if ent.get("look") not in (None, "beard", "mustache"):
                ent.pop("look")
            cast.append(ent)
    return dict(title=clean_line(data.get("title") or fallback_title), topic=clean_line(data.get("topic") or fallback_title),
                beats=beats, facts=facts, cast=cast)


def source_bundle(pr, meta):
    m = read_json(pr.p("source", "meta.json"), {}) or {}
    segs = read_json(pr.p("source", "transcript.json"), []) or []
    vn = read_json(pr.p("source", "visual_notes.json"))
    return dict(title=m.get("title", ""), channel=m.get("channel", ""), duration=m.get("duration"),
                description=m.get("description", ""), chapters=m.get("chapters") or [], segments=segs,
                transcript_text=transcript_text(segs), visual_notes=vn)


def save_research(pr, research):
    """The research this video used, in its project folder (the topic cache keeps the full copy)."""
    write_json(pr.p("research.json"), research.brief)
    d = pr.p("research")
    os.makedirs(d, exist_ok=True)
    write_json(os.path.join(d, "claims.json"), research.claims)
    write_json(os.path.join(d, "sources.json"), research.sources)
    write_json(os.path.join(d, "report.json"), dict(topic=research.topic, slug=research.slug, cached=research.cached,
                                                    sufficient=research.sufficient, gaps=research.gaps, budget=research.report))


def stage_script(ctx):
    pr, meta = ctx.project, ctx.project.meta()
    opts = meta.get("options") or {}
    llm = provider(meta, "llm", ctx, task="script")
    minutes = float(opts.get("minutes") or 10)
    youtube = meta.get("mode") == "youtube"
    src = source_bundle(pr, meta) if (youtube or opts.get("style_url")) else None
    ctx.progress(0.05, "writing the script")
    research = None
    if llm.id == "offline":
        script = rules.offline_script(meta.get("topic"), minutes, src if youtube else None)
        ctx.warn("Basic mode wrote a placeholder script. Pick an AI writer (Claude, Gemini, Groq...) for a real one.")
    else:
        ok, why = llm.available()
        if not ok:
            raise P.ProviderError(f"{llm.label} is not available: {why}")
        style_notes = ""
        if src and not youtube:
            vn = src.get("visual_notes") or {}
            style_notes = f"Reference video: {src['title']} by {src['channel']}. Visual style: {vn.get('style', '')}. " \
                          f"Copy the pacing and humor style only, not the content."
        brief_notes = ""
        rcfg = RB.resolve_config(load_settings(), opts, MD.name_of(meta))
        run_research = rcfg["enabled"] and meta.get("topic") and (MD.profile(meta)["research"] or opts.get("research_mode") in RB.MODES)
        if run_research:
            try:
                research = RE.research_topic(
                    ctx, llm, lambda l, sy, pr_, lb, web: call_llm(ctx, l, sy, pr_, label=lb, web=web, tries=1),
                    meta["topic"], minutes, rcfg, grant=meta.get("research_grant"))
                if research:
                    save_research(pr, research)
                    brief_notes = RS.notes_for_script(research.brief) + "\n" + "RESEARCH (cite the ids in each beat's claims):\n" + CL.prompt_lines(research.claims)
            except P.ProviderError as e:
                ctx.warn(f"couldn't research the topic first (the script is written from the model's own knowledge): {str(e)[:160]}")
        prompt = PR.script_prompt(meta.get("topic") or "", minutes, opts.get("tone") or "funny but respectful",
                                  style_notes, src if youtube else None, opts.get("faithfulness") or "balanced",
                                  opts.get("extra") or "", research=brief_notes)
        redo = os.path.exists(pr.p("script.json"))          # pressing "redo the script" must give a new one, not the saved answer
        data = call_llm(ctx, llm, PR.SCRIPT_SYSTEM, prompt, schema=PR.SCRIPT_SCHEMA, label="script", cache=not redo)
        script = normalize_script(data, meta.get("topic") or (src or {}).get("title", ""))
    script["generated_by"] = llm.id
    script["created"] = time.time()
    profile = MD.profile(meta)
    if research:
        CL.link_scenes(research.claims, script["beats"])
        write_json(pr.p("research", "claims.json"), research.claims)
        unsupported = CL.unsupported_items(script["beats"], research.claims, research.brief)
        script["evidence"] = dict(claims=len(research.claims), sources=len(research.sources), unsupported=unsupported[:40],
                                  research=research.report)
    if llm.id != "offline" and profile["factcheck"] and opts.get("fact_check", load_settings().get("fact_check", True)) is not False:
        ctx.progress(0.6, "fact-checking")
        backed = bool(research and research.claims and sum(1 for c in research.claims if c.get("url")) >= max(3, len(research.claims) // 2))
        unsupported = (script.get("evidence") or {}).get("unsupported")
        if backed and unsupported is not None and not unsupported:
            ctx.log("fact-check: every year, number and name in the script appears in the sourced research: no AI call needed")
            script["factcheck"] = dict(at=time.time(), web=True, checks=[], fixed=[], counts=dict(correct=0, wrong=0, unsure=0), by="research")
        else:
            try:
                fc = provider(meta, "llm", ctx, task="factcheck")
                if fc.id == "offline" or not fc.available()[0]:
                    fc = llm
                fact_check(ctx, fc, script, items=unsupported if backed else None)
            except P.ProviderError as e:
                ctx.warn(f"couldn't fact-check the script (it was kept as written): {str(e)[:200]}")
    if llm.id != "offline" and profile["smooth"] and opts.get("smooth_flow", True) is not False:
        smooth_flow(ctx, llm, script)
    MA.add_host_beats(script, load_settings(), mascot=opts.get("mascot", True) is not False)
    brief = read_json(pr.p("research.json"))
    if brief:                                        # people the research found that the script's cast doesn't list
        have = {c["name"].lower() for c in script.get("cast") or []}
        script.setdefault("cast", []).extend(c for c in RS.cast_from_brief(brief) if c["name"].lower() not in have and not any(
            c["name"].lower() in h_ or h_ in c["name"].lower() for h_ in have))
    registry = CH.build(script)                      # who is who, defined once for the whole video
    CH.merge_into_script(script, registry)
    CH.save(pr, registry)
    pr.save_script(script)
    if not meta.get("title") or meta.get("title") in (meta.get("source_url"), meta.get("topic")):
        pr.update(title=script.get("title") or meta.get("title"))
    words = sum(len(b["text"].split()) for b in script["beats"])
    ctx.log(f"script: {len(script['beats'])} beats, {words} words (~{words / 150:.1f} min), {len(script.get('facts', []))} facts")
    ctx.progress(1.0, f"{len(script['beats'])} beats")


def smooth_flow(ctx, llm, script, force=False):
    """Find the beats that don't connect to the one before them (free, local check), and when there are several ask
    the writer to reword just those so the story flows. Only for writers that cost nothing extra (your Claude plan,
    Gemini, Groq, Ollama): a paid writer is left alone and the Script tab offers a "Smooth the flow" button that shows
    its price first. Changes `script` in place; returns the beats that were reworded."""
    beats = script.get("beats") or []
    seams = FL.seams(beats)
    ctx.log(f"flow: {len(seams)} beat(s) that don't connect to the one before")
    if not seams or (not force and (len(seams) < 3 or len(seams) < 0.1 * len(beats))):
        return []
    if getattr(llm, "paid", False) and not force:
        ctx.warn(f"{len(seams)} beats jump from one point to another. Use 'Smooth the flow' in the Script tab "
                 f"to reword them (it shows the price first).")
        return []
    ctx.progress(0.85, "smoothing the flow between beats")
    todo = seams[:16]
    try:
        data = call_llm(ctx, llm, PR.SCRIPT_SYSTEM, PR.smooth_prompt(script, todo), schema=PR.SMOOTH_SCHEMA,
                        label="flow", tries=1, until=0.95)
    except P.ProviderError as e:
        ctx.warn(f"couldn't smooth the flow (the script was kept as written): {str(e)[:200]}")
        return []
    fixed = FL.apply_rewrites(beats, (data or {}).get("rewrites") if isinstance(data, dict) else None,
                              {i for i, _ in todo}, clean_line)
    script["flow"] = dict(at=time.time(), before=len(seams), fixed=fixed)
    ctx.log(f"flow: reworded {len(fixed)} beat(s) so they connect")
    return fixed


def fact_check(ctx, llm, script, items=None):
    """Double-check the claims the writer wasn't sure about (Claude Code searches the web for them), fix beats
    that got something wrong, and keep a report in script["factcheck"]. Changes `script` in place."""
    facts = script.get("facts") or []
    beats = script.get("beats") or []
    web = bool(getattr(llm, "supports_web", False))
    data = call_llm(ctx, llm, PR.FACTCHECK_SYSTEM, PR.factcheck_prompt(script, web, items), schema=PR.FACTCHECK_SCHEMA,
                    label="facts", tries=1, until=0.95, web=web)
    checks, fixed = [], []
    for c in (data.get("checks") if isinstance(data, dict) else None) or []:
        if not isinstance(c, dict):
            continue
        verdict = str(c.get("verdict", "unsure")).lower()
        verdict = verdict if verdict in ("correct", "wrong", "unsure") else "unsure"
        entry = dict(fact=c.get("fact"), beat=c.get("beat"), claim=str(c.get("claim", ""))[:300], verdict=verdict,
                     correction=str(c.get("correction", ""))[:300], source=str(c.get("source", ""))[:200])
        checks.append(entry)
        i = c.get("fact")
        if isinstance(i, int) and 0 <= i < len(facts):
            facts[i]["auto"] = verdict
            facts[i]["auto_note"] = (entry["correction"] or entry["source"])[:240]
    for rw in (data.get("rewrites") if isinstance(data, dict) else None) or []:
        if not isinstance(rw, dict):
            continue
        i, text = rw.get("beat"), clean_line(rw.get("text"))
        if isinstance(i, int) and 0 <= i < len(beats) and text and text != beats[i]["text"] and len(text.split()) <= 45:
            beats[i]["text"] = text
            fixed.append(i)
    script["factcheck"] = dict(at=time.time(), web=web, checks=checks, fixed=fixed,
                               counts={v: sum(1 for c in checks if c["verdict"] == v) for v in ("correct", "wrong", "unsure")})
    ctx.log(f"fact-check: {len(checks)} claims checked, {len(fixed)} beats corrected"
            + (" (with web search)" if web else " (from the model's knowledge, no web search)"))


# ================================================================== storyboard
def est_dur(text):
    return max(1.6, len(text.split()) / 2.9) + LEAD + TAIL


def beat_durations(pr, beats):
    v = pr.voice() or {}
    vb = v.get("beats") or []
    out = []
    for i, b in enumerate(beats):
        if i < len(vb) and vb[i].get("text") == b["text"]:
            out.append((vb[i]["dur"] + LEAD + TAIL, vb[i].get("word_times")))
        else:
            out.append((est_dur(b["text"]), None))
    return out


def stage_storyboard(ctx, only=None, force=False, instruction=""):
    """The storyboard. Default ("director"): the AI plans each scene as a pattern plus a few details, the local composer
    builds the scene, and only the beats no pattern fits go to the full storyboard writer. "classic" (Settings >
    storyboard_engine) asks the writer for every scene as before. Either way the result is checked and repaired
    locally, kept continuous from scene to scene, and reviewed before anything is voiced or rendered."""
    pr, meta = ctx.project, ctx.project.meta()
    script = pr.script()
    beats = script["beats"]
    n = len(beats)
    settings = load_settings()
    profile = MD.profile(meta, settings=settings)
    info = read_json(pr.p("storyboard.json"), {}) or {}
    made = info.get("scenes") or {}
    todo = []
    for i in (only if only is not None else range(n)):
        key = h(beats[i]["text"], beats[i]["mood"])
        if force or not os.path.exists(pr.scene_path(i)) or made.get(str(i), {}).get("key") != key:
            todo.append(i)
    llm = provider(meta, "llm", ctx, task="storyboard")
    ai_ok = llm.id != "offline" and llm.available()[0]
    engine = (meta.get("options") or {}).get("storyboard_engine") or settings.get("storyboard_engine") or "director"
    hints = {}
    if meta.get("mode") == "youtube":
        vn = read_json(pr.p("source", "visual_notes.json"))
        sm = read_json(pr.p("source", "meta.json"), {}) or {}
        hints = hints_for_beats(vn, n, float(sm.get("duration") or 0))
    raw = {}
    vthemes = TH.detect(script.get("title", ""), script.get("topic", ""), beats)
    kit_text = TH.kit_block(vthemes)
    custom = pr.prop_kit()
    registry = CH.load(pr) or CH.build(script)
    if not CH.load(pr):
        CH.save(pr, registry)
    cast = CH.as_cast(registry) or script.get("cast") or []
    topic_text = f"{script.get('title', '')} {script.get('topic', '')} {meta.get('topic', '')}"
    analyses = DR.analyses_for(beats, cast, topic_text)
    tracker = CT.Tracker(pr)
    host_beats = {i for i in todo if beats[i].get("host")}
    ai_todo = [i for i in todo if i not in host_beats]
    plan_info = {}
    composed = set()
    if todo and engine == "director":
        # 1. plan every scene (AI: one compact request per ~16 scenes, cached per beat) and build it locally
        if ai_ok:
            ctx.progress(0.02, f"planning {len(ai_todo)} scenes")
        who = getattr(llm, "short", "The AI")
        with ctx.working(f"{who} is planning {len(ai_todo)} scenes" if ai_ok else f"building {len(ai_todo)} scenes", expect=40, until=0.3), \
                PI.docs_scope(RS.docs_from_brief(read_json(pr.p("research.json")))):
            scenes, custom_idx, plan_info = DR.build(
                ctx, llm if ai_ok else None, script, ai_todo, registry, analyses, tracker, profile,
                lambda l, system, prompt, label: call_llm(ctx, l, system, prompt, label=label, cache=not force and not instruction),
                hints, parallel=max(1, int(getattr(llm, "parallel", 3) or 3)), force=force)
        raw.update(scenes)
        composed = set(scenes)
        ai_todo = custom_idx if (profile["custom_ai"] and ai_ok) else []
        ctx.log(f"storyboard: {len(composed)} scenes composed from patterns, {len(custom_idx)} need the full scene writer"
                + ("" if ai_todo else " (drawn with simple rules: AI is off for that in this mode)" if custom_idx else ""))
    if ai_todo and llm.id != "offline":
        ok, why = llm.available()
        if not ok:
            raise P.ProviderError(f"{llm.label} is not available: {why}")
        props_llm = provider(meta, "llm", ctx, task="props")
        if props_llm.id == "offline" or not props_llm.available()[0]:
            props_llm = llm
        if profile["props_ai"]:
            custom = design_props(ctx, props_llm, script, beats, vthemes, kit_text, custom)
        # free API writers have small per-minute limits: they get fewer scenes (and examples) per request
        size = max(1, int(getattr(llm, "batch_beats", 8) or 8))
        n_ex = int(getattr(llm, "examples", 20))
        compact = bool(getattr(llm, "compact", False))
        batches = [ai_todo[k:k + size] for k in range(0, len(ai_todo), size)]
        done = [0]
        who = getattr(llm, "short", "The AI")

        def run_batch(idx, n_ex=n_ex):
            try:
                return ask_batch(idx, n_ex)
            except P.TooLarge:
                # too big for the writer's free limits (or its reply got cut off): send less at once
                if len(idx) > 1:
                    half = len(idx) // 2
                    out = run_batch(idx[:half], n_ex)
                    out.update(run_batch(idx[half:], n_ex))
                    return out
                if n_ex > 0:
                    return run_batch(idx, 0)
                raise

        def ask_batch(idx, n_ex):
            # the active writer can change mid-way (backup writer), so size the request for the one answering now
            n_ex = min(n_ex, int(getattr(llm, "examples", 20)), 6 if composed else 20)   # fewer examples for the odd scenes
            prompt = PR.storyboard_prompt([(i, beats[i]) for i in idx], beats, script.get("cast") or cast, script.get("title", ""), hints,
                                          kit_text=kit_text, custom=custom, examples=n_ex,
                                          compact=compact or bool(getattr(llm, "compact", False)))
            if instruction:
                prompt += f"\n\nEXTRA DIRECTION FROM THE USER: {instruction}"
            data = call_llm(ctx, llm, PR.STORYBOARD_SYSTEM, prompt, label=f"storyboard {idx[0]}-{idx[-1]}",
                            cache=not force and not instruction)
            out = {}
            items = data.get("scenes") if isinstance(data, dict) else data
            for k, it in enumerate(items or []):
                if not isinstance(it, dict):
                    continue
                bi = it.get("beat")
                sc = it.get("scene") if "scene" in it else it
                if not isinstance(bi, int) or bi not in idx:
                    bi = idx[k] if k < len(idx) else None
                if bi is not None:
                    out[bi] = sc
            return out

        ctx.progress(0.3 if composed else 0.02, f"drawing {len(ai_todo)} scenes")
        par = max(1, int(getattr(llm, "parallel", 3) or 3))
        rounds = (len(batches) + par - 1) // par
        with ctx.working(f"{who} is drawing up {len(ai_todo)} scenes", expect=75 * rounds, until=0.64), \
                cf.ThreadPoolExecutor(max_workers=par) as ex:
            if getattr(llm, "warm_first", False) and len(batches) > 1 and par > 1:
                # plan saver: the first request alone, so Claude Code caches the long shared instructions
                # and the parallel requests after it reuse them
                b0 = batches.pop(0)
                try:
                    raw.update(run_batch(b0))
                except Exception as e:
                    ctx.warn(f"storyboard batch {b0[0]}-{b0[-1]} failed: {str(e)[:200]}")
                done[0] += len(b0)
                ctx.progress(0.3 + 0.35 * done[0] / len(ai_todo), f"{who} drew {done[0]} of {len(ai_todo)} scenes")
            futs = {ex.submit(run_batch, b): b for b in batches}
            for fut in cf.as_completed(futs):
                b = futs[fut]
                try:
                    raw.update(fut.result())
                except Exception as e:
                    ctx.warn(f"storyboard batch {b[0]}-{b[-1]} failed: {str(e)[:200]}")
                done[0] += len(b)
                ctx.progress(0.3 + 0.35 * done[0] / len(ai_todo), f"{who} drew {done[0]} of {len(ai_todo)} scenes")
    finished = {}
    for i in todo:
        ctx.check_cancel()
        beat = beats[i]
        if beat.get("host"):
            fixed, fixes, _ = check_scene(MA.host_scene(beat, load_settings(), script.get("title", ""), i),
                                          beat["mood"], beat["text"], custom, cast)
            finished[i] = fixed
            made[str(i)] = dict(key=h(beat["text"], beat["mood"]), fixes=["the channel host's scene"] + fixes,
                                source="host", at=time.time())
            continue
        sc = raw.get(i)
        talk = TH.ensure_dialogue(sc, beat["text"], beat["mood"], cast, TH.beat_themes(beat["text"], vthemes), i)
        fixed, fixes, errs = check_scene(sc, beat["mood"], beat["text"], custom, cast) if sc else (None, [], ["missing"])
        if talk:
            fixes = ["gave the speaker a line"] + fixes
        if (errs or not (fixed or {}).get("elements")) and llm.id != "offline" and sc is not None and i not in composed and ai_ok:
            try:
                data = call_llm(ctx, llm, PR.STORYBOARD_SYSTEM, PR.fix_scene_prompt(sc, errs or ["no elements"], beat),
                                label=f"fix scene {i}")
                fixed, fixes2, errs = check_scene(data, beat["mood"], beat["text"], custom, cast)
                fixes = fixes + ["asked the writer to fix it"] + fixes2
            except Exception as e:
                errs = [str(e)]
        source = llm.id
        if i in composed:
            source = "pattern:" + str((plan_info.get(i) or {}).get("pattern", ""))
        if fixed is None or errs or not fixed.get("elements"):
            fixed, fixes3, _ = check_scene(rules.rule_scene(beat, i, cast, vthemes), beat["mood"], beat["text"], custom, cast)
            fixes = fixes + ["used a simple rule-based scene"] + fixes3
            source = "rules"
        finished[i] = fixed
        made[str(i)] = dict(key=h(beat["text"], beat["mood"]), fixes=fixes, source=source, at=time.time(),
                            pattern=(plan_info.get(i) or {}).get("pattern"))
    # two scenes in a row shouldn't look the same: nudge colors / time of day of the new ones
    everything = {i: finished.get(i) or read_json(pr.scene_path(i)) for i in range(n)}
    if finished:
        for i, what in TH.vary(everything, list(range(n)), set(finished)):
            made[str(i)]["fixes"] = made[str(i)]["fixes"] + [f"varied the background ({what})"]
    # the storyboard review: check narration match, history, continuity, props, action, camera, pacing, mood, repeats
    if finished:
        ctx.progress(0.66, "reviewing the storyboard")
        durs = [d for d, _ in beat_durations(pr, beats)]
        old_plan = (read_json(pr.p("plan.json"), {}) or {}).get("beats") or {}
        reqs = {}
        for i in range(n):
            if beats[i].get("host") or not everything.get(i):
                continue
            pi = plan_info.get(i) or old_plan.get(str(i)) or {}
            reqs[i] = pi.get("reqs") or SM.requirements(analyses[i], beats[i]["text"])
        scenes_now = {i: sc for i, sc in everything.items() if sc}
        report = RV.run(scenes_now, beats, analyses, registry, durs, usage=UG.summarize(UG.calls(pr)), only=set(finished), reqs=reqs)
        failed_cov = [i for i in (report.get("coverage") or {}).get("failed", []) if i in finished]
        if ai_ok and profile["name"] != "fast" and (profile["review_ai"] or failed_cov):
            ai_fix_open(ctx, llm, report, finished, beats, custom, cast)
            if failed_cov:          # the writer redrew some of them: score them again
                from . import coverage as CVG
                again = {}
                for i in failed_cov:
                    again[i] = CVG.check(i, finished[i], analyses[i], reqs[i], registry, [])
                    report["coverage"]["per_beat"][str(i)] = again[i]["score"]
                report["coverage"]["failed"] = [i for i in report["coverage"]["failed"] if i not in again or again[i]["score"] < SM.COVERAGE_FAIL]
                report["coverage"]["blocked"] = [i for i in report["coverage"]["blocked"] if i not in again or again[i]["score"] < SM.COVERAGE_BLOCK]
        for i, pi_ in plan_info.items():
            if pi_.get("reqs") is not None and str(i) in made:
                made[str(i)]["coverage"] = (report.get("coverage") or {}).get("per_beat", {}).get(str(i))
        for iss in report["issues"]:
            if iss["fixed"] and iss["beat"] in made:
                made[str(iss["beat"])]["fixes"] = made[str(iss["beat"])]["fixes"] + ["review: " + iss["msg"]]
        report["mode"] = profile["name"]
        report["at"] = time.time()
        write_json(pr.p("review.json"), report)
        ctx.log(f"review: {report['fixed']} problems fixed automatically, {report['open']} left for you to look at")
    for i, fixed in finished.items():
        pr.save_scene(i, fixed)
    if finished:
        finish_storyboard(ctx, pr, script, beats, {**{i: sc for i, sc in everything.items() if sc}, **finished}, analyses, plan_info,
                          tracker, registry, reqs, report if finished else None, made)
    info["scenes"] = made
    info["themes"] = vthemes
    info["engine"] = engine
    info["mode"] = profile["name"]
    write_json(pr.p("storyboard.json"), info)
    if plan_info:
        old = (read_json(pr.p("plan.json"), {}) or {}).get("beats") or {}
        old.update({str(i): v for i, v in plan_info.items()})
        write_json(pr.p("plan.json"), dict(beats=old, engine=engine, patterns_version=DR.PT.version(), at=time.time()))
    tracker.save((read_json(pr.p("review.json"), {}) or {}).get("issues") if finished else None)
    ctx.progress(0.7, "rendering previews")
    render_previews(ctx, [i for i in range(n) if i in todo or not os.path.exists(pr.preview_path(i))], 0.7, 1.0)
    ctx.progress(1.0, f"{n} scenes")


def finish_storyboard(ctx, pr, script, beats, final, analyses, plan_info, tracker, registry, reqs, report, made):
    """After the review: time-jump checks on the world state, the muted-video test, the structured scene specs, the
    storyboard preview page and the used-sources file. All local; nothing here asks the AI anything."""
    durs = [d for d, _ in beat_durations(pr, beats)]
    extra = WD.check(tracker.worlds, beats, final)
    covs = {i: SM.coverage(reqs[i], final[i]) for i in reqs if final.get(i)}
    muted = MU.run(final, analyses, beats, tracker.worlds, {str(i): c["score"] for i, c in covs.items()})
    if report is not None:
        report["issues"] += extra
        report["open"] += len([x for x in extra if x["severity"] in ("medium", "high")])
        report["muted"] = muted
        report["coverage"]["per_beat"] = {str(i): c["score"] for i, c in covs.items()}
        report["coverage"].update(CVG.summary(covs))
        report["coverage"]["missing"] = {str(i): [f"{m['value']} ({m['kind']})" for m in c["must_missing"]] for i, c in covs.items() if c["must_missing"]}
        write_json(pr.p("review.json"), report)
    claims = read_json(pr.p("research", "claims.json"), []) or []
    claims_by_beat = {}
    for c in claims:
        for b in c.get("used_in_scenes") or []:
            claims_by_beat.setdefault(b, []).append(c["id"])
    old_plan = (read_json(pr.p("plan.json"), {}) or {}).get("beats") or {}
    plan_all = {int(k): v for k, v in old_plan.items()}
    plan_all.update(plan_info or {})
    specs = SP.write_all(pr, beats, final, analyses, plan_all, covs, tracker.worlds, durs, registry, claims_by_beat,
                         layout=(report or {}).get("layout"))
    used = used_sources(pr)
    page = SP.preview_html(script.get("title") or "", specs, muted, used)
    os.makedirs(pr.p("storyboard"), exist_ok=True)
    with open(pr.p("storyboard", "preview.html"), "w", encoding="utf-8") as f:
        f.write(page)
    lay = (report or {}).get("layout") or {}
    ctx.log(f"storyboard check: coverage {int(round(100 * CVG.summary(covs)['mean']))}%, muted-video test {int(round(100 * muted['score']))}%, "
            f"layout {int(round(100 * lay.get('mean', 1)))}% ({len(lay.get('open') or [])} open), "
            f"{len(muted['weak'])} weak scene(s); specs and preview.html written")


def ai_fix_open(ctx, llm, report, finished, beats, custom, cast, limit=8):
    """Deep mode: hand the writer, in ONE request, only the scenes the local review could not fix (at most `limit`)."""
    open_by_beat = {}
    for iss in report["issues"]:
        if not iss["fixed"] and iss["severity"] in ("medium", "high") and iss["beat"] in finished:
            open_by_beat.setdefault(iss["beat"], []).append(iss["msg"])
    items = [(i, beats[i], finished[i], msgs) for i, msgs in list(open_by_beat.items())[:limit]]
    if not items:
        return
    try:
        data = call_llm(ctx, llm, PR.STORYBOARD_SYSTEM, PR.fix_scenes_prompt(items), label=f"fix scenes {items[0][0]}-{items[-1][0]}")
    except Exception as e:
        ctx.log(f"couldn't ask the writer to fix {len(items)} scenes: {str(e)[:100]}")
        return
    for it in (data.get("scenes") if isinstance(data, dict) else data) or []:
        i = it.get("beat") if isinstance(it, dict) else None
        if i not in finished:
            continue
        fixed, _, errs = check_scene(it.get("scene"), beats[i]["mood"], beats[i]["text"], custom, cast)
        if fixed and not errs and fixed.get("elements"):
            n = len(open_by_beat.get(i, []))
            finished[i] = fixed
            report["fixed"] += n
            report["open"] = max(0, report["open"] - n)


def cached_props(text):
    """Custom props an earlier video already had drawn (the Rosetta Stone, a Spitfire) whose names appear in `text`."""
    idx = CA.get("props", "_index") or {}
    low = str(text or "").lower()
    out = []
    for name, k in idx.items():
        words = [w for w in name.split("_") if len(w) >= 4] or name.split("_")
        if words and all(w in low for w in words):
            d = CA.get("props", k)
            if d:
                out.append(d)
    return out


def remember_props(kit):
    idx = CA.get("props", "_index") or {}
    for d in kit or []:
        k = CA.key("prop", d.get("name"))
        CA.put("props", k, d, dict(name=d.get("name")))
        idx[d["name"]] = k
    if kit:
        CA.put("props", "_index", idx)


def design_props(ctx, llm, script, beats, vthemes, kit_text, current):
    """Ask the writer once per script for a few props this story needs that the library doesn't have.
    Saved in props.json; reused until the script changes. Props drawn for earlier videos are reused from the cache
    (and the AI isn't asked at all when the cache already covers the story). A failure here never stops the storyboard."""
    pr = ctx.project
    key = h(script.get("title", ""), script.get("topic", ""), [b["text"] for b in beats])
    saved = read_json(pr.p("props.json"), {}) or {}
    if saved.get("key") == key:
        return saved.get("props") or []
    if not (load_settings().get("custom_props", True)):
        return current or []
    have = cached_props(" ".join(b.get("text", "") for b in beats))
    if len(have) >= 4:
        ctx.log("props: reused " + ", ".join(d["name"] for d in have) + " from earlier videos (no AI call)")
        write_json(pr.p("props.json"), dict(key=key, props=have, themes=vthemes, at=time.time(), cached=True))
        return have
    try:
        data = call_llm(ctx, llm, PR.PROP_DESIGN_SYSTEM,
                        PR.prop_design_prompt(script.get("title", ""), script.get("topic", ""), beats, kit_text),
                        label="props", tries=1, until=0.06)
        kit = clean_kit(data, PROPS)
    except Exception as e:
        ctx.warn(f"couldn't design custom props, using the library only: {str(e)[:160]}")
        return have or current or []
    names = {d["name"] for d in kit}
    kit = kit + [d for d in have if d["name"] not in names]
    remember_props(kit)
    write_json(pr.p("props.json"), dict(key=key, props=kit, themes=vthemes, at=time.time()))
    if kit:
        ctx.log("designed props: " + ", ".join(d["name"] for d in kit))
        try:
            kit_sheet(kit, pr.p("props.png"))
        except Exception as e:
            ctx.log(f"couldn't draw the props sheet: {e}")
    return kit


def as_rendered(scene, i, beats, settings, plan=None, opts=None):
    """The scene as it is rendered: the stored scene, plus the host's cameo on a big moment, minus the automatic
    reactions or camera moves when they're switched off in Settings."""
    if not isinstance(scene, dict):
        return scene
    opts = opts or {}
    if opts.get("mascot", True) is not False:
        withc = MA.with_cameo(scene, i, beats, settings, plan)
        if withc is not scene:                 # the host's cameo is a flourish: it never gets to collide with the scene
            n0 = len(scene.get("elements") or [])
            clash = [x for x in LY.audit(withc, dict(text=(beats[i] or {}).get("text", ""))) if x["sev"] in ("high", "medium") and any(k >= n0 for k in x["idx"])]
            scene = scene if clash else withc
    if settings.get("auto_reactions", True) is False and scene.get("react") is not False:
        scene = dict(scene, react=False)
    if settings.get("auto_camera", True) is False:
        cam = dict(scene.get("camera") or {})
        if cam.get("auto_shots") is not False or cam.get("pan") is not False:
            cam.update(auto_shots=False, pan=False)
            scene = dict(scene, camera=cam)
    return scene


def scene_job(pr, i, beats, durs):
    dur, wt = durs[i]
    opts = (pr.meta() or {}).get("options") or {}
    scene = as_rendered(read_json(pr.scene_path(i)), i, beats, load_settings(), opts=opts)
    return dict(idx=i, scene=scene, dur=dur, mood=beats[i]["mood"], text=beats[i]["text"], word_times=wt)


def render_previews(ctx, indices, p0=0.0, p1=1.0):
    pr = ctx.project
    beats = pr.script()["beats"]
    durs = beat_durations(pr, beats)
    os.makedirs(pr.p("previews"), exist_ok=True)
    jobs = [(scene_job(pr, i, beats, durs), pr.preview_path(i)) for i in indices if os.path.exists(pr.scene_path(i))]
    if not jobs:
        return
    warns = {}
    with cf.ProcessPoolExecutor(max_workers=workers(), mp_context=mp.get_context("spawn")) as ex:
        futs = {ex.submit(render_still, j, out, 0.85, (640, 360), True): j["idx"] for j, out in jobs}
        for k, fut in enumerate(cf.as_completed(futs)):
            i = futs[fut]
            try:
                w = fut.result()
                if w:
                    warns[i] = w
            except Exception as e:
                warns[futs[fut]] = [f"preview failed: {e}"]
            ctx.progress(p0 + (p1 - p0) * (k + 1) / len(jobs), f"preview {k + 1}/{len(jobs)}")
    if warns:
        info = read_json(pr.p("storyboard.json"), {}) or {}
        for i, w in warns.items():
            info.setdefault("scenes", {}).setdefault(str(i), {})["warnings"] = w
        write_json(pr.p("storyboard.json"), info)


# ================================================================== voice
def stage_voice(ctx, only=None, force=False):
    pr, meta = ctx.project, ctx.project.meta()
    settings = load_settings()
    opts = meta.get("options") or {}
    beats = pr.script()["beats"]
    vp = provider(meta, "voice")
    ok, why = vp.available()
    if not ok:
        raise P.ProviderError(f"{vp.label} is not available: {why}")
    vs = dict(settings["voice"], **(opts.get("voice") or {}))
    voice = {"kokoro": vs.get("kokoro_voice"), "elevenlabs": vs.get("elevenlabs_voice_id"),
             "system": vs.get("system_voice") or "default"}.get(vp.id)
    speed = float(vs.get("kokoro_speed") or 1.2) if vp.id == "kokoro" else 1.1
    pron = settings.get("pronunciations") or {}
    prev = pr.voice() or {}
    same = prev.get("provider") == vp.id and prev.get("voice") == voice and prev.get("speed") == speed
    old = (prev.get("beats") or []) if same else []
    entries = [None] * len(beats)
    todo = []
    by_mood = opts.get("mood_narration", settings.get("mood_narration", True)) is not False
    for i, b in enumerate(beats):
        spoken = prep(b["text"], pron)
        bs, pad = narration(b["mood"], speed, vp.id) if by_mood else (speed, 0.0)
        reuse = (not force and i < len(old) and old[i] and old[i].get("text") == b["text"]
                 and old[i].get("spoken") == spoken and os.path.exists(pr.audio_path(i))
                 and old[i].get("speed", speed) == bs and old[i].get("pad", 0.0) == pad
                 and (only is None or i not in only))
        if reuse:
            entries[i] = old[i]
        else:
            todo.append((i, b, spoken))
    os.makedirs(pr.p("audio"), exist_ok=True)
    before = measure_credits(vp)
    done = [0]

    def synth(item):
        i, b, spoken = item
        bs, pad = narration(b["mood"], speed, vp.id) if by_mood else (speed, 0.0)
        s, sr, al = vp.synthesize(spoken, voice, bs)
        s = np.asarray(s, dtype=np.float32)
        if pad:
            s = np.concatenate([s, np.zeros(int(pad * sr), dtype=np.float32)])   # a breath before moving on
        sf.write(pr.audio_path(i), s, sr)
        wt = None
        if al:
            wt = word_times_from_alignment(b["text"], pron, al["chars"], al["starts"], al["ends"])
        return i, dict(text=b["text"], spoken=spoken, dur=round(len(s) / sr, 3), sr=sr, word_times=wt, speed=bs,
                       pad=pad)

    if todo:
        ctx.log(f"voice: generating {len(todo)} of {len(beats)} lines with {vp.label}")
        if vp.id == "kokoro":
            vp._load(progress=lambda msg, f: ctx.progress(0.02, f"{msg} {int(f * 100)}%"))
        par = 3 if vp.paid else 1
        try:
            with cf.ThreadPoolExecutor(max_workers=par) as ex:
                for i, e in ex.map(synth, todo):
                    entries[i] = e
                    done[0] += 1
                    ctx.progress(done[0] / len(todo), f"line {done[0]}/{len(todo)}")
                    ctx.check_cancel()
        finally:
            record_credits(ctx, vp, before, f"voice for {len(todo)} lines")
    total = sum(e["dur"] for e in entries if e)
    write_json(pr.p("audio", "voice.json"), dict(provider=vp.id, voice=voice, speed=speed, beats=entries,
                                                 total=round(total, 2)))
    ctx.progress(1.0, f"{total / 60:.1f} min of narration")


# how the narrator reads each mood: (speed factor, seconds of pause after the line)
MOOD_READING = {"fun": (1.05, 0.0), "tense": (0.98, 0.15), "somber": (0.86, 0.55)}
SPEED_RANGE = {"elevenlabs": (0.7, 1.2), "kokoro": (0.5, 2.0)}


def narration(mood, speed, provider_id):
    """(speed, pause) for a line: slower with a pause for sad moments, a little punchier for jokes."""
    k, pad = MOOD_READING.get(mood, (1.0, 0.0))
    lo, hi = SPEED_RANGE.get(provider_id, (0.5, 2.0))
    return round(max(lo, min(speed * k, hi)), 3), pad


# ================================================================== render
def layout_prepare(ctx, pr, beats):
    """Right before rendering, every scene is laid out once more (a scene can have been edited by hand since the
    storyboard stage): collisions, margins, sizes and close-ups are repaired locally and the fix is saved with the scene,
    so what is rendered is what was checked. Returns {beat: [problems that could not be fixed by moving things]}."""
    left, changed = {}, 0
    for i, b in enumerate(beats):
        if b.get("host") or not os.path.exists(pr.scene_path(i)):
            continue
        sc = read_json(pr.scene_path(i))
        if not isinstance(sc, dict):
            continue
        lc = dict(text=b.get("text", ""))
        _, fixes, _ = LY.fix_scene(sc, lc)
        if fixes:
            write_json(pr.scene_path(i), sc)
            changed += 1
        high = [x for x in LY.audit(sc, lc) if x["sev"] == "high"]
        if high:
            left[i] = high
    if changed:
        ctx.log(f"layout: repaired {changed} scene(s) before rendering (moved text and objects, no AI used)")
    return left


def layout_gate(left, idxs, opts, settings):
    """A scene that still has a serious layout problem after every local repair is not rendered: it would look wrong and
    the only cure left is a new layout. 'Render anyway' (options.allow_layout_issues) or Settings > layout_gate: warn lets it through."""
    blocked = [i for i in idxs if i in left]
    if not blocked or opts.get("allow_layout_issues") or settings.get("layout_gate", "block") != "block":
        return
    lines = "; ".join(f"scene {i + 1}: " + left[i][0]["msg"] for i in blocked[:4])
    raise P.ProviderError(f"{len(blocked)} scene(s) still have a layout problem that moving things around could not fix, so they were not "
                          f"rendered: {lines}. Redraw them in the Storyboard tab (Deep mode asks the writer for a new layout "
                          f"automatically), or choose 'Render anyway'.")


def coverage_gate(pr, idxs, opts, settings):
    """Don't render scenes that obviously don't show what the narration says (the review's coverage below COVERAGE_BLOCK
    after every repair). 'Render anyway' (options.allow_low_coverage) or Settings > coverage_gate: warn lets them through."""
    cov = (read_json(pr.p("review.json"), {}) or {}).get("coverage") or {}
    blocked = [i for i in idxs if i in set(cov.get("blocked") or [])]
    if not blocked or opts.get("allow_low_coverage") or settings.get("coverage_gate", "block") != "block":
        return
    miss = cov.get("missing") or {}
    lines = "; ".join(f"scene {i + 1} covers {cov.get('per_beat', {}).get(str(i), 0):.0%} (missing: "
                      + ", ".join(miss.get(str(i), [])[:3]) + ")" for i in blocked[:4])
    raise P.ProviderError(f"{len(blocked)} scene(s) don't show what the narration says, so they were not rendered: {lines}. "
                          f"Redraw them in the Storyboard tab, or choose 'Render anyway'.")


def stage_render(ctx, only=None, force=False):
    pr = ctx.project
    beats = pr.script()["beats"]
    v = pr.voice()
    vb = v.get("beats") or []
    if len(vb) != len(beats) or any(not e or e.get("text") != b["text"] for e, b in zip(vb, beats)):
        raise P.ProviderError("the voice is out of date with the script; run the Voice stage first")
    frames, starts, durs = plan_timeline([e["dur"] for e in vb])
    os.makedirs(pr.p("segments"), exist_ok=True)
    manifest = read_json(pr.p("segments", "manifest.json"), {}) or {}
    info = pr.render_info()
    sfx = {int(k): v for k, v in (info.get("sfx") or {}).items()}
    warns = {int(k): v for k, v in (info.get("warnings") or {}).items()}
    jobs = []
    opts = pr.meta().get("options") or {}
    settings = load_settings()
    wm = opts.get("watermark") or ""
    cap_style = opts.get("caption_style") or settings.get("caption_style", "highlight")
    use_tr = opts.get("transitions", settings.get("transitions", True)) is not False
    cameos = MA.cameo_plan(beats, settings) if opts.get("mascot", True) is not False else {}
    unresolved = layout_prepare(ctx, pr, beats)
    scenes = [as_rendered(read_json(pr.scene_path(i)), i, beats, settings, cameos, opts) for i in range(len(beats))]
    for i, b in enumerate(beats):
        scene = scenes[i]
        if scene is None:
            raise P.ProviderError(f"scene {i} is missing; run the Storyboard stage first")
        prev = scenes[i - 1] if i > 0 else None
        kind = pick_transition(prev, scene, i, b["mood"], beats[i - 1]["mood"] if i else "fun") if use_tr else "cut"
        prev_job = None
        if kind != "cut" and prev is not None:
            prev_job = dict(idx=i - 1, scene=prev, dur=durs[i - 1], mood=beats[i - 1]["mood"], text=beats[i - 1]["text"],
                            word_times=vb[i - 1].get("word_times"))
        key = h(scene, b, frames[i], vb[i].get("word_times"), wm, ENGINE_VERSION, cap_style, kind,
                h(prev_job) if prev_job else None)
        up_to_date = manifest.get(str(i)) == key and os.path.exists(pr.segment_path(i))
        if not (force or not up_to_date or (only is not None and i in only)):
            continue
        jobs.append((key, dict(idx=i, scene=scene, dur=durs[i], mood=b["mood"], text=b["text"],
                               word_times=vb[i].get("word_times"), frames=frames[i], out=pr.segment_path(i),
                               captions=opts.get("captions", True), watermark=wm, caption_style=cap_style,
                               transition=kind, prev=prev_job)))
    coverage_gate(pr, [j["idx"] for _, j in jobs], opts, settings)
    layout_gate(unresolved, [j["idx"] for _, j in jobs], opts, settings)
    ctx.log(f"render: {len(jobs)} of {len(beats)} scenes need rendering ({workers()} workers)")
    t0 = time.time()
    total_frames = sum(j["frames"] for _, j in jobs) or 1
    done_frames = 0
    if jobs:
        # longest scenes first for better load balancing
        jobs.sort(key=lambda kj: -kj[1]["frames"])
        with cf.ProcessPoolExecutor(max_workers=workers(), mp_context=mp.get_context("spawn")) as ex:
            futs = {ex.submit(render_segment, j): (k, j) for k, j in jobs}
            for n_done, fut in enumerate(cf.as_completed(futs), 1):
                k, j = futs[fut]
                res = fut.result()
                manifest[str(j["idx"])] = k
                sfx[j["idx"]] = res["sfx"]
                warns[j["idx"]] = res["warnings"]
                done_frames += j["frames"]
                el = time.time() - t0
                eta = el / done_frames * (total_frames - done_frames)
                ctx.progress(done_frames / total_frames, f"scene {n_done} of {len(jobs)}, ETA {int(eta // 60)}:{int(eta % 60):02d}")
                write_json(pr.p("segments", "manifest.json"), manifest)
                ctx.check_cancel()
    write_json(pr.p("segments", "render.json"), dict(starts=starts, durs=durs, frames=frames, total=sum(frames) / 30,
                                                     sfx={str(k): v for k, v in sfx.items()},
                                                     warnings={str(k): v for k, v in warns.items() if v}))
    for i, w in warns.items():
        for msg in w or []:
            ctx.log("warning: " + msg)
    ctx.progress(1.0, f"{len(beats)} scenes, {sum(frames) / 30 / 60:.1f} min")


# ================================================================== mix
def resample(x, sr):
    if sr == SR:
        return np.asarray(x, dtype=np.float64)
    from ..engine.dsp import resample_poly
    from math import gcd
    g = gcd(SR, sr)
    return resample_poly(np.asarray(x, dtype=np.float64), SR // g, sr // g)


def stage_mix(ctx):
    pr, meta = ctx.project, ctx.project.meta()
    opts = meta.get("options") or {}
    settings = load_settings()
    beats = pr.script()["beats"]
    info = pr.render_info()
    starts, durs = info["starts"], info["durs"]
    total = info["total"]
    clips = []
    for i in range(len(beats)):
        x, sr = sf.read(pr.audio_path(i), dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        clips.append(resample(x, sr))
    events = []
    for i, ev in (info.get("sfx") or {}).items():
        events += [(starts[int(i)] + t, k) for t, k in ev]
    mp = provider(meta, "music")
    beds, music_file = None, None
    if mp.id == "upload":
        music_file = opts.get("music_file")
        if music_file and not os.path.isabs(music_file):
            music_file = pr.p(music_file)
        if not music_file or not os.path.exists(music_file):
            ctx.warn("No uploaded music file found; using the built-in synth instead.")
            music_file = None
    elif mp.paid:
        ok, why = mp.available()
        if not ok:
            raise P.ProviderError(f"{mp.label} is not available: {why}")
        before = measure_credits(mp)
        try:
            paths = mp.beds({b["mood"] for b in beats}, total, pr.p("music"),
                            progress=lambda msg, f: ctx.progress(0.3 * f, msg))
        finally:
            record_credits(ctx, mp, before, "music")
        beds = {m: load_audio(pth) for m, pth in paths.items()}
    ctx.progress(0.35, "mixing voice, music and sound effects")
    os.makedirs(pr.p("final"), exist_ok=True)
    raw = pr.p("final", "mix_raw.wav")
    with ctx.working("mixing voice, music and sound effects", expect=10 + total / 30, until=0.54):
        ambiences = None
        if opts.get("ambience", settings.get("ambience", True)) is not False:
            ambiences = [ambience_kind(read_json(pr.scene_path(i))) for i in range(len(beats))]
        moods = [b["mood"] for b in beats]
        if not beds and not music_file and opts.get("music_styles", settings.get("music_styles", True)) is not False:
            # the free synth has more styles: epic battles, mysteries, victories, sad moments
            moods = smooth_styles([music_style(b["text"], b["mood"], read_json(pr.scene_path(i)))
                                   for i, b in enumerate(beats)], durs)
            ctx.log("music: " + ", ".join(sorted(set(moods))))
        elif beds:
            moods = [BASE_MOOD.get(m, m) for m in moods]
        if opts.get("music_stings", settings.get("music_stings", True)) is not False and opts.get("sfx", True):
            events += sting_events(beats, starts, durs, pr.voice() or {})
        build_mix(clips, starts, durs, moods, events, total, raw, lead=LEAD, music_beds=beds,
                  music_file=music_file, music_db=float(settings.get("music_db", -13)),
                  use_sfx=opts.get("sfx", True), ambiences=ambiences,
                  talk_blips=opts.get("talk_blips", settings.get("talk_blips", True)) is not False,
                  action_sounds=opts.get("action_sounds", settings.get("action_sounds", True)) is not False,
                  voice_polish=settings.get("voice_polish", True) is not False)
    ctx.progress(0.55, "making the loudness right for YouTube")
    with ctx.working("making the loudness right for YouTube", expect=10 + total / 20, until=0.69):
        loudnorm(raw, pr.p("final", "mix.wav"))
    os.remove(raw)
    ctx.progress(0.7, "putting the final video together")
    with ctx.working("putting the final video together", expect=10 + total / 30, until=0.79):
        concat_segments([pr.segment_path(i) for i in range(len(beats))], pr.p("final", "video.mp4"),
                        pr.p("final", "mix.wav"))
    if opts.get("share_copy", settings.get("share_copy", True)):
        ctx.progress(0.8, "making the small share copy")
        with ctx.working("making the small share copy", expect=15 + total / 4, until=0.98):
            _, kbps = share_copy(pr.p("final", "video.mp4"), pr.p("final", "video_share.mp4"),
                                 float(settings.get("share_max_mb") or 30), total,
                                 height=int(settings.get("share_height", 720) or 0))
        ctx.log(f"share copy at {kbps} kbps")
    ctx.progress(1.0, "final video ready")


def sting_events(beats, starts, durs, voice, gap=15.0):
    """Short musical hits on big moments (a victory, a twist, a war breaking out, a flop), at the word that
    triggers them, at most one every `gap` seconds."""
    from ..engine.timing import WordTimer
    vb = voice.get("beats") or []
    out, last = [], -1e9
    for i, b in enumerate(beats):
        hit = find_sting(b["text"], b["mood"])
        if not hit or starts[i] - last < gap:
            continue
        kind, word = hit
        wt = vb[i].get("word_times") if i < len(vb) and vb[i] else None
        timer = WordTimer(b["text"], durs[i], LEAD, TAIL, wt)
        t = starts[i] + timer.frac(word, 0, default=0.1) * durs[i]
        out.append((t, f"sting:{kind}"))
        last = t
    return out


# ================================================================== package
def fmt_ts(t):
    t = int(round(t))
    hh, rem = divmod(t, 3600)
    mm, ss = divmod(rem, 60)
    return f"{hh}:{mm:02d}:{ss:02d}" if hh else f"{mm}:{ss:02d}"


def build_chapters(chapters, starts, total, min_gap=10.0, beat_texts=None):
    """[(seconds, title)]: first chapter at 0:00, at least min_gap seconds apart, at least 3 if possible."""
    items = []
    for c in chapters or []:
        try:
            b = int(c.get("beat"))
        except (TypeError, ValueError):
            continue
        if 0 <= b < len(starts) and c.get("title"):
            items.append((float(starts[b]), clean_line(c["title"])[:60]))
    items.sort()
    out = []
    for t, title in items:
        if not out:
            out.append((0.0, title))
        elif t - out[-1][0] >= min_gap and total - t >= min_gap:
            out.append((t, title))
    if not out:
        out = [(0.0, "Intro")]
    if out[0][0] != 0.0:
        out[0] = (0.0, out[0][1])
    if len(out) < 3 and total >= 3 * min_gap:
        # pad with evenly spaced chapters so YouTube shows them
        for k in range(1, 4):
            t = total * k / 4
            if all(abs(t - o[0]) >= min_gap for o in out):
                bi = max(i for i, s in enumerate(starts) if s <= t)
                label = (beat_texts[bi] if beat_texts and bi < len(beat_texts) else f"Part {k + 1}")
                out.append((float(starts[bi]), " ".join(label.split()[:4]).rstrip(",.;:")))
        out = sorted(set(out))
    return out


def used_sources(pr):
    """The sources behind claims the finished script actually uses (links claims to beats again, in case the script was
    edited since the research)."""
    d = pr.p("research")
    claims = read_json(os.path.join(d, "claims.json"), []) or []
    sources = read_json(os.path.join(d, "sources.json"), []) or []
    if not claims:
        return []
    beats = (pr.script() or {}).get("beats") or []
    CL.link_scenes(claims, beats)
    write_json(os.path.join(d, "claims.json"), claims)
    return CL.used_sources(claims, sources)


def stage_package(ctx):
    pr, meta = ctx.project, ctx.project.meta()
    opts = meta.get("options") or {}
    script = pr.script()
    info = pr.render_info()
    total = float(info.get("total") or 0)
    llm = provider(meta, "llm", ctx, task="package")
    ctx.progress(0.05, "writing title, description and tags")
    data = None
    if llm.id != "offline" and llm.available()[0] and MD.profile(meta)["package_ai"]:
        try:
            data = call_llm(ctx, llm, "You are a YouTube growth expert for history channels. JSON only.",
                            PR.package_prompt(script, total / 60), schema=PR.PACKAGE_SCHEMA, label="package")
        except Exception as e:
            ctx.warn(f"Couldn't write the YouTube text with the AI ({str(e)[:150]}); used a simple template.")
    if not data:
        data = rules.offline_package(script, total / 60)
    chapters = build_chapters(data.get("chapters"), info["starts"], total,
                              beat_texts=[b["text"] for b in script["beats"]])
    lines = [clean_line(data.get("hook", "")), ""]
    lines.append("Chapters:")
    lines += [f"{fmt_ts(t)} {title}" for t, title in chapters]
    lines += ["", clean_line(data.get("question", "")), ""]
    if meta.get("mode") == "youtube" and opts.get("credit_source", True):
        sm = read_json(pr.p("source", "meta.json"), {}) or {}
        if sm.get("title"):
            lines.append(f"Inspired by \"{sm['title']}\" by {sm.get('channel', '')}: {sm.get('webpage_url') or meta.get('source_url')}")
    used = used_sources(pr)
    if used:                                           # only sources a scene really uses, written next to the video
        md, txt = SP.sources_markdown(script.get("title") or meta.get("title") or "", used)
        os.makedirs(pr.p("final"), exist_ok=True)
        with open(pr.p("final", "sources.md"), "w", encoding="utf-8") as f:
            f.write(md)
        lines += ["", txt]
    lines.append("The narration in this video is an AI-generated voice.")
    tags = [clean_line(t) for t in data.get("tags") or [] if t][:15]
    hashtags = [("#" + re.sub(r"[^A-Za-z0-9]", "", str(t).lstrip("#"))) for t in data.get("hashtags") or [] if t][:3]
    if hashtags:
        lines += ["", " ".join(hashtags)]
    description = "\n".join(lines).strip() + "\n"
    os.makedirs(pr.p("final"), exist_ok=True)
    with open(pr.p("final", "description.txt"), "w", encoding="utf-8") as f:
        f.write(description)
    ctx.progress(0.5, "drawing the thumbnail")
    th = data.get("thumbnail") or {}
    ip = provider(meta, "image")
    bg_img = None
    if ip.paid:
        ok, why = ip.available()
        if ok:
            before = measure_credits(ip)
            try:
                with ctx.working(f"{ip.label} is painting the thumbnail background", expect=40, until=0.9):
                    bg_img = ip.generate(th.get("image_prompt") or script.get("title", ""),
                                         pr.p("final", "thumbnail_bg.png"))
            except Exception as e:
                ctx.warn(f"AI thumbnail art failed, used the built-in one: {str(e)[:150]}")
            finally:
                record_credits(ctx, ip, before, "thumbnail image")
        else:
            ctx.warn(f"{ip.label} not available ({why}); used the built-in thumbnail.")
    coat_of = {resolve_kind(c.get("kind")): c.get("coat") for c in script.get("cast") or [] if c.get("coat")}
    small, big = th.get("small_kind") or "civ", th.get("big_kind") or "crown"
    render_thumbnail(pr.p("final", "thumbnail.png"), th.get("line1") or script.get("title", "")[:20],
                     th.get("line2") or "", small, big, background_image=bg_img, prop=th.get("prop") or None,
                     small_coat=coat_of.get(resolve_kind(small)), big_coat=coat_of.get(resolve_kind(big)))
    yt = dict(titles=[clean_line(t)[:100] for t in data.get("titles") or []][:3], description=description, tags=tags,
              hashtags=hashtags, chapters=[dict(time=fmt_ts(t), seconds=t, title=title) for t, title in chapters],
              question=clean_line(data.get("question", "")), thumbnail="final/thumbnail.png",
              video="final/video.mp4", share="final/video_share.mp4" if os.path.exists(pr.p("final", "video_share.mp4")) else None,
              duration=total)
    write_json(pr.p("final", "youtube.json"), yt)
    ctx.progress(1.0, "ready to post")


def stage_shorts(ctx):
    from .shorts import stage_shorts as run_shorts
    return run_shorts(ctx)


STAGE_FUNCS = {"source": stage_source, "script": stage_script, "storyboard": stage_storyboard, "voice": stage_voice,
               "render": stage_render, "mix": stage_mix, "package": stage_package, "shorts": stage_shorts}
