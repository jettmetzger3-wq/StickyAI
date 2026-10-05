"""FastAPI backend for the dashboard. Runs only on your PC (127.0.0.1)."""
import asyncio
import json
import mimetypes
import os
import shutil
import time

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config, db
from .. import providers as P
from .. import prompts as PR
from ..engine import check_scene, render_still
from ..pipeline import (Project, new_project, list_projects, STAGES, STAGE_LABELS, CHECKPOINTS, start_background,
                        is_running, cancel, mark_reviewed, mark_stale, costs)
from ..pipeline.events import bus
from ..pipeline.project import read_json, write_json
from ..pipeline.stages import beat_durations, scene_job, provider as stage_provider, normalize_script, clean_line

config.ensure_dirs()
app = FastAPI(title="Stickman Studio", docs_url="/api/docs", openapi_url="/api/openapi.json")


def proj(slug):
    pr = Project(slug)
    if not pr.exists():
        raise HTTPException(404, "project not found")
    return pr


def ensure_idle(pr):
    if is_running(pr.slug):
        raise HTTPException(409, "this project is busy; wait for the current step to finish or cancel it")


# ------------------------------------------------------------------ system
@app.get("/api/health")
def health():
    return dict(ok=True, ffmpeg=bool(shutil.which("ffmpeg")), claude=P.get("llm", "claude_cli").available()[0],
                time=time.time(), stages=STAGES, stage_labels=STAGE_LABELS, checkpoints=list(CHECKPOINTS))


@app.get("/api/providers")
def get_providers():
    return dict(catalog=P.catalog(), tiers=P.TIERS, stage_labels=P.STAGE_LABELS,
                notes={"openart": "OpenArt has no public developer API (only an MCP connector inside the Claude app), "
                                  "so this website can't use it. Its free-tier images also carry a watermark.",
                       "mcp": "The ElevenLabs / OpenArt / Higgsfield / Calliope connectors in the Claude app can't be "
                              "reached from a standalone website; paid tools here use their official APIs with your keys."})


@app.get("/api/settings")
def get_settings():
    return dict(settings=config.load_settings(), secrets=config.secrets_status())


@app.put("/api/settings")
def put_settings(body: dict):
    body = {k: v for k, v in body.items() if k in config.DEFAULT_SETTINGS}
    return dict(settings=config.save_settings(body))


class SecretBody(BaseModel):
    name: str
    value: str = ""


@app.put("/api/secrets")
def put_secret(b: SecretBody):
    if b.name not in config.SECRET_KEYS:
        raise HTTPException(400, "unknown key")
    config.set_secret(b.name, b.value.strip())
    return dict(secrets=config.secrets_status())


@app.get("/api/balances")
def balances():
    out = {}
    for stage, items in P.REGISTRY.items():
        for p in items:
            if p.paid and p.available()[0] and p.id not in out:
                try:
                    b = p.balance()
                except Exception:
                    b = None
                if b:
                    out[p.id] = dict(b, label=p.label)
    return dict(balances=out, spent=db.spend_summary())


# ------------------------------------------------------------------ voices
@app.get("/api/voices")
def voices(provider: str = "kokoro"):
    try:
        vp = P.get("voice", provider)
    except KeyError:
        raise HTTPException(404, "unknown voice provider")
    ok, why = vp.available()
    return dict(available=ok, reason=why, voices=vp.voices() if ok or provider == "kokoro" else [])


@app.get("/api/voices/preview")
def voice_preview(provider: str = "kokoro", voice: str = "am_michael", speed: float = 0):
    from ..providers.voice import preview_path, PREVIEW_TEXT
    import soundfile as sf
    if provider == "elevenlabs":
        # ElevenLabs voices come with free preview clips; never spend credits on a preview
        for v in P.get("voice", "elevenlabs").voices():
            if v.get("id") == voice and v.get("preview_url"):
                return dict(url=v["preview_url"])
        raise HTTPException(404, "no free preview for this voice")
    vp = P.get("voice", provider)
    ok, why = vp.available()
    if not ok:
        raise HTTPException(400, why)
    path = preview_path(provider, f"{voice}_{speed or 'd'}")
    if not os.path.exists(path):
        try:
            s, sr, _ = vp.synthesize(PREVIEW_TEXT, voice, speed or None)
        except P.NeedsSetup as e:
            raise HTTPException(400, str(e))
        sf.write(path, s, sr)
    return FileResponse(path, media_type="audio/wav")


