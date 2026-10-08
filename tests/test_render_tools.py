"""Render-side tools: the opt-in hardware encoder (with its CPU fallback), the 'which scenes changed' check, the preview video."""
import json
import os
import shutil
import subprocess

import pytest

from studio.engine import encoders as EN

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is needed")


# ---------------------------------------------------------------- encoders
def test_the_cpu_encoder_arguments_are_exactly_what_every_video_was_made_with():
    assert EN.video_args(EN.CPU) == ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "1"]
    assert EN.video_args(EN.CPU, "fast", 18, 2) == ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "2"]
    assert EN.video_args("h264_nvenc")[:2] == ["-c:v", "h264_nvenc"]
    assert EN.key_part(EN.CPU) is None and EN.key_part("h264_nvenc") == "h264_nvenc"


def test_settings_resolve_to_an_encoder_that_works_or_the_cpu(monkeypatch):
    monkeypatch.setattr(EN, "detect", lambda refresh=False: ["h264_nvenc", "h264_qsv"])
    assert EN.resolve("cpu") == EN.CPU and EN.resolve("") == EN.CPU and EN.resolve(None) == EN.CPU
    assert EN.resolve("auto") == "h264_nvenc" and EN.resolve("h264_qsv") == "h264_qsv"
    assert EN.resolve("h264_amf") == EN.CPU and EN.resolve("nonsense") == EN.CPU           # not available here: never an error
    monkeypatch.setattr(EN, "detect", lambda refresh=False: [])
    assert EN.resolve("auto") == EN.CPU


def test_detection_only_reports_encoders_that_pass_a_real_test_encode(monkeypatch):
    class R:
        def __init__(self, code=0, out=""):
            self.returncode, self.stdout = code, out
    calls = []

    def fake(cmd, timeout=20):
        calls.append(cmd)
        if "-encoders" in cmd:
            return R(0, " V....D h264_nvenc NVIDIA\n V....D h264_qsv Intel\n V....D libx264 x264\n")
        return R(0 if "h264_qsv" in cmd else 1)                                      # the card says no to NVENC, yes to Quick Sync
    monkeypatch.setattr(EN, "_run", fake)
    EN._found.clear()
    assert EN.listed() == ["h264_nvenc", "h264_qsv"] and EN.detect(refresh=True) == ["h264_qsv"]
    monkeypatch.setattr(EN, "_run", lambda cmd, timeout=20: (_ for _ in ()).throw(OSError("no ffmpeg")))
    assert EN.listed() == [] and EN.works("h264_nvenc") is False
    EN._found.clear()


def test_the_real_detection_runs_here_without_error():
    EN._found.clear()
    got = EN.detect(refresh=True)
    assert isinstance(got, list) and set(got) <= set(EN.HARDWARE)
    EN._found.clear()


def _job(tmp_path, encoder=None):
    scene = {"bg": {"type": "paper"}, "elements": [{"type": "text", "text": "HELLO", "x": 960, "y": 400, "size": 120, "color": "navy"}]}
    j = dict(idx=0, scene=scene, dur=0.5, mood="fun", text="Hello there.", word_times=None, frames=6, out=str(tmp_path / "s.mp4"),
             captions=False, watermark="", caption_style="highlight", transition="cut", prev=None)
    if encoder:
        j["encoder"] = encoder
    return j


def test_a_failing_hardware_encoder_falls_back_to_the_cpu_for_that_scene(tmp_path):
    from studio.engine.render import render_segment
    if "h264_nvenc" in EN.detect():
        pytest.skip("this PC really has NVENC")
    res = render_segment(_job(tmp_path, "h264_nvenc"))                             # ffmpeg rejects it (no card) -> CPU
    assert os.path.getsize(tmp_path / "s.mp4") > 1000
    assert any("encoded on the CPU instead" in w for w in res["warnings"])
    res2 = render_segment(_job(tmp_path))
    assert not any("CPU instead" in w for w in res2["warnings"])
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt,width,height",
                        "-of", "json", str(tmp_path / "s.mp4")], capture_output=True, text=True)
    st = json.loads(p.stdout)["streams"][0]
    assert (st["codec_name"], st["pix_fmt"], st["width"], st["height"]) == ("h264", "yuv420p", 1920, 1080)


