"""Places where things happen, faces that react to the words, the smarter camera, the channel mascot, and
choosing which AI does each job (with the Claude plan savers)."""
import json

import numpy as np
import pytest

from studio.engine.compiler import build_scene
from studio.engine.schema import check_scene, activity_place, build_what_from_text, BG_TYPES
from studio.engine.timing import WordTimer
from studio.engine import reactions as RX
from studio.engine.puppet import Puppet

PLACES = ("construction", "factory", "farm", "mine", "classroom", "lab", "parliament", "courtroom", "prison",
          "market", "camp", "battlefield")


# ------------------------------------------------------------------ places
@pytest.mark.parametrize("text, want", [
    ("In 1820 he built a factory in Manchester.", {"type": "construction", "what": "factory"}),
    ("Then he built a navy to rival Britain.", {"type": "construction", "what": "ship"}),
    ("They built the Great Wall.", {"type": "construction", "what": "wall"}),
    ("He opened a factory.", {"type": "factory"}),
    ("Workers on the assembly line made a car a minute.", {"type": "factory", "style": "inside"}),
    ("They were thrown in jail for ten years.", {"type": "prison"}),
    ("The trial lasted three weeks.", {"type": "courtroom"}),
    ("Parliament debated the bill all night.", {"type": "parliament"}),
    ("Miners dug for coal.", {"type": "mine"}),
    ("Peasants worked the farms.", {"type": "farm"}),
    ("The Battle of Austerlitz was his masterpiece.", {"type": "battlefield"}),
    ("He set up camp by the river.", {"type": "camp"}),
])
def test_narration_names_the_place(text, want):
    assert activity_place(text) == want


@pytest.mark.parametrize("text", ["He built a reputation as a ship captain.", "He built an empire.",
                                  "He was charged with treason.", "He had a heart attack.", "The talks stalled.",
                                  "Land mines killed thousands.", "The stock market crashed.",
                                  "This land is mine, he said.", "Prisoners were sent to concentration camps.",
                                  "She fought for the vote.", "Napoleon was born in 1769."])
def test_no_place_for_figures_of_speech_or_sensitive_ones(text):
    assert activity_place(text) is None


def test_plain_scene_becomes_the_construction_site_and_loses_the_tiny_factory():
    sc = {"bg": {"type": "paper"}, "elements": [{"type": "char", "kind": "tophat", "x": 500, "y": 900},
                                                {"type": "prop", "name": "factory", "x": 1300, "y": 800}]}
    fixed, fixes, errs = check_scene(sc, "fun", "In 1820 he built a factory in Manchester.")
    assert not errs
    assert fixed["bg"] == {"type": "construction", "what": "factory"}
    assert [e["type"] for e in fixed["elements"]] == ["char"]


def test_diagrams_and_deliberate_places_are_left_alone():
    chart = {"bg": {"type": "paper"}, "elements": [{"type": "chart", "data": [{"label": "a", "value": 1}]}]}
    assert check_scene(chart, "fun", "He built a factory.")[0]["bg"]["type"] == "paper"
    harbor = {"bg": {"type": "harbor"}, "elements": []}
    assert check_scene(harbor, "fun", "The battle began.")[0]["bg"]["type"] == "harbor"


def test_bg_aliases_and_options():
    f = check_scene({"bg": {"type": "shipyard"}, "elements": []}, "fun", "x")[0]
    assert f["bg"] == {"type": "construction", "what": "ship"}
    f = check_scene({"bg": {"type": "assembly_line"}, "elements": []}, "fun", "x")[0]
    assert f["bg"] == {"type": "factory", "style": "inside"}
    f = check_scene({"bg": {"type": "battlefield", "style": "WW1"}, "elements": []}, "tense", "x")[0]
    assert f["bg"]["style"] == "ruins"
    f = check_scene({"bg": {"type": "construction", "progress": [0.2, 2]}, "elements": []}, "fun",
                    "They built a castle.")[0]
    assert f["bg"] == {"type": "construction", "what": "castle", "progress": [0.2, 1.0]}
    assert build_what_from_text("He built a huge new skyscraper.") == "tower"


def test_no_weather_inside():
    f = check_scene({"bg": {"type": "prison"}, "weather": "rain", "elements": []}, "somber", "x")[0]
    assert "weather" not in f
    f = check_scene({"bg": {"type": "factory", "style": "inside"}, "weather": "snow", "elements": []}, "fun", "x")[0]
    assert "weather" not in f