# ------------------------------------------------------------------ YouTube source preview + estimates
class SourcePreview(BaseModel):
    url: str


@app.post("/api/source/preview")
def source_preview(b: SourcePreview):
    from ..pipeline.source import fetch_meta
    vid = P.video_id(b.url)
    if not vid:
        raise HTTPException(400, "that doesn't look like a YouTube link")
    try:
        m = fetch_meta(b.url)
    except Exception as e:
        raise HTTPException(400, f"couldn't read that video: {str(e)[:200]}")
    return dict(id=m.get("video_id"), title=m.get("title"), channel=m.get("channel"), duration=m.get("duration"),
                thumbnail=m.get("thumbnail"), chapters=m.get("chapters"), description=(m.get("description") or "")[:600])


class EstimateBody(BaseModel):
    mode: str = "topic"
    minutes: float = 10
    providers: dict = {}
    options: dict = {}
    duration: float | None = None


@app.post("/api/estimate")
def estimate(b: EstimateBody):
    prov = dict(P.TIERS["free"], **(b.providers or {}))
    opts = dict(b.options or {}, minutes=b.minutes)
    est = costs.estimate_draft(b.mode, prov, opts, b.duration)
    return dict(estimate=est, unavailable={st: P.get(st, pid).available()[1] for st, pid in prov.items()
                                           if not P.get(st, pid).available()[0]})


# ------------------------------------------------------------------ projects
class NewProject(BaseModel):
    mode: str = "topic"           # topic | youtube
    url: str = ""
    topic: str = ""
    title: str = ""
    minutes: float = 10
    tone: str = "funny but respectful"
    faithfulness: str = "balanced"
    style_url: str = ""
    extra: str = ""
    watch: bool = True
    autopilot: bool = True
    share_copy: bool = True
    credit_source: bool = True
    providers: dict = {}
    voice: dict = {}
    approve: dict = {}            # {stage: cost dict} the user saw and confirmed
    start: bool = True


@app.post("/api/projects")
def create_project(b: NewProject):
    if b.mode == "youtube" and not P.video_id(b.url):
        raise HTTPException(400, "please paste a valid YouTube link")
    if b.mode == "topic" and not b.topic.strip():
        raise HTTPException(400, "please type a topic")
    prov = dict(P.TIERS["free"], **{k: v for k, v in (b.providers or {}).items() if v})
    for st, pid in prov.items():
        try:
            P.get(st, pid)
        except KeyError:
            raise HTTPException(400, f"unknown provider {pid}")
    opts = dict(minutes=b.minutes, tone=b.tone, faithfulness=b.faithfulness, style_url=b.style_url, extra=b.extra,
                watch=b.watch, autopilot=b.autopilot, share_copy=b.share_copy, credit_source=b.credit_source,
                captions=True, voice=b.voice or {})
    pr = new_project(b.title or (b.topic if b.mode == "topic" else ""), b.mode,
                     source_url=b.url if b.mode == "youtube" else "", topic=b.topic, options=opts, providers=prov)
    if b.approve:
        costs.approve(pr, b.approve)
    if b.start:
        start_background(pr.slug)
    return dict(slug=pr.slug)


@app.get("/api/projects")
def projects():
    out = []
    for m in list_projects():
        pr = Project(m["slug"])
        out.append(dict(slug=m["slug"], title=m.get("title"), mode=m.get("mode"), status=m.get("status"),
                        created=m.get("created"), updated=m.get("updated"), source_url=m.get("source_url"),
                        running=is_running(m["slug"]), minutes=(m.get("options") or {}).get("minutes"),
                        has_video=os.path.exists(pr.p("final", "video.mp4")),
                        has_thumb=os.path.exists(pr.p("final", "thumbnail.png")),
                        stages={k: v.get("status") for k, v in (m.get("stages") or {}).items()},
                        spent_usd=round(sum(c.get("usd") or 0 for c in m.get("costs") or []), 3)))
    return dict(projects=out)


