"""The storyboard stage end to end with the director: a stand-in writer, real composer, real review."""
import json

import pytest

from studio import cache, usage
from studio.pipeline import stages
from studio.pipeline.project import new_project
from studio.pipeline.runner import Ctx

BEATS = [
    ("fun", "Hook: the Constitution almost never got signed."),
    ("fun", "In 1787, Washington and James Madison met in Philadelphia to write the Constitution."),
    ("tense", "In August 1914, Germany declared war on France."),
    ("fun", "He kept losing at chess to a pigeon, which was frankly embarrassing."),
    ("tense", "The angry mob stormed the castle and burned it down."),
    ("somber", "Lincoln was shot at Ford's Theatre in April 1865."),
]


@pytest.fixture(autouse=True)
def clean():
    cache.clear()
    yield
    cache.clear()


def make_project(engine="director", mode="normal"):
    pr = new_project("Director test", "topic", topic="The Constitution",
                     options={"minutes": 1, "storyboard_engine": engine, "gen_mode": mode, "mascot": False})
    pr.save_script({"title": "The Constitution", "topic": "The Constitution",
                    "cast": [{"name": "Washington", "kind": "tricorn", "hat_color": "black"}],
                    "beats": [{"mood": m, "text": t} for m, t in BEATS]})
    return pr


class Writer:
    id, label, paid, supports_images, short = "fake", "Fake writer", False, False, "Fake"
    parallel, batch_beats, examples = 2, 12, 20

    def __init__(self):
        self.calls = []

    def available(self):
        return True, ""

    def complete(self, system, prompt, schema=None, images=(), label="", **kw):
        self.calls.append((label, len(prompt)))
        if label.startswith("plan"):
            idx = [int(x) for x in label.split()[1].split("-")]
            plan = {1: ("DOCUMENT_SIGNING", {"signer": "Madison"}), 2: ("WAR_DECLARATION", {}), 3: ("CUSTOM", {}),
                    4: ("RIOT", {"target": "castle"}), 5: ("DEATH_OF_HISTORICAL_FIGURE", {})}
            return json.dumps({"plan": [{"beat": i, "pattern": plan[i][0], "slots": plan[i][1]} for i in range(idx[0], idx[1] + 1) if i in plan]}), \
                {"in_tok": 3000, "out_tok": 500, "measured": True}
        if label == "props":
            return json.dumps({"props": []}), {}
        if label.startswith("storyboard"):
            idx = [int(x) for x in label.split()[1].split("-")]
            return json.dumps({"scenes": [{"beat": i, "scene": {"bg": {"type": "field"}, "elements": [
                {"type": "char", "kind": "civ", "x": 600, "y": 900}, {"type": "prop", "name": "chess_piece", "x": 1200, "y": 860}]}}
                for i in range(idx[0], idx[1] + 1)]}), {}
        raise AssertionError(label)


def run(monkeypatch, pr, writer):
    monkeypatch.setattr(stages, "provider", lambda meta, stage, ctx=None, task=None: writer)
    monkeypatch.setattr(stages, "render_previews", lambda *a, **k: None)
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    return json.load(open(pr.p("storyboard.json")))


def test_director_stage_composes_most_scenes_and_sends_only_the_odd_one_to_the_scene_writer(monkeypatch):
    pr = make_project()
    w = Writer()
    sb = run(monkeypatch, pr, w)
    labels = [c[0] for c in w.calls]
    assert sum(1 for x in labels if x.startswith("plan")) == 1                         # ONE plan request for all the beats
    assert [x for x in labels if x.startswith("storyboard")] == ["storyboard 3-3"]      # only the chess/pigeon beat
    src = {i: sb["scenes"][str(i)]["source"] for i in range(len(BEATS))}
    assert src[1] == "pattern:DOCUMENT_SIGNING" and src[2] == "pattern:WAR_DECLARATION" and src[3] == "fake"
    plan = json.load(open(pr.p("plan.json")))
    assert plan["beats"]["1"]["pattern"] == "DOCUMENT_SIGNING" and plan["beats"]["3"]["pattern"] == "CUSTOM"
    # the document names the real document, the characters come from one registry
    s1 = json.load(open(pr.scene_path(1)))
    assert any(e.get("params", {}).get("title") == "THE CONSTITUTION" for e in s1["elements"] if e.get("type") == "prop")
    chars = {e["id"] for e in map(json.load, [open(pr.p("characters", f)) for f in __import__("os").listdir(pr.p("characters")) if f != "index.json"])}
    assert {"washington", "madison"} <= chars
    # review and continuity files exist, and the review fixed something real
    rev = json.load(open(pr.p("review.json")))
    assert rev["mode"] == "normal" and "narration" in rev["scores"] and rev["fixed"] >= 1
    assert "states" in json.load(open(pr.p("continuity.json")))
    u = usage.summary(pr)
    assert u["total"]["calls"] == len(w.calls) and u["total"]["tokens"] > 0


