"""Shorts helpers, the Claude Code MCP bridge (with a fake `claude`), and the per-video budget."""
import json
import os
import stat
import sys

import pytest

from studio import config
from studio.pipeline import shorts, costs, new_project
from studio.providers import mcp_bridge
from studio.providers.shorts import find, CalliopeShorts


def test_fix_range_keeps_short_between_limits():
    durs = [8.0] * 20
    p = shorts.fix_range({"start": 3, "end": 15}, durs)        # 13 beats = 104 s: too long
    assert sum(durs[p["start"]:p["end"] + 1]) <= shorts.MAX_S
    p = shorts.fix_range({"start": 5, "end": 5}, durs)         # 8 s: too short
    assert sum(durs[p["start"]:p["end"] + 1]) >= shorts.MIN_S
    p = shorts.fix_range({"start": 99, "end": -3}, durs)       # nonsense from the model
    assert 0 <= p["start"] <= p["end"] < len(durs)


def test_rule_pick_and_calliope_script_length():
    beats = [{"text": "word " * 20, "mood": "fun"} for _ in range(12)]
    p = shorts.rule_pick(beats, [9.0] * 12)
    assert p["start"] == 0 and 20 <= sum([9.0] * (p["end"] + 1)) <= 58
    s = shorts.calliope_script({"start": 0, "end": 0, "script": "Too short."}, beats)
    assert 280 <= len(s) <= 1120
    s = shorts.calliope_script({"start": 0, "end": 0, "script": "A long sentence here. " * 80}, beats)
    assert len(s) <= 1120 and s.endswith(".")


def test_caption_chunks_are_short_and_ordered():
    beats = [{"text": "Rome was not built in a day, and it did not fall in one either.", "mood": "fun"}] * 2
    info = {"starts": [0.0, 6.0], "durs": [6.0, 6.0]}
    chunks = shorts.caption_chunks(beats, info, {}, 0, 1)
    assert all(len(t.split()) <= 6 for _, _, t in chunks)
    assert all(a < b for a, b, _ in chunks)
    assert [a for a, _, _ in chunks] == sorted(a for a, _, _ in chunks)
    assert chunks[-1][1] <= 12.0 + 1e-6


STREAM = [
    {"type": "system", "subtype": "init", "tools": ["mcp__calliope__list_templates"]},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tu_1", "name": "mcp__calliope__list_templates",
                                                   "input": {"content_type": "short"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu_1",
                                              "content": [{"type": "text", "text": json.dumps(
                                                  {"templates": [{"id": "11111111-1111-4111-8111-111111111111",
                                                                  "name": "History short", "visibility": "community"}]})}]}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "DONE"}]}},
    {"type": "result", "subtype": "success", "result": "DONE"},
]


def test_parse_stream_reads_the_raw_tool_result():
    res, err, final, called = mcp_bridge.parse_stream([json.dumps(e) for e in STREAM], "mcp__calliope__list_templates")
    assert called and not err and final["result"] == "DONE"
    data = mcp_bridge.decode(res)
    assert data["templates"][0]["name"] == "History short"
    # another tool's result is ignored
    res, err, final, called = mcp_bridge.parse_stream([json.dumps(e) for e in STREAM], "mcp__calliope__get_job")
    assert not called and res is None