@pytest.mark.parametrize("bg", [dict(type=t) for t in PLACES] + [
    dict(type="construction", what=w) for w in ("house", "tower", "castle", "wall", "ship")] + [
    dict(type="battlefield", style="open"), dict(type="battlefield", style="ruins", time="night"),
    dict(type="factory", style="inside"), dict(type="market", style="arab"), dict(type="camp", time="night")])
def test_every_place_paints_and_animates(bg):
    sc = build_scene({"bg": bg, "elements": [{"type": "char", "kind": "civ", "x": 400, "y": 920}]}, 0, 4.0, "fun",
                     "Something happened here.")
    assert not sc.warnings
    a, b = np.asarray(sc.render_at(0.5)), np.asarray(sc.render_at(2.6))
    assert a.shape == (1080, 1920, 3) and a.std() > 20
    if bg["type"] in ("construction", "factory", "battlefield", "camp", "lab"):
        assert np.abs(a.astype(int) - b.astype(int)).mean() > 0.05, "its moving parts should move"


def test_walls_rise_during_the_scene():
    from studio.engine.places_work import RisingWalls, Building
    w = RisingWalls(Building("factory", 770), (0.2, 0.9), 8.0)
    opaque = [int((np.asarray(w.frame(t).getchannel("A")) > 0).sum()) for t in (0.0, 4.0, 8.0)]
    assert opaque[0] < opaque[1] < opaque[2]
    assert w.top_y(8.0) < w.top_y(0.0)


def test_the_same_building_keeps_rising_across_scenes():
    from studio.pipeline.themes import vary
    sc = {i: {"bg": {"type": "construction", "what": "factory"}} for i in range(3)}
    vary(sc, [0, 1, 2], {0, 1, 2})
    assert sc[1]["bg"]["progress"] == [0.85, 1.0] and sc[2]["bg"]["progress"] == "done"


def test_place_ambience():
    from studio.engine.audio import ambience_kind, make_ambience
    assert ambience_kind({"bg": {"type": "construction"}}) == "construction"
    assert ambience_kind({"bg": {"type": "factory"}}) == "city"
    assert ambience_kind({"bg": {"type": "factory", "style": "inside"}}) == "factory"
    assert ambience_kind({"bg": {"type": "mine"}}) == "cave"
    for k in ("construction", "factory", "cave"):
        assert np.abs(make_ambience(k, 4.0)).max() > 0.5


def test_workers_hold_their_tools():
    from studio.engine.pen import Pen
    for tool in ("hammer", "pickaxe", "shovel"):
        p = Pen(1, rgba=True, size=(400, 500))
        p.stick(200, 460, 1.0, "hardhat", prop=tool, arms=((20, 15), (150, 40)), shadow=False)
        assert p.im.getbbox()
    pz = Puppet(500, 900, 1.0, dict(kind="hardhat"), actions=[dict(act="hammer", t0=0.0, dur=2.0)])
    up, down = pz.state(0.1)[0], pz.state(0.4)[0]
    assert up["prop"] == "hammer" and up["arms"][1] != down["arms"][1]


# ------------------------------------------------------------------ faces that react to the words
def plan(text, els, mood="fun"):
    return RX.plan({"elements": els}, WordTimer(text, 8.0), mood)


NAP = {"type": "char", "kind": "bicorne", "who": "Napoleon", "x": 400, "y": 900}
FRA = {"type": "char", "kind": "germany", "who": "Francis", "x": 1400, "y": 900}


def test_the_named_character_reacts_on_the_word():
    p = plan("Napoleon won at Austerlitz, and Francis was furious.", [NAP, FRA])
    assert [e for _, e in p[0]] == ["smug"] and [e for _, e in p[1]] == ["angry"]
    t = WordTimer("Napoleon won at Austerlitz, and Francis was furious.", 8.0)
    assert abs(p[1][0][0] - (t.starts[t.find("furious")] - 0.05)) < 1e-6


def test_everyone_gasps_but_negations_dont_count():
    p = plan("Out of the blue, suddenly the bridge collapsed.", [NAP, FRA])
    assert set(p) == {0, 1} and p[0][0][1] == "surprise"
    assert plan("He never lost a battle.", [NAP]) == {}


def test_somber_scenes_only_get_sad_faces():
    assert plan("It was a brilliant plan, but everyone died.", [NAP], "somber") == {0: [(pytest.approx(
        WordTimer("It was a brilliant plan, but everyone died.", 8.0).starts[7] - 0.05), "sad")]}


