"""Moving props, coats and riders, war-map pieces, transitions, highlighted captions, sound, fact-check, YouTube."""
import json

import numpy as np
import pytest
from PIL import ImageChops

from studio.engine.compiler import build_scene
from studio.engine.schema import check_scene, element_bbox
from studio.engine.registry import ANIMATED, PROPS
from studio.engine.render import pick_transition, compose_transition, TRANSITIONS
from studio.engine.captions import make_captions, paste_caption
from studio.engine import audio as A


def _scene(elements, bg=None, text="x", dur=4.0, mood="fun"):
    fixed, fixes, errs = check_scene({"bg": bg or {"type": "paper"}, "elements": elements,
                                      "camera": {"auto_shots": False, "zoom": [1.0, 1.0]}}, mood, text)
    assert not errs, errs
    return fixed, fixes, build_scene(fixed, 0, dur, mood, text)


def _differs(a, b):
    return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is not None


# ------------------------------------------------------------------ moving props
def test_animated_props_change_over_time():
    assert {"windmill", "flag", "fire", "smoke", "lighthouse", "helicopter"} <= set(ANIMATED)
    assert all(n in PROPS for n in ANIMATED)
    for name in ("windmill", "flag", "fire", "smoke", "helicopter"):
        _, _, sc = _scene([{"type": "prop", "name": name, "x": 960, "y": 860, "enter": "none"}])
        assert _differs(sc.render_at(1.0), sc.render_at(1.0 + ANIMATED[name] / 3)), name


def test_props_can_stand_still():
    _, _, sc = _scene([{"type": "prop", "name": "windmill", "x": 960, "y": 860, "enter": "none", "animate": False}])
    assert not _differs(sc.render_at(1.0), sc.render_at(1.7))


# ------------------------------------------------------------------ characters
def test_coats_and_riders():
    els = [{"type": "char", "kind": "bicorne", "x": 500, "y": 900, "coat": "#2B3F8C", "pose": "hand_in_coat"},
           {"type": "char", "kind": "shako", "x": 1300, "y": 900, "coat": "red", "ride": "horse",
            "do": [{"act": "run", "dx": 200, "at": 0.2}]},
           {"type": "crowd", "kind": "shako", "x": 960, "y": 930, "coat": "#C8302B", "ride": "Pony", "count": 3}]
    fixed, fixes, sc = _scene(els)
    assert fixed["elements"][2]["ride"] == "horse"                       # alias understood
    rider = element_bbox(fixed["elements"][1])
    walker = element_bbox(dict(fixed["elements"][1], ride=None))
    assert rider[1] < walker[1] and rider[2] - rider[0] > walker[2] - walker[0]   # taller and wider on a horse
    assert _differs(sc.render_at(0.5), sc.render_at(1.5))                  # the rider gallops
    bad, fixes2, _ = check_scene({"bg": {"type": "paper"}, "elements": [
        {"type": "char", "ride": "dinosaur", "coat": "notacolor", "x": 900, "y": 900}]})
    assert "ride" not in bad["elements"][0] and "coat" not in bad["elements"][0] and len(fixes2) == 2


# ------------------------------------------------------------------ war maps
def test_war_map_pieces():
    bg = {"type": "map", "style": "dark", "center": [30, 54], "width": 34}
    els = [{"type": "counter", "from": 1939, "to": 1945, "x": 960, "y": 110, "at": 0.05, "dur": 2.0},
           {"type": "counter", "from": 0, "to": 500000, "suffix": " men", "x": 500, "y": 700, "size": 60},
           {"type": "front", "keys": [{"at": 0.1, "points": [{"lon": 23, "lat": 58}, {"lon": 24, "lat": 50}]},
                                      {"at": 0.9, "points": [{"lon": 34, "lat": 58}, {"lon": 33, "lat": 51}]}]},
           {"type": "arrow", "points": [{"lon": 19, "lat": 53}, {"lon": 37, "lat": 55.6}], "units": "infantry"},
           {"type": "arrow", "from": [300, 800], "to": [900, 700], "units": "tank"},
           {"type": "battle", "lon": 35.8, "lat": 55.5, "label": "Borodino", "at": 0.5},
           {"type": "front", "points": [[0, 0]]},
           {"type": "counter", "from": "lots", "to": 3}]
    fixed, fixes, sc = _scene(els, bg, dur=6.0)
    types = [e["type"] for e in fixed["elements"]]
    assert types.count("front") == 1 and types.count("counter") == 2 and "battle" in types
    assert fixed["elements"][0]["color"] == "#EBEBF5"                    # light numbers on a dark map
    arrows = [e for e in fixed["elements"] if e["type"] == "arrow"]
    assert arrows[0]["units"] == "shako" or arrows[0]["units"] == "infantry"
    assert arrows[1]["units"] == "tank" and arrows[1]["count"] == 1
    assert any("front" in f for f in fixes) and any("counter" in f for f in fixes)
    assert ("boom" in [k for _, k in sc.sfx]) and ("tick1" in [k for _, k in sc.sfx])
    assert _differs(sc.render_at(1.0), sc.render_at(4.0))