def _fake_claude(tmp_path, events):
    out = tmp_path / "events.jsonl"
    out.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    script = tmp_path / "claude"
    script.write_text(f"#!{sys.executable}\nimport sys\nsys.stdin.read()\nprint(open({str(out)!r}).read())\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


@pytest.mark.skipif(os.name == "nt", reason="uses a shebang script")
def test_calliope_test_connection_through_fake_claude(tmp_path):
    fake = _fake_claude(tmp_path, STREAM)
    config.save_settings({"claude_cli_path": fake, "calliope": {"connected": False, "templates": []}})
    try:
        temps = CalliopeShorts().test()
        assert temps[0]["id"].startswith("1111")
        assert config.load_settings()["calliope"]["connected"] is True
        assert CalliopeShorts().available()[0]
    finally:
        config.save_settings({"claude_cli_path": "", "calliope": {"connected": False, "templates": []}})


@pytest.mark.skipif(os.name == "nt", reason="uses a shebang script")
def test_bridge_reports_missing_connector(tmp_path):
    fake = _fake_claude(tmp_path, [{"type": "result", "subtype": "success", "result": "I don't have that tool."}])
    config.save_settings({"claude_cli_path": fake})
    try:
        with pytest.raises(Exception, match="claude mcp add"):
            mcp_bridge.call_tool("calliope", "list_templates", {})
    finally:
        config.save_settings({"claude_cli_path": ""})


def test_find_and_credit_parsing():
    raw = {"data": {"estimate": {"estimated_cost": 420, "image_model": "x"}}}
    assert find(raw, ("estimated_cost",)) == 420
    config.save_settings({"calliope": {"usd_per_1k_credits": 10.0}})
    try:
        c = CalliopeShorts().to_cost(raw, "AI Short")
        assert c.credits == 420 and c.usd == 4.2 and c.known
    finally:
        config.save_settings({"calliope": {"usd_per_1k_credits": 0.0}})
    c = CalliopeShorts().to_cost({"text": "no numbers"}, "AI Short")
    assert not c.known


def test_budget_pauses_and_approval_raises_it():
    pr = new_project("Budget test", "topic", topic="Budget", options={"minutes": 3},
                     providers={"llm": "anthropic", "voice": "kokoro", "music": "synth", "image": "local",
                                "transcript": "youtube_captions", "shorts": "none"})
    pr.update(budget_usd=0.05, costs=[dict(stage="script", provider="anthropic", usd=0.04)])
    est, lines = costs.stage_estimate(pr, "storyboard")
    assert est.usd > 0.01
    costs.approve(pr, {"storyboard": est.to_dict()})
    with pytest.raises(costs.NeedsApproval) as e:
        costs.check(pr, "storyboard")                       # approved, but over the per-video budget
    assert e.value.over_budget["budget"] == 0.05
    pr.update(pending=dict(type="approval", stage="storyboard", over_budget=e.value.over_budget))
    costs.approve(pr, {"storyboard": est.to_dict()})
    assert costs.budget(pr.meta()) >= 0.04 + est.usd
    costs.check(pr, "storyboard")                           # now fine


def test_calliope_line_in_draft_estimate_but_not_in_check():
    pr = new_project("Shorts est", "topic", topic="X", options={"minutes": 3},
                     providers={"llm": "offline", "voice": "kokoro", "music": "synth", "image": "local",
                                "transcript": "youtube_captions", "shorts": "calliope"})
    c, lines = costs.stage_estimate(pr, "shorts")
    assert lines and not lines[0][1].known                 # shown up front: "exact price comes from Calliope"
    assert costs.check(pr, "shorts").is_free               # but the step itself starts and asks with the real number
    pr.update(calliope_quote={"cost": {"usd": 0, "credits": 300, "credit_unit": "Calliope credits", "known": True}})
    with pytest.raises(costs.NeedsApproval):
        costs.check(pr, "shorts")


def test_free_short_skips_the_channel_host_and_its_text_matches(monkeypatch):
    """With no AI picking the moment, the Short starts after the host's greeting, stops before the sign-off, and the
    text kept for it is the narration of the beats actually used (not the greeting)."""
    from studio.pipeline import mascot as M
    from studio.pipeline.runner import Ctx
    pr = new_project("Short pick", "topic", topic="mills", options={"minutes": 1},
                     providers={"llm": "offline", "shorts": "stickman"})
    script = {"title": "Mills", "beats": [{"mood": "fun", "part": "hook" if i == 0 else "story",
                                           "text": f"Fact number {i} about the mill and its workers in town."} for i in range(8)]}
    M.add_host_beats(script, {})
    pr.save_script(script)
    from studio.pipeline.shorts import pick_clip
    ctx = Ctx(pr, "shorts")
    monkeypatch.setattr(type(pr), "render_info", lambda self: {"durs": [9.0] * len(script["beats"])})
    pick, durs = pick_clip(ctx)
    used = script["beats"][pick["start"]:pick["end"] + 1]
    assert used and not any(b.get("host") for b in used)
    assert "Sticky" not in pick["script"] and "like and subscribe" not in pick["script"]
    assert pick["script"].split()[:3] == used[0]["text"].split()[:3]