# ---------------------------------------------------------------- which scenes changed
def _project(tmp_path_factory=None):
    from studio.pipeline import new_project
    pr = new_project("Render tools", "topic", topic="Rome", options={"minutes": 1, "mascot": False})
    beats = [dict(mood="fun", text="Rome was founded by two brothers."), dict(mood="fun", text="One of them did not survive the argument.")]
    pr.save_script({"title": "Rome", "topic": "Rome", "cast": [], "beats": beats})
    os.makedirs(pr.p("scenes"), exist_ok=True)
    for i, t in enumerate(("ROME", "TWO BROTHERS")):
        sc = {"bg": {"type": "paper"}, "elements": [{"type": "text", "text": t, "x": 960, "y": 400, "size": 120, "color": "navy"}]}
        with open(pr.scene_path(i), "w") as f:
            json.dump(sc, f)
    os.makedirs(pr.p("audio"), exist_ok=True)
    import numpy as np
    import soundfile as sf
    for i in range(2):
        sf.write(pr.audio_path(i), np.zeros(24000, dtype="float32"), 24000)
    with open(pr.p("audio", "voice.json"), "w") as f:
        json.dump({"provider": "x", "voice": "v", "beats": [dict(text=b["text"], spoken=b["text"], dur=1.0, sr=24000) for b in beats]}, f)
    return pr


def test_render_status_matches_what_the_render_stage_would_do():
    from studio.engine.render import plan_timeline
    from studio.pipeline import stages
    pr = _project()
    st = stages.render_status(pr)
    assert st["ready"] and st["stale"] == [0, 1] and st["rendered"] == 0                   # nothing rendered yet
    # pretend both segments were rendered with exactly the keys the render stage makes
    beats = pr.script()["beats"]
    vb = pr.voice()["beats"]
    frames, starts, durs = plan_timeline([e["dur"] for e in vb])
    settings = stages.load_settings()
    scenes = [stages.as_rendered(json.load(open(pr.scene_path(i))), i, beats, settings, {}, {"mascot": False}) for i in range(2)]
    os.makedirs(pr.p("segments"), exist_ok=True)
    man = {}
    for i in range(2):
        man[str(i)] = stages.render_key(i, beats, scenes, frames, durs, vb, "", settings.get("caption_style", "highlight"),
                                        settings.get("transitions", True) is not False, EN.CPU)[0]
        open(pr.segment_path(i), "wb").write(b"x")
    json.dump(man, open(pr.p("segments", "manifest.json"), "w"))
    assert stages.render_status(pr)["stale"] == []
    # change the words of scene 1: only scene 1 (and the one after it, none here) is stale
    sc = json.load(open(pr.scene_path(1)))
    sc["elements"][0]["text"] = "ONE BROTHER"
    json.dump(sc, open(pr.scene_path(1), "w"))
    st = stages.render_status(pr)
    assert st["stale"] == [1] and st["rendered"] == 1
    # a missing voice is "not ready", not an error
    os.remove(pr.p("audio", "voice.json"))
    assert stages.render_status(pr)["ready"] is False


def test_switching_to_a_graphics_encoder_re_renders_and_the_cpu_key_is_unchanged():
    from studio.pipeline import stages
    pr = _project()
    beats = pr.script()["beats"]
    vb = pr.voice()["beats"]
    scenes = [json.load(open(pr.scene_path(i))) for i in range(2)]
    args = (0, beats, scenes, [30, 30], [1.0, 1.0], vb, "", "highlight", True)
    cpu = stages.render_key(*args, EN.CPU)[0]
    assert cpu == stages.render_key(*args, EN.CPU)[0] and cpu != stages.render_key(*args, "h264_nvenc")[0]


# ---------------------------------------------------------------- the preview video
def test_the_preview_video_is_made_from_the_pictures_and_the_voice(tmp_path):
    from PIL import Image
    from studio.pipeline import animatic
    pr = _project()
    os.makedirs(pr.p("previews"), exist_ok=True)
    Image.new("RGB", (640, 360), (200, 220, 240)).save(pr.preview_path(0))               # scene 1 has no picture yet
    r = animatic.build(pr)
    assert os.path.getsize(r["path"]) > 2000 and r["scenes"] == 2 and r["missing_pictures"] == [1]
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", r["path"]],
                       capture_output=True, text=True)
    info = json.loads(p.stdout)
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"} and abs(float(info["format"]["duration"]) - r["seconds"]) < 0.6
    assert not os.path.exists(pr.p("final", "_animatic"))                                 # the temporary pictures are gone
    os.remove(pr.p("audio", "voice.json"))
    with pytest.raises(ValueError):
        animatic.build(pr)