@app.get("/api/projects/{slug}")
def project_detail(slug: str):
    pr = proj(slug)
    m = pr.meta()
    script = pr.script()
    sb = read_json(pr.p("storyboard.json"), {}) or {}
    v = pr.voice() or {}
    ri = pr.render_info()
    n = len((script or {}).get("beats") or [])
    scenes = []
    for i in range(n):
        info = (sb.get("scenes") or {}).get(str(i), {})
        scenes.append(dict(i=i, has_scene=os.path.exists(pr.scene_path(i)), has_preview=os.path.exists(pr.preview_path(i)),
                           preview_v=int(os.path.getmtime(pr.preview_path(i))) if os.path.exists(pr.preview_path(i)) else 0,
                           fixes=info.get("fixes") or [], source=info.get("source"), warnings=(info.get("warnings") or [])
                           + ((ri.get("warnings") or {}).get(str(i)) or []),
                           has_audio=os.path.exists(pr.audio_path(i)),
                           start=(ri.get("starts") or [None] * n)[i] if ri.get("starts") and i < len(ri["starts"]) else None))
    src = None
    if m.get("mode") == "youtube" or (m.get("options") or {}).get("style_url"):
        sm = read_json(pr.p("source", "meta.json"))
        if sm:
            src = dict(title=sm.get("title"), channel=sm.get("channel"), duration=sm.get("duration"),
                       thumbnail=sm.get("thumbnail"), url=sm.get("webpage_url"),
                       has_transcript=os.path.exists(pr.p("source", "transcript.json")),
                       visual_notes=read_json(pr.p("source", "visual_notes.json")),
                       sheets=sorted(os.listdir(pr.p("source", "sheets"))) if os.path.isdir(pr.p("source", "sheets")) else [])
    final = {}
    for k, f in (("video", "video.mp4"), ("share", "video_share.mp4"), ("thumbnail", "thumbnail.png"), ("mix", "mix.wav")):
        path = pr.p("final", f)
        if os.path.exists(path):
            final[k] = dict(path=f"final/{f}", size=os.path.getsize(path), v=int(os.path.getmtime(path)))
    return dict(meta=m, running=is_running(slug), script=script, scenes=scenes, source=src,
                voice=dict(provider=v.get("provider"), voice=v.get("voice"), total=v.get("total"),
                           beats=[dict(dur=(e or {}).get("dur"), text=(e or {}).get("text")) for e in (v.get("beats") or [])]),
                render=dict(total=ri.get("total"), starts=ri.get("starts")), youtube=pr.youtube(), final=final,
                estimate=costs.estimate_all(pr), stage_labels=STAGE_LABELS)


@app.delete("/api/projects/{slug}")
def delete_project(slug: str):
    pr = proj(slug)
    ensure_idle(pr)
    pr.delete()
    db.remove(slug)
    return dict(ok=True)


class RunBody(BaseModel):
    start: str | None = None
    stop_after: str | None = None


@app.post("/api/projects/{slug}/run")
def run_project(slug: str, b: RunBody):
    pr = proj(slug)
    ensure_idle(pr)
    if b.start and b.start not in STAGES:
        raise HTTPException(400, "unknown stage")
    if b.start:
        mark_stale(pr, b.start)
    start_background(slug, start=b.start, stop_after=b.stop_after)
    return dict(ok=True)


@app.post("/api/projects/{slug}/cancel")
def cancel_project(slug: str):
    proj(slug)
    cancel(slug)
    return dict(ok=True)


@app.post("/api/projects/{slug}/continue")
def continue_project(slug: str):
    pr = proj(slug)
    ensure_idle(pr)
    pend = pr.meta().get("pending") or {}
    if pend.get("type") == "review":
        mark_reviewed(pr, pend["stage"])
    pr.update(pending=None)
    start_background(slug)
    return dict(ok=True)


