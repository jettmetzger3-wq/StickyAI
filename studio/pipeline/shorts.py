"""Shorts teaser: a vertical (1080x1920) Short to promote the finished video.

Free "stickman" Short: the AI (or a simple rule) picks one continuous 25-55 s run of beats. Those scenes are
re-rendered without the small captions, then ffmpeg puts them on a blurred, zoomed copy of themselves with a title
on top, big captions under the picture and "Full video on the channel" at the end. The audio is cut from the
final mix, so voice, music and sound effects match the main video.

Calliope AI Short (paid): Calliope gets a 90-150 word standalone script for the same moment and makes a fully
AI-illustrated Short. You approve Calliope's exact credit estimate first.
"""
import concurrent.futures as cf
import multiprocessing as mp
import os
import re
import subprocess
import time

from PIL import Image, ImageDraw

from .. import providers as P
from .. import prompts as PR
from ..engine import render_segment, chunk_words
from ..engine.fonts import font
from ..engine.timing import WordTimer, LEAD, TAIL
from ..providers.shorts import find
from . import costs
from .project import read_json, write_json

SW, SH = 1080, 1920
FG_Y = 520                      # top of the 16:9 picture (1080x608)
CAP_Y = 1250                    # top of the caption area
MIN_S, MAX_S = 20.0, 58.0


def _stages():
    from . import stages
    return stages


# ------------------------------------------------------------------ choosing the clip
def rule_pick(beats, durs):
    """Fallback: the first run of beats from the start of the video that fits in ~50 s."""
    s, total, e = 0, 0.0, 0
    for i, d in enumerate(durs):
        if total + d > 50 and total >= MIN_S:
            break
        total += d
        e = i
    words = " ".join(b["text"] for b in beats[s:e + 1]).split()
    return dict(start=s, end=e, title="", script=" ".join(words[:140]), description="", hashtags=["#shorts", "#history"],
                by="rule")


def fix_range(pick, durs):
    n = len(durs)
    s = max(0, min(int(pick.get("start", 0)), n - 1))
    e = max(s, min(int(pick.get("end", s)), n - 1))
    while sum(durs[s:e + 1]) > MAX_S and e > s:
        e -= 1
    while sum(durs[s:e + 1]) < MIN_S and e + 1 < n and sum(durs[s:e + 2]) <= MAX_S:
        e += 1
    pick.update(start=s, end=e)
    return pick


def pick_clip(ctx):
    st = _stages()
    pr, meta = ctx.project, ctx.project.meta()
    script = pr.script()
    beats = script["beats"]
    info = pr.render_info()
    durs = info.get("durs") or [st.est_dur(b["text"]) for b in beats]
    key = st.h([b["text"] for b in beats], durs)
    old = read_json(pr.p("final", "short.json"), {}) or {}
    if old.get("key") == key and old.get("pick"):
        return old["pick"], durs
    llm = st.provider(meta, "llm")
    pick = None
    if llm.id != "offline" and llm.available()[0]:
        try:
            ctx.progress(0.03, "choosing the best moment for the Short")
            pick = st.call_llm(ctx, llm, "You edit YouTube Shorts for a stickman history channel. JSON only.",
                               PR.short_prompt(script, durs, meta.get("title") or script.get("title", "")),
                               schema=PR.SHORT_SCHEMA, label="short")
            pick["by"] = llm.id
        except Exception as e:
            ctx.warn(f"Couldn't pick the Short's moment with the AI ({str(e)[:120]}); used the opening instead.")
    pick = fix_range(pick or rule_pick(beats, durs), durs)
    pick["title"] = st.clean_line(pick.get("title") or script.get("title", ""))[:40]
    pick["script"] = st.clean_line(pick.get("script") or "")
    tags = [("#" + re.sub(r"[^A-Za-z0-9]", "", str(t).lstrip("#"))) for t in pick.get("hashtags") or [] if t]
    pick["hashtags"] = (["#shorts"] + [t for t in tags if t.lower() != "#shorts"])[:3]
    write_json(pr.p("final", "short.json"), dict(old, key=key, pick=pick))
    return pick, durs


