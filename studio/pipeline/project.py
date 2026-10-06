"""A project = one video. Everything lives in projects/<slug>/ so any stage can be resumed or redone:

    meta.json          settings, stage status, approvals, costs
    source/            YouTube metadata, transcript, frames, contact sheets, visual notes
    script.json        beats + fact list + cast
    scenes/NNN.json    one scene (JSON scene language) per beat
    previews/NNN.jpg   storyboard stills
    audio/             b_NNN.wav per beat + voice.json (durations, word timing)
    music/             music beds
    segments/          s_NNN.mp4 per scene + manifest.json
    final/             video.mp4, video_share.mp4, mix.wav, thumbnail.png, youtube.json, description.txt,
                       short.mp4 (+ short_ai.mp4 from Calliope), short.json
    shorts/            caption-less scenes for the Short
"""
import json
import os
import re
import shutil
import threading
import time
import unicodedata

from ..config import PROJECTS_DIR, ensure_dirs

STAGES = ["source", "script", "storyboard", "voice", "render", "mix", "package", "shorts"]
STAGE_LABELS = {"source": "Watch source video", "script": "Script", "storyboard": "Storyboard", "voice": "Voice",
                "render": "Render scenes", "mix": "Music & mix", "package": "YouTube package", "shorts": "Shorts teaser"}
CHECKPOINTS = ("script", "storyboard", "voice")

_locks = {}
_locks_guard = threading.Lock()


def _sync(meta):
    try:
        from .. import db
        db.sync(meta)
    except Exception:
        pass


def slugify(s, maxlen=48):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return (s[:maxlen].strip("-") or "video")


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


class Project:
    def __init__(self, slug):
        self.slug = slug
        self.dir = os.path.join(PROJECTS_DIR, slug)

    # ---------------- paths
    def p(self, *parts):
        return os.path.join(self.dir, *parts)

    @property
    def meta_path(self):
        return self.p("meta.json")

    def scene_path(self, i):
        return self.p("scenes", f"{i:03d}.json")

    def preview_path(self, i):
        return self.p("previews", f"{i:03d}.jpg")

    def audio_path(self, i):
        return self.p("audio", f"b_{i:03d}.wav")

    def segment_path(self, i):
        return self.p("segments", f"s_{i:03d}.mp4")

    @property
    def lock(self):
        with _locks_guard:
            return _locks.setdefault(self.slug, threading.RLock())

    # ---------------- meta
    def exists(self):
        return os.path.exists(self.meta_path)

    def meta(self):
        return read_json(self.meta_path, {}) or {}

    def update(self, fn=None, **fields):
        """Atomically read-modify-write meta.json."""
        with self.lock:
            m = self.meta()
            if fn:
                fn(m)
            m.update(fields)
            m["updated"] = time.time()
            write_json(self.meta_path, m)
        _sync(m)
        return m

    def set_stage(self, stage, **fields):
        def f(m):
            st = m.setdefault("stages", {}).setdefault(stage, {})
            st.update(fields)
        return self.update(f)

    def stage(self, stage):
        return self.meta().get("stages", {}).get(stage, {})

    # ---------------- artifacts
    def script(self):
        return read_json(self.p("script.json"))

    def save_script(self, script):
        write_json(self.p("script.json"), script)

    def scenes(self):
        sc = self.script() or {}
        return [read_json(self.scene_path(i)) for i in range(len(sc.get("beats", [])))]

    def save_scene(self, i, scene):
        write_json(self.scene_path(i), scene)

    def prop_kit(self):
        """Props the writer designed for this video (see engine/custom_props.py)."""
        return (read_json(self.p("props.json"), {}) or {}).get("props") or []

    def voice(self):
        return read_json(self.p("audio", "voice.json"), {}) or {}

    def render_info(self):
        return read_json(self.p("segments", "render.json"), {}) or {}

    def youtube(self):
        return read_json(self.p("final", "youtube.json"))

    def delete(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def new_project(title, mode, source_url="", topic="", options=None, providers=None):
    ensure_dirs()
    base = slugify(title or topic or source_url)
    slug = base
    k = 2
    while os.path.exists(os.path.join(PROJECTS_DIR, slug)):
        slug = f"{base}-{k}"
        k += 1
    pr = Project(slug)
    os.makedirs(pr.dir)
    now = time.time()
    meta = dict(slug=slug, title=title or topic or source_url, created=now, updated=now, mode=mode,
                source_url=source_url, topic=topic, options=options or {}, providers=providers or {},
                status="new", stages={s: {"status": "pending", "progress": 0.0, "message": ""} for s in STAGES},
                pending=None, approvals={}, costs=[], warnings=[], error=None)
    if mode != "youtube" and not (options or {}).get("style_url"):
        meta["stages"]["source"]["status"] = "skipped"
    write_json(pr.meta_path, meta)
    _sync(meta)
    return pr


def list_projects():
    ensure_dirs()
    out = []
    for name in os.listdir(PROJECTS_DIR):
        m = read_json(os.path.join(PROJECTS_DIR, name, "meta.json"))
        if m:
            out.append(m)
    out.sort(key=lambda m: -m.get("created", 0))
    return out