class ApproveBody(BaseModel):
    stages: dict           # {stage: cost dict}
    run: bool = True


@app.post("/api/projects/{slug}/approve")
def approve(slug: str, b: ApproveBody):
    pr = proj(slug)
    costs.approve(pr, b.stages)
    if b.run and not is_running(slug):
        start_background(slug)
    return dict(ok=True)


@app.get("/api/projects/{slug}/estimate")
def project_estimate(slug: str):
    pr = proj(slug)
    return dict(estimate=costs.estimate_all(pr), balances=costs.balances(pr.meta()))


@app.put("/api/projects/{slug}/options")
def put_options(slug: str, body: dict):
    pr = proj(slug)

    def f(m):
        if "options" in body:
            m.setdefault("options", {}).update(body["options"])
        if "providers" in body:
            for st, pid in body["providers"].items():
                P.get(st, pid)
                m.setdefault("providers", {})[st] = pid
        if "title" in body:
            m["title"] = str(body["title"])[:120]
    return dict(meta=pr.update(f))


# ------------------------------------------------------------------ script editing
@app.put("/api/projects/{slug}/script")
def put_script(slug: str, body: dict):
    pr = proj(slug)
    ensure_idle(pr)
    old = pr.script() or {}
    data = dict(old)
    for k in ("title", "facts", "cast"):
        if k in body:
            data[k] = body[k]
    if "beats" in body:
        data["beats"] = body["beats"]
    norm = normalize_script(data, old.get("title", ""))
    for k in ("generated_by", "created"):
        if k in old:
            norm[k] = old[k]
    # keep fact check marks
    norm["facts"] = [dict(f, checked=bool(f.get("checked"))) for f in (data.get("facts") or []) if f.get("claim")]
    # keep scenes aligned when beats were reordered/inserted/deleted (client sends "origin" index per beat)
    origins = [b.get("origin") for b in body.get("beats") or []] if "beats" in body else None
    n_old = len(old.get("beats") or [])
    if origins is not None and origins != list(range(n_old)):
        scenes, previews = {}, {}
        for new_i, o in enumerate(origins):
            if isinstance(o, int) and os.path.exists(pr.scene_path(o)):
                scenes[new_i] = read_json(pr.scene_path(o))
                if os.path.exists(pr.preview_path(o)):
                    with open(pr.preview_path(o), "rb") as f:
                        previews[new_i] = f.read()
        sb = read_json(pr.p("storyboard.json"), {}) or {}
        old_info = sb.get("scenes") or {}
        for d_ in ("scenes", "previews"):
            if os.path.isdir(pr.p(d_)):
                for f in os.listdir(pr.p(d_)):
                    os.remove(pr.p(d_, f))
        new_info = {}
        for new_i, sc in scenes.items():
            pr.save_scene(new_i, sc)
            if new_i in previews:
                with open(pr.preview_path(new_i), "wb") as f:
                    f.write(previews[new_i])
            if str(origins[new_i]) in old_info:
                new_info[str(new_i)] = old_info[str(origins[new_i])]
        sb["scenes"] = new_info
        write_json(pr.p("storyboard.json"), sb)
    pr.save_script(norm)
    changed_text = [b["text"] for b in (old.get("beats") or [])] != [b["text"] for b in norm["beats"]] or \
                   [b["mood"] for b in (old.get("beats") or [])] != [b["mood"] for b in norm["beats"]]
    if changed_text:
        mark_stale(pr, "storyboard")
    return dict(script=norm, stale=changed_text)


class RegenBeat(BaseModel):
    instruction: str = ""
    approved: bool = False


def _paid_guard(pr, label, in_chars, out_tokens, approved):
    llm = stage_provider(pr.meta(), "llm")
    if llm.id == "offline":
        raise HTTPException(400, "Basic (no AI) mode can't rewrite beats; switch the writer to Claude in the project options")
    ok, why = llm.available()
    if not ok:
        raise HTTPException(400, f"{llm.label}: {why}")
    if llm.paid:
        c = llm.estimate_tokens(in_chars, out_tokens)
        if not approved:
            return JSONResponse(status_code=402, content=dict(needs_approval=True, label=label,
                                                              cost=c.to_dict(), provider=llm.label))
    return llm