# ------------------------------------------------------------------ drawing the overlays
def text_box(text, size, max_w, fill=(255, 255, 255), stroke=8, box=None, pad=28):
    """Wrapped, centred, outlined text as an RGBA image (optionally on a rounded box)."""
    f = font("bold", size)
    words, lines, cur = text.split(), [], ""
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) + 2 * stroke <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = int(size * 1.18)
    widths = [d.textlength(l, font=f) for l in lines] or [0]
    w = int(max(widths)) + 2 * stroke + 2 * pad
    h = lh * len(lines) + 2 * stroke + 2 * pad
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if box:
        dr.rounded_rectangle((0, 0, w - 1, h - 1), radius=34, fill=box)
    for k, l in enumerate(lines):
        x = (w - widths[k]) / 2
        dr.text((x, pad + stroke + k * lh), l, font=f, fill=fill, stroke_width=stroke, stroke_fill=(22, 22, 30))
    return im


def caption_chunks(beats, info, voice, s, e):
    """[(t0, t1, text)] in Short time, 4 words max per chunk, from the real word timing when we have it."""
    out = []
    t_off = info["starts"][s]
    vb = voice.get("beats") or []
    for i in range(s, e + 1):
        b = beats[i]
        dur = info["durs"][i]
        wt = vb[i].get("word_times") if i < len(vb) and vb[i] else None
        timer = WordTimer(b["text"], dur, LEAD, TAIL, wt)
        chunks = chunk_words(timer.words, max_words=4)
        base = info["starts"][i] - t_off
        for k, idx in enumerate(chunks):
            t0 = timer.starts[idx[0]] if k else min(timer.starts[idx[0]], LEAD)
            t1 = timer.starts[chunks[k + 1][0]] if k + 1 < len(chunks) else dur
            out.append((base + t0, base + max(t1, t0 + 0.2), " ".join(timer.words[j] for j in idx)))
    return out