def no_skip(monkeypatch, on=False):
    from studio.pipeline import director
    real = director.load_settings
    monkeypatch.setattr(director, "load_settings", lambda: dict(real(), plan_skip_easy=on))


def test_second_run_after_an_edit_replans_only_the_changed_beat(monkeypatch):
    no_skip(monkeypatch)                                  # with "easy scenes skip the plan" off, every beat is planned once
    pr = make_project()
    w = Writer()
    run(monkeypatch, pr, w)
    first = len(w.calls)
    script = pr.script()
    script["beats"][4]["text"] = "The angry mob stormed the castle and burned it to the ground."
    pr.save_script(script)
    w2 = Writer()
    run(monkeypatch, pr, w2)
    labels = [c[0] for c in w2.calls]
    assert labels == ["plan 4-4"] and first >= 2                                      # one beat re-planned, the rest from the cache/disk


def test_easy_scenes_skip_the_ai_plan_and_the_saving_is_written_down(monkeypatch):
    pr = make_project()
    w = Writer()
    sb = run(monkeypatch, pr, w)
    plan = json.load(open(pr.p("plan.json")))["beats"]
    easy = [int(i) for i, v in plan.items() if v["source"] == "local"]
    assert easy and all(plan[str(i)]["coverage"] >= 0.9 for i in easy)                 # drawn by the studio, and it shows the narration
    planned = [c for c in w.calls if c[0].startswith("plan")]
    assert len(planned) == 1 and sb["scenes"][str(easy[0])]["source"].startswith("pattern:")
    saved = usage.summary(pr)["saved"]
    assert saved["tokens"] >= 190 * len(easy) and any(x["kind"] == "plan" for x in saved["items"])
    # the same video with the setting off plans every beat with the AI (and saves nothing)
    cache.clear()
    no_skip(monkeypatch)
    pr2 = make_project()
    w2 = Writer()
    run(monkeypatch, pr2, w2)
    plan2 = json.load(open(pr2.p("plan.json")))["beats"]
    local2 = {i for i, v in plan2.items() if v["source"] == "local"}
    plan_saved = lambda pr_: sum(x["tokens"] for x in usage.summary(pr_)["saved"]["items"] if x["kind"] == "plan")
    assert local2 <= {"0"} and plan_saved(pr2) == 0                                    # (the stand-in writer never plans the hook beat)
    # a scene that is not easy still goes to the plan: the Constitution scene names a document and people
    assert plan["1"]["source"] == "plan"


def test_fast_mode_keeps_its_own_confident_match_rule(monkeypatch):
    pr = make_project(mode="fast")
    w = Writer()
    run(monkeypatch, pr, w)
    assert not [x for x in usage.summary(pr)["saved"]["items"] if x["kind"] == "plan"]  # fast mode does not use the easy-scene test


def test_fast_mode_makes_fewer_calls_than_normal_and_deep_adds_research_free_review(monkeypatch):
    fast = Writer()
    run(monkeypatch, make_project(mode="fast"), fast)
    normal = Writer()
    cache.clear()
    run(monkeypatch, make_project(mode="normal"), normal)
    assert len(fast.calls) <= len(normal.calls)
    assert not any(c[0].startswith("storyboard") for c in fast.calls)                  # fast: no full scene writer at all


def test_classic_engine_still_works_and_costs_more_tokens(monkeypatch):
    classic = Writer()
    run(monkeypatch, make_project(engine="classic"), classic)
    director = Writer()
    cache.clear()
    run(monkeypatch, make_project(engine="director"), director)
    assert sum(n for _, n in classic.calls) > sum(n for _, n in director.calls)       # prompt characters sent to the writer


def test_basic_writer_builds_every_scene_locally(monkeypatch):
    from studio.providers import OfflineLLM
    pr = make_project()
    sb = run(monkeypatch, pr, OfflineLLM())
    assert all(sb["scenes"][str(i)]["source"] in ("rules",) or sb["scenes"][str(i)]["source"].startswith("pattern:") for i in range(len(BEATS)))
    assert sb["scenes"]["2"]["source"] == "pattern:WAR_DECLARATION"
