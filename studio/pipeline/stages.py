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
from .. import prompts as PR
from . import rules, costs, themes as TH
from .project import read_json, write_json
from ..engine.custom_props import clean_kit, kit_sheet
from ..engine.registry import PROPS
from .source import (fetch_meta, transcript_text, download_lowres, extract_frames, thumbnail_frames, contact_sheets,
                     hints_for_beats)


class Cancelled(Exception):
    pass


def h(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def provider(meta, stage, ctx=None):
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


def call_llm(ctx, llm, system, prompt, schema=None, images=(), label="", parse=True, tries=2, until=None, web=False):
    last = None
    kind = label.split()[0] if label else ""
    for attempt in range(tries):
        ctx.check_cancel()
        who = getattr(llm, "short", "The AI")
        with ctx.working(ctx.msg if ctx.msg and kind not in SAYING else SAYING.get(kind, ctx.msg or "working").format(who=who),
                         expect=EXPECT.get(kind, 45), until=until):
            text, usage = llm.complete(system, prompt, schema=schema, images=images, label=label,
                                       **({"web": True} if web and getattr(llm, "supports_web", False) else {}))
        if usage.get("billed_usd"):
            costs.record(ctx.project, ctx.stage, llm.id, usd=usage["billed_usd"],
                         note=f"{label}: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out tokens")
        if not parse:
            return text
        try:
            return P.extract_json(text)
        except Exception as e:
            last = e
            ctx.log(f"{label}: reply was not valid JSON, retrying ({e})")
            prompt = prompt + "\n\nIMPORTANT: your previous answer was not valid JSON. Reply with valid JSON only."
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
    llm = provider(meta, "llm", ctx)
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
        beats.append({"mood": mood, "text": t})
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
            cast.append(dict(name=str(c["name"])[:40], kind=resolve_kind(c.get("kind")), hat_color=c.get("hat_color") or ""))
    return dict(title=clean_line(data.get("title") or fallback_title), topic=clean_line(data.get("topic") or fallback_title),
                beats=beats, facts=facts, cast=cast)


def source_bundle(pr, meta):
    m = read_json(pr.p("source", "meta.json"), {}) or {}
    segs = read_json(pr.p("source", "transcript.json"), []) or []
    vn = read_json(pr.p("source", "visual_notes.json"))
    return dict(title=m.get("title", ""), channel=m.get("channel", ""), duration=m.get("duration"),
                description=m.get("description", ""), chapters=m.get("chapters") or [], segments=segs,
                transcript_text=transcript_text(segs), visual_notes=vn)


def stage_script(ctx):
    pr, meta = ctx.project, ctx.project.meta()
    opts = meta.get("options") or {}
    llm = provider(meta, "llm", ctx)
    minutes = float(opts.get("minutes") or 10)
    youtube = meta.get("mode") == "youtube"
    src = source_bundle(pr, meta) if (youtube or opts.get("style_url")) else None
    ctx.progress(0.05, "writing the script")
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
        prompt = PR.script_prompt(meta.get("topic") or "", minutes, opts.get("tone") or "funny but respectful",
                                  style_notes, src if youtube else None, opts.get("faithfulness") or "balanced",
                                  opts.get("extra") or "")
        data = call_llm(ctx, llm, PR.SCRIPT_SYSTEM, prompt, schema=PR.SCRIPT_SCHEMA, label="script")
        script = normalize_script(data, meta.get("topic") or (src or {}).get("title", ""))
    script["generated_by"] = llm.id
    script["created"] = time.time()
    if llm.id != "offline" and opts.get("fact_check", load_settings().get("fact_check", True)) is not False:
        ctx.progress(0.6, "fact-checking")
        try:
            fact_check(ctx, llm, script)
        except P.ProviderError as e:
            ctx.warn(f"couldn't fact-check the script (it was kept as written): {str(e)[:200]}")
    pr.save_script(script)
    if not meta.get("title") or meta.get("title") in (meta.get("source_url"), meta.get("topic")):
        pr.update(title=script.get("title") or meta.get("title"))
    words = sum(len(b["text"].split()) for b in script["beats"])
    ctx.log(f"script: {len(script['beats'])} beats, {words} words (~{words / 150:.1f} min), {len(script.get('facts', []))} facts")
    ctx.progress(1.0, f"{len(script['beats'])} beats")


def fact_check(ctx, llm, script):
    """Double-check the claims the writer wasn't sure about (Claude Code searches the web for them), fix beats
    that got something wrong, and keep a report in script["factcheck"]. Changes `script` in place."""
    facts = script.get("facts") or []
    beats = script.get("beats") or []
    web = bool(getattr(llm, "supports_web", False))
    data = call_llm(ctx, llm, PR.FACTCHECK_SYSTEM, PR.factcheck_prompt(script, web), schema=PR.FACTCHECK_SCHEMA,
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
    pr, meta = ctx.project, ctx.project.meta()
    script = pr.script()
    beats, cast = script["beats"], script.get("cast") or []
    n = len(beats)
    info = read_json(pr.p("storyboard.json"), {}) or {}
    made = info.get("scenes") or {}
    todo = []
    for i in (only if only is not None else range(n)):
        key = h(beats[i]["text"], beats[i]["mood"])
        if force or not os.path.exists(pr.scene_path(i)) or made.get(str(i), {}).get("key") != key:
            todo.append(i)
    llm = provider(meta, "llm", ctx)
    hints = {}
    if meta.get("mode") == "youtube":
        vn = read_json(pr.p("source", "visual_notes.json"))
        sm = read_json(pr.p("source", "meta.json"), {}) or {}
        hints = hints_for_beats(vn, n, float(sm.get("duration") or 0))
    raw = {}
    vthemes = TH.detect(script.get("title", ""), script.get("topic", ""), beats)
    kit_text = TH.kit_block(vthemes)
    custom = pr.prop_kit()
    if todo and llm.id != "offline":
        ok, why = llm.available()
        if not ok:
            raise P.ProviderError(f"{llm.label} is not available: {why}")
        custom = design_props(ctx, llm, script, beats, vthemes, kit_text, custom)
        # free API writers have small per-minute limits: they get fewer scenes (and examples) per request
        size = max(1, int(getattr(llm, "batch_beats", 8) or 8))
        n_ex = int(getattr(llm, "examples", 20))
        compact = bool(getattr(llm, "compact", False))
        batches = [todo[k:k + size] for k in range(0, len(todo), size)]
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
            n_ex = min(n_ex, int(getattr(llm, "examples", 20)))
            prompt = PR.storyboard_prompt([(i, beats[i]) for i in idx], beats, cast, script.get("title", ""), hints,
                                          kit_text=kit_text, custom=custom, examples=n_ex,
                                          compact=compact or bool(getattr(llm, "compact", False)))
            if instruction:
                prompt += f"\n\nEXTRA DIRECTION FROM THE USER: {instruction}"
            data = call_llm(ctx, llm, PR.STORYBOARD_SYSTEM, prompt, label=f"storyboard {idx[0]}-{idx[-1]}")
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

        ctx.progress(0.02, f"drawing {len(todo)} scenes")
        par = max(1, int(getattr(llm, "parallel", 3) or 3))
        rounds = (len(batches) + par - 1) // par
        with ctx.working(f"{who} is drawing up {len(todo)} scenes", expect=75 * rounds, until=0.64), \
                cf.ThreadPoolExecutor(max_workers=par) as ex:
            futs = {ex.submit(run_batch, b): b for b in batches}
            for fut in cf.as_completed(futs):
                b = futs[fut]
                try:
                    raw.update(fut.result())
                except Exception as e:
                    ctx.warn(f"storyboard batch {b[0]}-{b[-1]} failed: {str(e)[:200]}")
                done[0] += len(b)
                ctx.progress(0.05 + 0.6 * done[0] / len(todo), f"{who} drew {done[0]} of {len(todo)} scenes")
    finished = {}
    for i in todo:
        ctx.check_cancel()
        beat = beats[i]
        sc = raw.get(i)
        talk = TH.ensure_dialogue(sc, beat["text"], beat["mood"], cast, TH.beat_themes(beat["text"], vthemes), i)
        fixed, fixes, errs = check_scene(sc, beat["mood"], beat["text"], custom) if sc else (None, [], ["missing"])
        if talk:
            fixes = ["gave the speaker a line"] + fixes
        if (errs or not (fixed or {}).get("elements")) and llm.id != "offline" and sc is not None:
            try:
                data = call_llm(ctx, llm, PR.STORYBOARD_SYSTEM, PR.fix_scene_prompt(sc, errs or ["no elements"], beat),
                                label=f"fix scene {i}")
                fixed, fixes2, errs = check_scene(data, beat["mood"], beat["text"], custom)
                fixes = fixes + ["asked the writer to fix it"] + fixes2
            except Exception as e:
                errs = [str(e)]
        source = llm.id
        if fixed is None or errs or not fixed.get("elements"):
            fixed, fixes3, _ = check_scene(rules.rule_scene(beat, i, cast, vthemes), beat["mood"], beat["text"], custom)
            fixes = fixes + ["used a simple rule-based scene"] + fixes3
            source = "rules"
        finished[i] = fixed
        made[str(i)] = dict(key=h(beat["text"], beat["mood"]), fixes=fixes, source=source, at=time.time())
    # two scenes in a row shouldn't look the same: nudge colors / time of day of the new ones
    if finished:
        everything = {i: finished.get(i) or read_json(pr.scene_path(i)) for i in range(n)}
        for i, what in TH.vary(everything, list(range(n)), set(finished)):
            made[str(i)]["fixes"] = made[str(i)]["fixes"] + [f"varied the background ({what})"]
    for i, fixed in finished.items():
        pr.save_scene(i, fixed)
    info["scenes"] = made
    info["themes"] = vthemes
    write_json(pr.p("storyboard.json"), info)
    ctx.progress(0.7, "rendering previews")
    render_previews(ctx, [i for i in range(n) if i in todo or not os.path.exists(pr.preview_path(i))], 0.7, 1.0)
    ctx.progress(1.0, f"{n} scenes")


def design_props(ctx, llm, script, beats, vthemes, kit_text, current):
    """Ask the writer once per script for a few props this story needs that the library doesn't have.
    Saved in props.json; reused until the script changes. A failure here never stops the storyboard."""
    pr = ctx.project
    key = h(script.get("title", ""), script.get("topic", ""), [b["text"] for b in beats])
    saved = read_json(pr.p("props.json"), {}) or {}
    if saved.get("key") == key:
        return saved.get("props") or []
    if not (load_settings().get("custom_props", True)):
        return current or []
    try:
        data = call_llm(ctx, llm, PR.PROP_DESIGN_SYSTEM,
                        PR.prop_design_prompt(script.get("title", ""), script.get("topic", ""), beats, kit_text),
                        label="props", tries=1, until=0.06)
        kit = clean_kit(data, PROPS)
    except Exception as e:
        ctx.warn(f"couldn't design custom props, using the library only: {str(e)[:160]}")
        return current or []
    write_json(pr.p("props.json"), dict(key=key, props=kit, themes=vthemes, at=time.time()))
    if kit:
        ctx.log("designed props: " + ", ".join(d["name"] for d in kit))
        try:
            kit_sheet(kit, pr.p("props.png"))
        except Exception as e:
            ctx.log(f"couldn't draw the props sheet: {e}")
    return kit


def scene_job(pr, i, beats, durs):
    dur, wt = durs[i]
    return dict(idx=i, scene=read_json(pr.scene_path(i)), dur=dur, mood=beats[i]["mood"], text=beats[i]["text"],
                word_times=wt)


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
    scenes = [read_json(pr.scene_path(i)) for i in range(len(beats))]
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
    from scipy.signal import resample_poly
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
                  action_sounds=opts.get("action_sounds", settings.get("action_sounds", True)) is not False)
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
                                 float(settings.get("share_max_mb") or 30), total)
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


def stage_package(ctx):
    pr, meta = ctx.project, ctx.project.meta()
    opts = meta.get("options") or {}
    script = pr.script()
    info = pr.render_info()
    total = float(info.get("total") or 0)
    llm = provider(meta, "llm", ctx)
    ctx.progress(0.05, "writing title, description and tags")
    data = None
    if llm.id != "offline" and llm.available()[0]:
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