# ------------------------------------------------------------------ the free stickman Short
def make_stickman_short(ctx, pick):
    st = _stages()
    pr = ctx.project
    meta = pr.meta()
    opts = meta.get("options") or {}
    beats = pr.script()["beats"]
    info = pr.render_info()
    voice = pr.voice()
    s, e = pick["start"], pick["end"]
    work = pr.p("shorts")
    os.makedirs(work, exist_ok=True)
    manifest = read_json(os.path.join(work, "manifest.json"), {}) or {}
    vb = voice.get("beats") or []
    wm = opts.get("watermark") or ""
    jobs = []
    for i in range(s, e + 1):
        scene = read_json(pr.scene_path(i))
        key = st.h(scene, beats[i], info["frames"][i], (vb[i] or {}).get("word_times") if i < len(vb) else None, wm)
        out = os.path.join(work, f"s_{i:03d}.mp4")
        if manifest.get(str(i)) == key and os.path.exists(out):
            continue
        jobs.append((key, dict(idx=i, scene=scene, dur=info["durs"][i], mood=beats[i]["mood"], text=beats[i]["text"],
                               word_times=(vb[i] or {}).get("word_times") if i < len(vb) else None,
                               frames=info["frames"][i], out=out, captions=False, watermark=wm)))
    if jobs:
        ctx.progress(0.1, f"drawing {len(jobs)} scenes for the Short")
        with cf.ProcessPoolExecutor(max_workers=st.workers(), mp_context=mp.get_context("spawn")) as ex:
            futs = {ex.submit(render_segment, j): (k, j) for k, j in jobs}
            for n, fut in enumerate(cf.as_completed(futs), 1):
                k, j = futs[fut]
                fut.result()
                manifest[str(j["idx"])] = k
                write_json(os.path.join(work, "manifest.json"), manifest)
                ctx.progress(0.1 + 0.5 * n / len(jobs), f"Short scene {n} of {len(jobs)}")
                ctx.check_cancel()
    t0 = info["starts"][s]
    total = info["starts"][e] + info["durs"][e] - t0
    ctx.progress(0.65, "laying out the vertical video")
    # overlays
    over = []
    title = text_box(pick.get("title") or "", 76, 960, box=(255, 255, 255, 235), fill=(30, 30, 40), stroke=0)
    title_y = max(80, FG_Y - 60 - title.height)
    tpath = os.path.join(work, "title.png")
    title.save(tpath)
    over.append((tpath, (SW - title.width) // 2, title_y, None))
    for k, (a, b, txt) in enumerate(caption_chunks(beats, info, voice, s, e)):
        im = text_box(txt.replace(" ", "  "), 92, 1000, pad=10)
        path = os.path.join(work, f"cap_{k:03d}.png")
        im.save(path)
        over.append((path, (SW - im.width) // 2, CAP_Y, (max(0.0, a), min(total, b))))
    end = text_box("Full video on the channel", 58, 900, box=(255, 214, 10, 240), fill=(30, 30, 40), stroke=0, pad=22)
    epath = os.path.join(work, "end.png")
    end.save(epath)
    over.append((epath, (SW - end.width) // 2, 1640, (max(0.0, total - 3.5), total)))
    # video track: concat the caption-less scenes
    lst = os.path.join(work, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for i in range(s, e + 1):
            f.write("file '" + os.path.abspath(os.path.join(work, f"s_{i:03d}.mp4")).replace("\\", "/").replace("'", "'\\''") + "'\n")
    out = pr.p("final", "short.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
           "-ss", f"{t0:.3f}", "-t", f"{total:.3f}", "-i", pr.p("final", "mix.wav")]
    for path, _, _, _ in over:
        cmd += ["-i", path]
    fg_h = SW * 9 // 16
    graph = [f"[0:v]split=2[a][b]",
             f"[a]scale=-2:{SH},crop={SW}:{SH},gblur=sigma=28,eq=brightness=-0.10[bg]",
             f"[b]scale={SW}:{fg_h}[fg]",
             f"[bg][fg]overlay=0:{FG_Y}[v0]"]
    last = "v0"
    for k, (_, x, y, when) in enumerate(over):
        en = f":enable='between(t,{when[0]:.3f},{when[1]:.3f})'" if when else ""
        graph.append(f"[{last}][{k + 2}:v]overlay={x}:{y}{en}[v{k + 1}]")
        last = f"v{k + 1}"
    fade = max(0.0, total - 0.6)
    graph.append(f"[1:a]afade=t=in:d=0.08,afade=t=out:st={fade:.3f}:d=0.6[aout]")
    script_path = os.path.join(work, "graph.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(";\n".join(graph))
    cmd += ["-filter_complex_script", script_path, "-map", f"[{last}]", "-map", "[aout]", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", "-movflags", "+faststart", out + ".part.mp4"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise P.ProviderError(f"ffmpeg couldn't build the Short: {r.stderr[-400:]}")
    os.replace(out + ".part.mp4", out)
    for f in os.listdir(work):
        if f.startswith("cap_") and f.endswith(".png"):
            os.remove(os.path.join(work, f))
    return dict(path="final/short.mp4", seconds=round(total, 2), kind="stickman")


# ------------------------------------------------------------------ the Calliope AI Short
def calliope_script(pick, beats):
    """Calliope wants 280-1120 characters for a Short: grow with the next (then previous) beats, trim at a sentence."""
    s, e = pick["start"], pick["end"]
    text = pick.get("script") or " ".join(b["text"] for b in beats[s:e + 1])
    k = e + 1
    while len(text) < 300 and k < len(beats):
        text = (text + " " + beats[k]["text"]).strip()
        k += 1
    k = s - 1
    while len(text) < 300 and k >= 0:
        text = (beats[k]["text"] + " " + text).strip()
        k -= 1
    if len(text) > 1100:
        cut = text[:1100]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[:end + 1] if end >= 280 else cut[:cut.rfind(" ")].rstrip(",;:") + "."
    return text


def make_calliope_short(ctx, sp, pick):
    pr = ctx.project
    beats = pr.script()["beats"]
    script = calliope_script(pick, beats)
    if len(script) < 280:
        raise P.ProviderError("the script is too short for a Calliope Short (it needs at least 280 characters)")
    seconds = max(20, min(60, int(len(script.split()) / 2.6)))
    state = read_json(pr.p("final", "short.json"), {}) or {}
    job = (state.get("calliope") or {}).get("job_id") if (state.get("calliope") or {}).get("script") == script else None
    if not job:
        ctx.progress(0.1, "asking Calliope for the exact price")
        cost, raw = sp.quote(seconds)
        pr.update(calliope_quote=dict(cost=cost.to_dict(), seconds=seconds, at=time.time()))
        # now that the exact number is known, it must be approved before anything is spent
        costs.check(pr, "shorts")
        ctx.progress(0.15, "starting the Calliope job")
        job, created = sp.create(script)
        state["calliope"] = dict(job_id=job, script=script, started=time.time())
        write_json(pr.p("final", "short.json"), state)
        costs.record(pr, "shorts", sp.id, usd=cost.usd, credits=cost.credits, note="Calliope AI Short (estimate)")
        ctx.log(f"Calliope job {job} started")
    else:
        ctx.log(f"Calliope job {job} already started; waiting for it")
    raw = sp.wait(job, pr.p("final", "short_ai.mp4"), progress=ctx.progress, check_cancel=ctx.check_cancel)
    real = find(raw, ("credit_cost",))
    state = read_json(pr.p("final", "short.json"), {}) or {}
    state.setdefault("calliope", {}).update(done=time.time(), credit_cost=real)
    write_json(pr.p("final", "short.json"), state)
    return dict(path="final/short_ai.mp4", kind="calliope", job_id=job)


# ------------------------------------------------------------------ stage
def stage_shorts(ctx):
    st = _stages()
    pr, meta = ctx.project, ctx.project.meta()
    sp = st.provider(meta, "shorts")
    if sp.id == "none":
        ctx.progress(1.0, "no Short (turned off)")
        return
    if not os.path.exists(pr.p("final", "mix.wav")):
        raise P.ProviderError("the final mix is missing; run Music & mix first")
    pick, durs = pick_clip(ctx)
    ctx.log(f"Short: beats {pick['start']}-{pick['end']} ({sum(durs[pick['start']:pick['end'] + 1]):.0f} s), "
            f"\"{pick['title']}\" (picked by {pick.get('by', 'rule')})")
    result = None
    if sp.id == "calliope":
        ok, why = sp.available()
        if ok:
            try:
                result = make_calliope_short(ctx, sp, pick)
            except (costs.NeedsApproval, st.Cancelled):
                raise
            except Exception as e:
                ctx.warn(f"Calliope AI Short failed ({str(e)[:200]}); made the free stickman Short instead.")
        else:
            ctx.warn(f"Calliope isn't ready ({why}); made the free stickman Short instead.")
    if result is None or not os.path.exists(pr.p("final", "short.mp4")):
        stick = make_stickman_short(ctx, pick)
        result = result or stick
    state = read_json(pr.p("final", "short.json"), {}) or {}
    state.update(result=result, title=pick["title"],
                 description=(pick.get("description") or "") + "\nFull video: " + (meta.get("title") or ""),
                 hashtags=pick["hashtags"], made=time.time())
    write_json(pr.p("final", "short.json"), state)
    ctx.progress(1.0, "Short ready")
