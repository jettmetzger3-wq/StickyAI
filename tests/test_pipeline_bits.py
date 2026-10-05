import pytest

from studio.pipeline.stages import build_chapters, fmt_ts, normalize_script, clean_line
from studio.pipeline import new_project, costs
from studio.pipeline.rules import rule_scene, offline_script, split_beats
from studio.providers.transcript import parse_vtt, parse_json3, video_id
from studio.providers.llm import extract_json
from studio.engine import check_scene


# ------------------------------------------------------------------ chapters
def test_fmt_ts():
    assert fmt_ts(0) == "0:00"
    assert fmt_ts(65.4) == "1:05"
    assert fmt_ts(3725) == "1:02:05"


def test_chapters_first_at_zero_and_spaced():
    starts = [0, 4, 9, 15, 22, 30, 41, 55, 70, 90]
    ch = build_chapters([{"beat": 1, "title": "Intro"}, {"beat": 2, "title": "Too close"},
                         {"beat": 4, "title": "Middle"}, {"beat": 8, "title": "End"}], starts, 100)
    assert ch[0][0] == 0.0 and ch[0][1] == "Intro"
    times = [t for t, _ in ch]
    assert all(b - a >= 10 for a, b in zip(times, times[1:]))
    assert len(ch) >= 3


def test_chapters_padded_to_three():
    starts = [i * 10.0 for i in range(12)]
    ch = build_chapters([{"beat": 0, "title": "Only one"}], starts, 120, beat_texts=[f"Beat number {i} text" for i in range(12)])
    assert len(ch) >= 3 and ch[0] == (0.0, "Only one")


# ------------------------------------------------------------------ script cleanup
def test_normalize_script_removes_dashes_and_bad_moods():
    s = normalize_script({"title": "T", "beats": [{"mood": "happy", "text": "Rome fell — slowly."}, {"text": " "}],
                          "facts": [{"beat": 0, "claim": "476", "confidence": "sure"}],
                          "cast": [{"name": "Rome", "kind": "romans"}]})
    assert s["beats"] == [{"mood": "fun", "text": "Rome fell, slowly."}]
    assert s["facts"][0]["confidence"] == "medium"
    assert s["cast"][0]["kind"] == "roman"
    assert clean_line("a – b") == "a, b"


def test_rule_scenes_are_valid():
    cast = [{"name": "Japan", "kind": "japan"}, {"name": "America", "kind": "america"}]
    for i, (mood, text) in enumerate([("fun", "In 1853 America sends ships to Japan."),
                                      ("somber", "Many civilians were killed."),
                                      ("tense", "The oil runs out.")]):
        sc = rule_scene({"mood": mood, "text": text}, i, cast)
        fixed, fixes, errs = check_scene(sc, mood, text)
        assert errs == [] and fixed["elements"]


def test_offline_script_and_split():
    s = offline_script("The Fall of Rome", 1)
    assert s["beats"] and s["title"] == "The Fall of Rome"
    beats = split_beats("One two three. " * 30)
    assert all(len(b.split()) <= 30 for b in beats)


# ------------------------------------------------------------------ transcripts
def test_video_id():
    for u in ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ?t=3",
              "https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"):
        assert video_id(u) == "dQw4w9WgXcQ"
    assert video_id("https://example.com") is None


def test_parse_vtt_dedupes_rolling_auto_captions():
    vtt = """WEBVTT

00:00:00.000 --> 00:00:02.000
In 1941 Japan

00:00:02.000 --> 00:00:04.000
In 1941 Japan
makes a bold move

00:00:04.000 --> 00:00:06.500 align:start
<c>makes a bold move</c>
"""
    segs = parse_vtt(vtt)
    text = " ".join(s["text"] for s in segs)
    assert text.count("1941") == 1 and text.count("bold move") == 1
    assert segs[0]["start"] == 0.0


def test_parse_json3():
    data = {"events": [{"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
                       {"tStartMs": 3000}]}
    assert parse_json3(data) == [{"start": 1.0, "end": 3.0, "text": "Hello world"}]


def test_extract_json():
    assert extract_json('Sure! ```json\n{"a": 1}\n``` done') == {"a": 1}
    assert extract_json('{"a": [1, 2,],}') == {"a": [1, 2]}
    assert extract_json('prefix {"a": {"b": "}"}} suffix') == {"a": {"b": "}"}}


# ------------------------------------------------------------------ costs & approvals
def test_free_project_needs_no_approval():
    pr = new_project("free test", "topic", topic="Rome", options={"minutes": 1},
                     providers={"llm": "claude_cli", "voice": "kokoro", "music": "synth", "image": "local",
                                "transcript": "youtube_captions"})
    for st in ("script", "storyboard", "voice", "mix", "package"):
        assert costs.check(pr, st).is_free


def test_paid_stage_requires_approval_and_respects_margin():
    pr = new_project("paid test", "topic", topic="Rome", options={"minutes": 2},
                     providers={"llm": "anthropic", "voice": "kokoro", "music": "synth", "image": "local",
                                "transcript": "youtube_captions"})
    with pytest.raises(costs.NeedsApproval) as e:
        costs.check(pr, "script")
    est = e.value.cost
    assert est.usd > 0
    costs.approve(pr, {"script": est.to_dict()})
    costs.check(pr, "script")  # now fine
    # an approval for a much smaller amount is not enough
    costs.approve(pr, {"storyboard": {"usd": 0.001, "credits": 0, "known": True}})
    with pytest.raises(costs.NeedsApproval):
        costs.check(pr, "storyboard")


def test_elevenlabs_voice_estimate_uses_half_credit_per_char():
    from studio.providers import get
    c = get("voice", "elevenlabs").estimate(chars=1000)
    assert c.credits == 500 and c.credit_unit