def test_counter_formats():
    from studio.engine.warmap import fmt_count
    assert fmt_count(1812.4, "year") == "1812" and fmt_count(-44, "year") == "44 BC"
    assert fmt_count(1234567, prefix="$") == "$1,234,567"


# ------------------------------------------------------------------ transitions
def test_transitions_are_picked_and_drawn():
    paper, field = {"bg": {"type": "paper"}}, {"bg": {"type": "field"}}
    m = {"bg": {"type": "map", "center": [0, 0], "width": 40}}
    assert pick_transition(None, field, 0) == "cut"
    assert pick_transition(m, dict(m), 3) == "cut"
    assert pick_transition(paper, field, 3, "somber") == "fade"
    assert pick_transition(paper, dict(field, transition="iris"), 3) == "iris"
    assert pick_transition(paper, field, 3) in TRANSITIONS
    fixed, fixes, _ = check_scene({"bg": {"type": "paper"}, "elements": [], "transition": "dissolve"})
    assert fixed["transition"] == "fade"
    from PIL import Image
    a, b = Image.new("RGB", (1920, 1080), (255, 0, 0)), Image.new("RGB", (1920, 1080), (0, 0, 255))
    for k in ("slide", "wipe", "zoom", "iris", "paper", "fade"):
        mid = compose_transition(a, b, k, 0.5)
        assert mid.size == (1920, 1080)
        end = compose_transition(a, b, k, 1.0).convert("RGB").getpixel((960, 540))
        assert end[2] > 200, k                                           # ends on the new scene


# ------------------------------------------------------------------ captions
def test_highlight_captions_follow_the_words():
    text = "Napoleon crossed the Alps in the snow."
    plain = make_captions(text, 4.0)
    hi = make_captions(text, 4.0, style="highlight")
    assert len(plain) == 1 and len(hi) >= 6
    assert all(b[0] <= a[0] for a, b in zip(hi[1:], hi))                 # in order
    from PIL import Image
    fr = Image.new("RGB", (1920, 1080), (0, 0, 0))
    paste_caption(fr, hi, hi[2][0] + 0.01)
    assert fr.getbbox() is not None


# ------------------------------------------------------------------ sound
def test_new_sounds_and_ambience():
    for k in ("step", "step_soft", "jump", "thud", "cheer", "blip:300", "tick1"):
        s = A.sfx(k)
        assert len(s) > 100 and np.isfinite(s).all() and np.abs(s).max() > 0.05, k
    for k in set(A.AMBIENCE_FOR.values()) | {"storm", "fire"}:
        x = A.make_ambience(k, 6.0)
        assert np.isfinite(x).all() and np.abs(x).max() > 0.5, k
    assert A.ambience_kind({"bg": {"type": "harbor"}}) == "harbor"
    assert A.ambience_kind({"bg": {"type": "field", "time": "night"}}) == "night"
    assert A.ambience_kind({"bg": {"type": "field", "time": "storm"}}) == "storm"
    assert A.ambience_kind({"bg": {"type": "map"}}) is None


def test_scenes_emit_action_and_talk_sounds():
    els = [{"type": "char", "kind": "civ", "x": 500, "y": 900, "do": [{"act": "walk", "dx": 300, "at": 0.1},
                                                                       {"act": "jump", "at": 0.7}],
            "say": ["Hello there, everyone!"]},
           {"type": "crowd", "kind": "civ", "x": 1300, "y": 930, "count": 6, "do": [{"act": "cheer", "at": 0.5}]}]
    _, _, sc = _scene(els, {"type": "field"}, text="He walked over and said hello.", dur=5.0)
    kinds = [k for _, k in sc.sfx]
    assert "step" in kinds and "jump" in kinds and "cheer" in kinds
    assert sum(1 for k in kinds if k.startswith("blip:")) >= 4


def test_mix_with_ambience_and_switches(tmp_path):
    sr = A.SR
    voice = [np.zeros(sr * 2), np.zeros(sr * 2)]
    events = [(0.5, "step"), (0.6, "blip:300"), (2.5, "cheer")]
    out1 = tmp_path / "a.wav"
    A.build_mix(voice, [0, 2.2], [2.2, 2.2], ["fun", "fun"], events, 4.4, str(out1), ambiences=["harbor", None])
    out2 = tmp_path / "b.wav"
    A.build_mix(voice, [0, 2.2], [2.2, 2.2], ["fun", "fun"], events, 4.4, str(out2), ambiences=None,
                talk_blips=False, action_sounds=False)
    import soundfile as sf
    a, _ = sf.read(out1)
    b, _ = sf.read(out2)
    assert len(a) == len(b) and np.abs(a - b).max() > 1e-4