def test_own_actions_win_over_reactions():
    acts = [dict(act="laugh", t0=2.0, dur=1.6)]
    out = RX.merge(acts, [(2.5, "angry"), (5.0, "sad")], appear_s=0.0, dur=8.0)
    assert [(a["act"], a.get("expr")) for a in out] == [("laugh", None), ("react", "sad")]


def test_react_changes_the_face():
    pz = Puppet(500, 900, 1.0, dict(kind="civ"), actions=[dict(act="react", t0=1.0, dur=1.5, expr="angry")])
    before, during = pz.state(0.5)[0], pz.state(1.2)[0]
    assert during["eyes"] == "angry" and "vein" in during["extra"] and before.get("eyes") != "angry"


def test_react_can_be_switched_off():
    assert RX.plan({"react": False, "elements": [NAP]}, WordTimer("Suddenly he won.", 6.0)) == {}
    assert RX.plan({"elements": [dict(NAP, react=False)]}, WordTimer("Then he won.", 6.0)) == {}


# ------------------------------------------------------------------ smarter camera
def test_close_up_cuts_in_on_the_punchline_word_and_back():
    text = "Napoleon marched his army across the river. Everyone expected a siege, but Francis was furious."
    sc = build_scene({"bg": {"type": "battlefield"}, "elements": [NAP, FRA]}, 0, 9.0, "fun", text)
    t = sc.timer.starts[sc.timer.find("furious")]
    assert sc.shots and abs(sc.shots[0]["t"] - t) < 0.2 and sc.shots[0]["z"] > 1.4
    assert abs(sc.shots[0]["cx"] - 1400) < 1


def test_wide_places_pan_slowly():
    sc = build_scene({"bg": {"type": "market"}, "elements": [dict(NAP, x=960)], "camera": {"zoom": [1.0, 1.04]}},
                     0, 6.0, "fun", "The market was busy.")
    assert sc.cam["z0"] > 1.05 and sc.cam["cx0"] != sc.cam["cx1"]
    still = build_scene({"bg": {"type": "paper"}, "elements": [NAP]}, 0, 6.0, "fun", "The market was busy.")
    assert still.cam["cx0"] == still.cam["cx1"]


def test_after_a_close_up_the_pan_carries_on():
    sc = build_scene({"bg": {"type": "market"}, "elements": [dict(NAP, x=960)]}, 0, 6.0, "fun", "x y z")
    sc.shot(1.0, 1.6, (960, 600), "cut")
    sc.shot(2.0, 1.0, None, "cut", base=True)
    assert sc.cam_at(3.0) == pytest.approx(sc.cam_at(3.0)) and sc.cam_at(3.0)[0] == pytest.approx(
        sc._base_cam(3.0)[0])


# ------------------------------------------------------------------ the channel mascot
def script():
    return {"title": "The Napoleonic Wars", "beats": [
        {"mood": "fun", "text": "In 1796 a short general took over a starving army."},
        {"mood": "fun", "text": "Napoleon marched into Italy."},
        {"mood": "tense", "text": "Suddenly, the Austrians attacked from the north."},
        {"mood": "fun", "text": "He won anyway."}]}


def test_host_beats_go_after_the_hook_and_at_the_end():
    from studio.pipeline import mascot as M
    s = M.add_host_beats(script(), {})
    hosts = [(i, b["host"]) for i, b in enumerate(s["beats"]) if b.get("host")]
    assert hosts == [(1, "intro"), (5, "outro")]
    assert "Sticky" in s["beats"][1]["text"] and "The Napoleonic Wars" in s["beats"][1]["text"]
    again = M.add_host_beats(s, {"mascot": {"name": "Dot", "outro": False}})
    assert [b.get("host") for b in again["beats"]].count("intro") == 1 and "Dot" in again["beats"][1]["text"]
    assert not any(b.get("host") == "outro" for b in again["beats"])
    off = M.add_host_beats(s, {"mascot": {"on": False}})
    # no mascot: no greeting, but the video still ends with the like-and-subscribe card (no character)
    assert [b.get("host") for b in off["beats"] if b.get("host")] == ["end"] and off["beats"][-1]["host"] == "end"
    assert "like" in off["beats"][-1]["text"].lower() and "subscribe" in off["beats"][-1]["text"].lower()
    plain = M.add_host_beats(script(), {}, mascot=False)
    assert [b.get("host") for b in plain["beats"] if b.get("host")] == ["end"]