@app.post("/api/projects/{slug}/beats/{i}/regenerate")
def regen_beat(slug: str, i: int, b: RegenBeat):
    pr = proj(slug)
    script = pr.script()
    if not script or not (0 <= i < len(script["beats"])):
        raise HTTPException(404, "no such beat")
    prompt = PR.regen_beat_prompt(script["beats"], i, b.instruction)
    llm = _paid_guard(pr, "rewrite one beat", len(prompt), 200, b.approved)
    if isinstance(llm, JSONResponse):
        return llm
    from ..pipeline.costs import record
    text, usage = llm.complete(PR.SCRIPT_SYSTEM, prompt, schema=PR.REGEN_BEAT_SCHEMA, label="beat")
    if usage.get("billed_usd"):
        record(pr, "script", llm.id, usd=usage["billed_usd"], note="rewrite one beat")
    data = P.extract_json(text)
    beat = dict(mood=data.get("mood") if data.get("mood") in ("fun", "tense", "somber") else script["beats"][i]["mood"],
                text=clean_line(data.get("text") or script["beats"][i]["text"]))
    return dict(beat=beat)


# ------------------------------------------------------------------ storyboard editing
@app.get("/api/projects/{slug}/scenes/{i}")
def get_scene(slug: str, i: int):
    pr = proj(slug)
    sc = read_json(pr.scene_path(i))
    if sc is None:
        raise HTTPException(404, "scene not made yet")
    return dict(scene=sc)


@app.put("/api/projects/{slug}/scenes/{i}")
def put_scene(slug: str, i: int, body: dict):
    pr = proj(slug)
    ensure_idle(pr)
    script = pr.script()
    if not script or not (0 <= i < len(script["beats"])):
        raise HTTPException(404, "no such beat")
    beat = script["beats"][i]
    scene = body.get("scene", body)
    fixed, fixes, errs = check_scene(scene, beat["mood"], beat["text"])
    if errs:
        return JSONResponse(status_code=422, content=dict(errors=errs, fixes=fixes))
    pr.save_scene(i, fixed)
    sb = read_json(pr.p("storyboard.json"), {}) or {}
    from ..pipeline.stages import h
    sb.setdefault("scenes", {})[str(i)] = dict(key=h(beat["text"], beat["mood"]), fixes=fixes, source="edited", at=time.time())
    write_json(pr.p("storyboard.json"), sb)
    warns = _preview(pr, i)
    if pr.meta().get("stages", {}).get("render", {}).get("status") == "done":
        mark_stale(pr, "render")
    return dict(scene=fixed, fixes=fixes, warnings=warns)


def _preview(pr, i):
    beats = pr.script()["beats"]
    durs = beat_durations(pr, beats)
    os.makedirs(pr.p("previews"), exist_ok=True)
    return render_still(scene_job(pr, i, beats, durs), pr.preview_path(i), 0.85, (640, 360), True)


@app.post("/api/projects/{slug}/scenes/{i}/preview")
def scene_preview(slug: str, i: int, t: float = 0.85):
    pr = proj(slug)
    beats = pr.script()["beats"]
    durs = beat_durations(pr, beats)
    out = pr.p("previews", f"{i:03d}_t.jpg")
    warns = render_still(scene_job(pr, i, beats, durs), out, max(0.0, min(t, 1.0)), (960, 540), True)
    return dict(path=f"previews/{i:03d}_t.jpg", warnings=warns, v=int(time.time()))


class RegenScene(BaseModel):
    instruction: str = ""
    approved: bool = False