# ------------------------------------------------------------------ fact-check
def test_fact_check_fixes_wrong_beats(monkeypatch):
    from studio.pipeline import new_project, stages
    from studio.pipeline.runner import Ctx

    class FakeLLM:
        id, label, supports_web = "fake", "Fake", True
        seen = {}

        def complete(self, system, prompt, schema=None, images=(), label="", web=False, **kw):
            self.seen["web"] = web
            return json.dumps({"checks": [
                {"fact": 0, "beat": 0, "claim": "Waterloo was in 1816", "verdict": "wrong", "correction": "1815",
                 "source": "Britannica"},
                {"fact": 1, "beat": 1, "claim": "about 25,000 French casualties", "verdict": "unsure",
                 "correction": "estimates range 24,000-26,000", "source": "various"}],
                "rewrites": [{"beat": 0, "text": "In 1815, Napoleon meets his Waterloo — literally."},
                             {"beat": 7, "text": "out of range"}]}), {}

    pr = new_project("fc test", "topic", topic="Waterloo", options={"minutes": 1})
    script = {"title": "Waterloo", "beats": [{"mood": "fun", "text": "In 1816, Napoleon meets his Waterloo."},
                                             {"mood": "tense", "text": "The French lose about 25,000 men."}],
              "facts": [{"beat": 0, "claim": "Waterloo was in 1816", "confidence": "low"},
                        {"beat": 1, "claim": "25,000 French casualties", "confidence": "medium"}]}
    llm = FakeLLM()
    stages.fact_check(Ctx(pr, "script"), llm, script)
    assert llm.seen["web"] is True
    assert script["beats"][0]["text"].startswith("In 1815") and "—" not in script["beats"][0]["text"]
    assert script["factcheck"]["fixed"] == [0]
    assert script["factcheck"]["counts"] == {"correct": 0, "wrong": 1, "unsure": 1}
    assert script["facts"][0]["auto"] == "wrong" and script["facts"][1]["auto"] == "unsure"


# ------------------------------------------------------------------ YouTube
def test_youtube_resource_rules():
    from studio import youtube as YT
    r = YT.video_resource("<Title>" + "x" * 200, "desc <b>", ["a"] * 200, "public", "2030-01-01T10:00:00Z", False, False)
    assert len(r["snippet"]["title"]) <= 100 and "<" not in r["snippet"]["title"]
    assert "<" not in r["snippet"]["description"]
    assert r["status"]["privacyStatus"] == "private" and r["status"]["publishAt"] == "2030-01-01T10:00:00Z"
    assert len(",".join(r["snippet"]["tags"])) <= 450
    assert r["snippet"]["categoryId"] == "27"
    r2 = YT.video_resource("T", "D", privacy="unlisted")
    assert r2["status"]["privacyStatus"] == "unlisted" and "publishAt" not in r2["status"]


def test_youtube_needs_your_own_client(monkeypatch):
    from studio import youtube as YT
    monkeypatch.setattr(YT.config, "secret", lambda k: "")
    with pytest.raises(YT.YouTubeError):
        YT.auth_url(8765)
    monkeypatch.setattr(YT.config, "secret", lambda k: {"YOUTUBE_CLIENT_ID": "cid", "YOUTUBE_CLIENT_SECRET": "cs"}.get(k, ""))
    url = YT.auth_url(8765)
    assert url.startswith(YT.AUTH_URL) and "code_challenge_method=S256" in url and "youtube.upload" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2F" in url


def test_youtube_resumable_upload(monkeypatch, tmp_path):
    """The upload follows the resumable protocol: start a session, send chunks, resume after a 308, set the thumbnail."""
    from studio import youtube as YT
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * (YT.CHUNK + 1000))
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"png")
    monkeypatch.setattr(YT, "access_token", lambda: "tok")
    calls = []

    class R:
        def __init__(self, code, headers=None, body=None):
            self.status_code, self.headers, self._b = code, headers or {}, body or {}
            self.text = json.dumps(self._b)

        def json(self):
            return self._b

    def post(url, **kw):
        calls.append(("POST", url, kw.get("params")))
        if url == YT.UPLOAD_URL:
            assert kw["params"]["uploadType"] == "resumable" and kw["headers"]["X-Upload-Content-Length"]
            return R(200, {"location": "https://upload.example/session"})
        if url == YT.THUMB_URL:
            return R(200, body={})
        raise AssertionError(url)

    def put(url, content=b"", headers=None, **kw):
        calls.append(("PUT", headers["Content-Range"]))
        start = int(headers["Content-Range"].split()[1].split("-")[0])
        if start == 0:
            return R(308, {"range": f"bytes=0-{YT.CHUNK - 1}"})
        return R(200, body={"id": "abc123"})

    import httpx
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "put", put)
    vid = YT.upload(str(video), YT.video_resource("T", "D"), str(thumb))
    assert vid == "abc123"
    puts = [c for c in calls if c[0] == "PUT"]
    assert puts[0][1].startswith("bytes 0-") and puts[1][1].startswith(f"bytes {YT.CHUNK}-")
    assert any(c[0] == "POST" and c[1] == YT.THUMB_URL and c[2]["videoId"] == "abc123" for c in calls)