def test_host_scenes_are_valid_and_talk_without_blips():
    from studio.pipeline import mascot as M
    s = M.add_host_beats(script(), {})
    for b in (s["beats"][1], s["beats"][-1]):
        sc = M.host_scene(b, {}, s["title"])
        fixed, fixes, errs = check_scene(sc, b["mood"], b["text"])
        assert not errs
        built = build_scene(fixed, 1, 5.0, b["mood"], b["text"])
        assert not built.warnings
        assert not any(str(name).startswith("blip") for _, name in built.sfx)


def test_cameos_pop_in_on_big_moments_only_now_and_then():
    from studio.pipeline import mascot as M
    beats = [{"mood": "fun", "text": "Quiet beat."}] * 2 + [{"mood": "fun", "text": "Suddenly it exploded."}] + \
            [{"mood": "fun", "text": "He laughed."}] * 3 + [{"mood": "fun", "text": "Then everyone was shocked."}] * 6
    plan_ = M.cameo_plan(beats, {})
    assert 2 in plan_ and plan_[2] == ("Suddenly", "surprise")
    assert all(abs(a - b) >= M.CAMEO_EVERY for a in plan_ for b in plan_ if a != b)
    scene = {"bg": {"type": "paper"}, "elements": []}
    out = M.with_cameo(scene, 2, beats, {}, plan_)
    host = out["elements"][0]
    assert host["peek"] and host["x"] + 40 > 1920 - 60 and out["elements"][1]["type"] == "bubble"
    assert M.with_cameo(scene, 3, beats, {}, plan_) is scene
    assert M.cameo_plan(beats, {"mascot": {"cameos": False}}) == {}
    built = build_scene(out, 2, 5.0, "fun", "Suddenly it exploded.")
    assert not built.warnings
    peek = [L for L in built.layers if L.get("puppet") and L["puppet"].x > 1803]
    assert peek, "the host stands half outside the right edge and leans in"


def test_host_beats_survive_script_edits_and_stay_out_of_shorts():
    from studio.pipeline.stages import normalize_script
    from studio.pipeline.shorts import fix_range
    s = normalize_script({"beats": [{"mood": "fun", "text": "Hi!", "host": "intro"}, {"mood": "fun", "text": "x"}]})
    assert s["beats"][0]["host"] == "intro"
    beats = [{"text": "a"}, {"text": "b", "host": "intro"}] + [{"text": "c"}] * 10 + [{"text": "d", "host": "outro"}]
    pick = fix_range({"start": 0, "end": 5}, [8.0] * 13, beats)
    assert not any(beats[i].get("host") for i in range(pick["start"], pick["end"] + 1))


def test_storyboard_draws_host_scenes_without_the_ai(monkeypatch):
    from studio.pipeline import new_project, stages
    from studio.pipeline.runner import Ctx
    asked, prompts = [], []

    class Writer:
        id, label, short, paid, supports_images = "groq", "W", "W", False, False
        batch_beats, parallel, examples, compact = 8, 1, 3, True

        def available(self):
            return True, ""

        def complete(self, system, prompt, schema=None, images=(), label="", **kw):
            asked.append(label)
            prompts.append(prompt) if label.startswith("storyboard") else None
            if label == "props":
                return '{"props": []}', {}
            idx = [int(x) for x in label.split()[1].split("-")]
            return json.dumps({"scenes": [{"beat": i, "scene": {"bg": {"type": "field"}, "elements": [
                {"type": "char", "kind": "bicorne", "x": 600, "y": 900}]}} for i in range(idx[0], idx[1] + 1)]}), {}

    monkeypatch.setattr(stages, "provider", lambda meta, stage, ctx=None, task=None: Writer())
    monkeypatch.setattr(stages, "render_previews", lambda *a, **k: None)
    pr = new_project("Host", "topic", topic="Napoleon", options={"minutes": 1, "storyboard_engine": "classic"})
    s = script()
    from studio.pipeline import mascot as M
    M.add_host_beats(s, {})
    pr.save_script(s)
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    sb = json.load(open(pr.p("storyboard.json")))
    assert sb["scenes"]["1"]["source"] == "host" and sb["scenes"]["5"]["source"] == "host"
    asks = "\n".join(p.split("Make one scene for each of these beats:")[-1] for p in prompts)
    assert "Sticky" not in asks and "Napoleon marched into Italy." in asks