@app.post("/api/projects/{slug}/scenes/{i}/regenerate")
def regen_scene(slug: str, i: int, b: RegenScene):
    pr = proj(slug)
    ensure_idle(pr)
    llm = stage_provider(pr.meta(), "llm")
    if llm.paid and not b.approved:
        c = llm.estimate_tokens(24500, 700)
        return JSONResponse(status_code=402, content=dict(needs_approval=True, label="redraw one scene",
                                                          cost=c.to_dict(), provider=llm.label))
    if llm.paid:
        cur = (pr.meta().get("approvals") or {}).get("storyboard") or {}
        c = llm.estimate_tokens(24500, 700).to_dict()
        costs.approve(pr, {"storyboard": dict(usd=max(cur.get("usd", 0), c["usd"]), credits=0, known=True)})
    start_background(slug, start="storyboard", stop_after="storyboard",
                     stage_kwargs={"storyboard": dict(only=[i], force=True, instruction=b.instruction)})
    return dict(ok=True)


@app.post("/api/projects/{slug}/scenes/{i}/rerender")
def rerender_scene(slug: str, i: int):
    pr = proj(slug)
    ensure_idle(pr)
    start_background(slug, start="render", stop_after="mix", stage_kwargs={"render": dict(only=[i])})
    return dict(ok=True)


@app.put("/api/projects/{slug}/facts")
def put_facts(slug: str, body: dict):
    pr = proj(slug)
    script = pr.script() or {}
    script["facts"] = body.get("facts") or []
    pr.save_script(script)
    return dict(facts=script["facts"])


@app.post("/api/projects/{slug}/music")
async def upload_music(slug: str, file: UploadFile = File(...)):
    pr = proj(slug)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"):
        raise HTTPException(400, "upload an mp3, wav, m4a, ogg, flac or aac file")
    os.makedirs(pr.p("music"), exist_ok=True)
    dest = pr.p("music", "upload" + ext)
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)

    def u(m):
        m.setdefault("options", {})["music_file"] = os.path.relpath(dest, pr.dir)
        m.setdefault("providers", {})["music"] = "upload"
    pr.update(u)
    if pr.meta().get("stages", {}).get("mix", {}).get("status") == "done":
        mark_stale(pr, "mix")
    return dict(ok=True, file=os.path.basename(dest))


@app.get("/api/projects/{slug}/file/{path:path}")
def project_file(slug: str, path: str):
    pr = proj(slug)
    full = os.path.realpath(os.path.join(pr.dir, path))
    if not full.startswith(os.path.realpath(pr.dir) + os.sep) or not os.path.isfile(full):
        raise HTTPException(404, "not found")
    if os.path.basename(full) in ("meta.json",) or full.endswith(".env"):
        raise HTTPException(403, "no")
    mt = mimetypes.guess_type(full)[0] or "application/octet-stream"
    return FileResponse(full, media_type=mt)


@app.get("/api/projects/{slug}/download/{kind}")
def download(slug: str, kind: str):
    pr = proj(slug)
    files = {"video": ("final/video.mp4", "video.mp4"), "share": ("final/video_share.mp4", "video_share.mp4"),
             "thumbnail": ("final/thumbnail.png", "thumbnail.png"), "description": ("final/description.txt", "description.txt")}
    if kind not in files:
        raise HTTPException(404, "unknown")
    rel, name = files[kind]
    full = pr.p(*rel.split("/"))
    if not os.path.exists(full):
        raise HTTPException(404, "not made yet")
    return FileResponse(full, filename=f"{slug}-{name}")


# ------------------------------------------------------------------ live events (SSE)
@app.get("/api/events")
async def events(request: Request, project: str | None = None):
    q, entry = bus.subscribe_async(project)

    async def gen():
        try:
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe_async(entry)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ frontend
if os.path.isdir(os.path.join(config.WEB_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(config.WEB_DIST, "assets")), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "not found")
    target = os.path.join(config.WEB_DIST, full_path)
    if full_path and os.path.isfile(target) and os.path.realpath(target).startswith(os.path.realpath(config.WEB_DIST)):
        return FileResponse(target)
    index = os.path.join(config.WEB_DIST, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return HTMLResponse("<h1>Stickman Studio</h1><p>The dashboard isn't built yet. Run <code>start.sh</code> / "
                        "<code>start.bat</code>, or <code>cd web && npm install && npm run build</code>.</p>"
                        "<p>The API is running: <a href='/api/docs'>/api/docs</a></p>")