# ------------------------------------------------------------------ who does what, and the plan savers
def test_task_writer_picks(monkeypatch):
    from studio.pipeline import writers as WR
    meta = {"providers": {"llm": "claude_cli"}}
    s = {"task_writers": {"storyboard": "gemini", "package": "nope"}}
    assert WR.task_writer_id(meta, "storyboard", s) == "gemini"
    assert WR.task_writer_id(meta, "package", s) == "claude_cli"      # unknown ids fall back to the video's writer
    assert WR.task_writer_id(meta, "script", s) == "claude_cli"
    S = "claude-sonnet-5-5"
    assert WR.claude_model("script", {"plan_saver": "balanced"}) == S          # Sonnet 5.5 is the main model
    assert WR.claude_model("storyboard", {"plan_saver": "off"}) == S
    assert WR.claude_model("package", {"plan_saver": "balanced"}) == S
    assert WR.claude_model("short", {"plan_saver": "balanced"}) == "claude-haiku-4-5"     # the lightest job
    assert WR.claude_model("package", {"plan_saver": "max"}) == "claude-haiku-4-5"
    assert WR.claude_model("package", {"plan_saver": "max", "claude_task_models": {"package": "opus"}}) == "claude-opus-5-5"
    assert WR.claude_model("package", {"claude_task_models": {"package": "default"}}) == ""   # your Claude Code default
    assert WR.claude_model("script", {"llm_models": {"claude_cli": "opus"}}) == "claude-opus-5-5"
    assert WR.claude_model("script", {"llm_models": {"claude_cli": "default"}}) == ""
    assert WR.main_model({}) == S


def test_claude_task_sends_the_model_and_effort(monkeypatch):
    from studio.pipeline import writers as WR
    from studio.providers.llm import ClaudeCLI
    import subprocess
    seen = []

    class R:
        returncode, stderr = 0, ""
        stdout = json.dumps({"result": "{}", "subtype": "success", "structured_output": {"ok": 1}})

    monkeypatch.setattr(ClaudeCLI, "path", lambda self: "/usr/bin/claude")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (seen.append(cmd), R())[1])
    monkeypatch.setattr(WR, "_cli_flags", lambda cmd: "  --effort <level>  ")
    monkeypatch.setattr(WR, "load_settings", lambda: {"plan_saver": "balanced", "llm_models": {}})
    t = WR.ClaudeTask(ClaudeCLI(), "package", {"plan_saver": "balanced"})
    t.complete("sys", "Write titles", schema={"type": "object"}, label="package")
    cmd = seen[-1]
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-5-5" and cmd[cmd.index("--effort") + 1] == "low"
    s = WR.ClaudeTask(ClaudeCLI(), "storyboard", {"plan_saver": "balanced"})
    assert s.batch_beats == 12 and s.warm_first and s.model == "claude-sonnet-5-5" and s.id == "claude_cli"
    d = WR.ClaudeTask(ClaudeCLI(), "storyboard", {"plan_saver": "balanced", "llm_models": {"claude_cli": "default"}})
    d.complete("sys", "x", label="x")
    assert "--model" not in seen[-1]                      # "default" = no --model: your own Claude Code default


def test_paid_task_writers_are_always_estimated(monkeypatch, tmp_path):
    from studio.pipeline import costs
    from studio import config
    real = config.load_settings()
    monkeypatch.setattr(costs, "load_settings", lambda: dict(real, task_writers={"package": "anthropic"}))
    from studio.pipeline import writers as WR
    monkeypatch.setattr(WR, "load_settings", lambda: dict(real, task_writers={"package": "anthropic"}))
    est = costs.estimate_draft("topic", {"llm": "claude_cli"}, {"minutes": 2})
    assert est["package"]["lines"] and "Anthropic" in est["package"]["lines"][0]["provider"]
    assert not est["storyboard"]["lines"]


def test_backups_are_free_only(monkeypatch):
    from studio.providers import backup as B
    monkeypatch.setattr(B, "load_settings", lambda: {"backup_writer": "anthropic"})
    assert B.backup_for("claude_cli") is None


def test_new_bg_types_are_in_the_docs():
    from studio.prompts import scene_language, scene_language_compact
    full, short = scene_language(), scene_language_compact()
    for t in PLACES:
        assert t in BG_TYPES and t in full
    assert "THE PLACE IS THE BACKGROUND" in full and "THE PLACE IS THE BACKGROUND" in short
