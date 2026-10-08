"""The v2 pipeline end to end with a stand-in writer: research (budget, cache, sources), claim linking, the evidence-first
fact-check, the storyboard with coverage/world state/muted test/specs/preview, the render gate, approval and the estimate."""
import json
import os

import pytest

from studio import cache, config
from studio.pipeline import stages, runner, estimate
from studio.pipeline.project import new_project
from studio.pipeline.runner import Ctx
from studio.research import budget as BD, store as ST

AR = "The American Revolution"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "d"))
    cache.clear()
    yield
    cache.clear()


def research_json(n=16):
    srcs = [dict(url="https://www.archives.gov/founding-docs/declaration", title="Declaration of Independence", organization="National Archives", date="2023")] + [
        dict(url=f"https://www.loc.gov/item/{i}/", title=f"LoC {i}", organization="Library of Congress", date="2020") for i in range(1, 6)]
    return dict(summary="Thirteen colonies broke from Britain between 1775 and 1783.",
                timeline=[dict(year=1765 + i, event=f"event {i} in the colonies") for i in range(8)],
                people=[dict(name=n_, role="r", years="1732-1799", look="l", trait="t") for n_ in ("George Washington", "King George III", "Thomas Jefferson", "Benjamin Franklin", "John Adams")],
                places=[dict(name="Boston", note="Massachusetts")], documents=[dict(name="Declaration of Independence", lines=["WE HOLD THESE TRUTHS"])],
                numbers=[dict(claim="colonies", value="13")], visuals=["Boston Tea Party"],
                claims=[dict(claim=c, url=srcs[k % 6]["url"], evidence="page says so", confidence="high") for k, c in enumerate([
                    "In 1773 colonists dumped 342 chests of tea into Boston Harbor.", "In 1775 fighting began at Lexington and Concord.",
                    "In 1776 the Declaration of Independence was adopted in Philadelphia.", "In 1787 delegates wrote the Constitution in Philadelphia.",
                    "Thirteen British colonies lay along the Atlantic coast of North America.", "In 1781 Cornwallis surrendered at Yorktown.",
                    "In 1783 the Treaty of Paris recognized American independence."] + [f"Fact number {i} about the colonies in {1760 + i}." for i in range(n - 7)])],
                sources=srcs, queries_used=["american revolution timeline", "boston tea party archives", "declaration of independence"], gaps=[])


SCRIPT = {"title": "The American Revolution", "topic": AR, "cast": [{"name": "George Washington", "kind": "tricorn", "hat_color": "black", "coat": "#2B3F8C"}],
          "facts": [{"beat": 1, "claim": "342 chests of tea", "confidence": "high", "note": ""}],
          "beats": [
              {"mood": "fun", "part": "hook", "text": "In 1773 colonists dumped 342 chests of tea into Boston Harbor.", "purpose": "start with the protest",
               "location": "Boston Harbor", "visual": "colonists and ships in Boston Harbor at night"},
              {"mood": "fun", "part": "story", "text": "England established 13 colonies along the Atlantic coast.", "purpose": "show where the colonies were",
               "location": "Atlantic coast of North America", "visual": "map of the 13 colonies, England across the ocean"},
              {"mood": "tense", "part": "story", "text": "In 1787 the colonists eventually wrote the Constitution in Philadelphia.", "purpose": "how the nation got its rules",
               "location": "Philadelphia", "visual": "delegates writing the Constitution"},
              {"mood": "fun", "part": "payoff", "text": "In 1781 Cornwallis surrendered at Yorktown, and the war was won.", "purpose": "the ending",
               "location": "Yorktown", "visual": "the surrender at Yorktown"}]}


class Writer:
    id, label, paid, supports_images, supports_web, short = "fake", "Fake", False, False, True, "Fake"
    parallel, batch_beats, examples = 2, 12, 20

    def __init__(self, research=None, script=None):
        self.calls, self.research, self.script = [], research or research_json(), script or SCRIPT

    def available(self):
        return True, ""

    def complete(self, system, prompt, schema=None, images=(), label="", **kw):
        self.calls.append(label)
        if label == "research":
            return json.dumps(self.research), {}
        if label == "script":
            return json.dumps(self.script), {}
        if label.startswith("plan"):
            return json.dumps({"plan": []}), {}
        if label == "props":
            return json.dumps({"props": []}), {}
        raise AssertionError("unexpected AI call: " + label)


def patch_provider(monkeypatch, writer):
    monkeypatch.setattr(stages, "provider", lambda meta, stage, ctx=None, task=None: writer)
    monkeypatch.setattr(stages, "render_previews", lambda *a, **k: None)


def project(name="V2 test", **opts):
    return new_project(name, "topic", topic=AR, options=dict(minutes=1, gen_mode="normal", mascot=False, **opts))


# ---------------------------------------------------------------- script stage: research, claims, fact-check
def test_script_stage_researches_once_tracks_sources_and_skips_the_factcheck_when_evidence_covers(monkeypatch):
    pr, w = project(), Writer()
    patch_provider(monkeypatch, w)
    stages.stage_script(Ctx(pr, "script"))
    assert w.calls.count("research") == 1 and "facts" not in w.calls                 # evidence covered the script: no fact-check call
    d = pr.p("research")
    assert sorted(os.listdir(d)) == ["claims.json", "report.json", "sources.json"]
    claims = json.load(open(os.path.join(d, "claims.json")))
    assert any(0 in c["used_in_scenes"] for c in claims)                             # the tea claim is used by beat 0
    script = pr.script()
    assert script["factcheck"]["by"] == "research" and script["evidence"]["unsupported"] == []
    assert script["beats"][1]["location"] == "Atlantic coast of North America" and script["beats"][2]["purpose"]
    assert os.path.isdir(os.path.join(ST.root(), "the-american-revolution")) or os.path.isdir(os.path.join(ST.root(), "american-revolution"))


def test_a_second_video_on_the_same_topic_does_no_research(monkeypatch):
    patch_provider(monkeypatch, Writer())
    stages.stage_script(Ctx(project("first"), "script"))
    w2 = Writer()
    patch_provider(monkeypatch, w2)
    pr2 = project("second")
    stages.stage_script(Ctx(pr2, "script"))
    assert "research" not in w2.calls
    rep = json.load(open(pr2.p("research", "report.json")))
    assert rep["cached"] is True and rep["budget"]["queries"] == 0 and rep["budget"]["cached_hits"] > 0


def test_only_unsupported_items_go_to_the_factcheck(monkeypatch):
    script = json.loads(json.dumps(SCRIPT))
    script["beats"][3]["text"] = "In 1799 Cornwallis lost 9000 men at Yorktown."
    w = Writer(script=script)
    patch_provider(monkeypatch, w)
    prompts = []
    orig = w.complete

    def spy(system, prompt, schema=None, images=(), label="", **kw):
        if label == "facts":
            prompts.append(prompt)
            return json.dumps({"checks": [], "rewrites": []}), {}
        return orig(system, prompt, schema, images, label, **kw)
    w.complete = spy
    stages.stage_script(Ctx(project("unsupported"), "script"))
    assert prompts and "Check ONLY these items" in prompts[0] and "1799" in prompts[0] and "9000" in prompts[0]


def test_budget_reached_pauses_the_run_and_the_grant_continues_it(monkeypatch):
    thin = research_json(n=5)
    thin["sources"] = thin["sources"][:1]
    thin["claims"] = thin["claims"][:5]
    pr = project("budget", research={"max_queries": 2})
    w = Writer(research=thin)
    patch_provider(monkeypatch, w)
    with pytest.raises(BD.ResearchBudgetReached) as e:
        stages.stage_script(Ctx(pr, "script"))
    assert e.value.info["gaps"] and e.value.info["proposal"]["queries"] >= 3
    # the runner turns that into 'awaiting_approval' with the question attached (never a silent overrun, never an error)
    pr2 = project("budget2", research={"max_queries": 2})
    status = runner.run(pr2, start="script", stop_after="script")
    assert status == "awaiting_approval" and pr2.meta()["pending"]["type"] == "research" and pr2.meta()["pending"]["gaps"]


def test_approve_endpoint_sets_the_grant_and_use_what_we_have_stops_asking(monkeypatch):
    from fastapi.testclient import TestClient
    from studio.server import app as appmod
    monkeypatch.setattr(appmod, "start_background", lambda *a, **k: None)
    pr = project("approve")
    pr.update(lambda m: m.update(pending=dict(type="research", gaps=["x"])))
    c = TestClient(appmod.app, base_url="http://localhost", headers={"X-Studio": "1"})
    assert c.post(f"/api/projects/{pr.slug}/research/approve", json=dict(queries=6, sources=9, seconds=120)).status_code == 200
    m = pr.meta()
    assert m["research_grant"] == dict(queries=6, sources=9, seconds=120) and m["pending"] is None
    assert c.post(f"/api/projects/{pr.slug}/research/approve", json=dict(use_what_we_have=True)).status_code == 200
    assert pr.meta()["options"]["research"]["require_approval_for_extra_research"] is False
    r = c.get(f"/api/projects/{pr.slug}/research").json()
    assert "claims" in r and "sources_used" in r


# ---------------------------------------------------------------- storyboard: coverage, world, muted, specs, preview, gate
def test_storyboard_makes_scenes_that_show_the_narration_and_writes_everything_the_user_reviews(monkeypatch):
    pr, w = project("sb"), Writer()
    patch_provider(monkeypatch, w)
    stages.stage_script(Ctx(pr, "script"))
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    rv = json.load(open(pr.p("review.json")))
    assert rv["coverage"]["mean"] >= 0.9 and not rv["coverage"]["blocked"] and rv["muted"]["score"] >= 0.7
    sb = json.load(open(pr.p("storyboard.json")))
    patterns = [sb["scenes"][str(i)].get("pattern") for i in range(4)]
    assert patterns[:4] == ["FAMOUS_EVENT", "COLONIZATION", "DOCUMENT_SIGNING", "FAMOUS_EVENT"] or "COLONIZATION" in patterns and "DOCUMENT_SIGNING" in patterns
    for i in range(4):
        spec = json.load(open(pr.p("storyboard", "specs", f"{i:03d}.json")))
        assert spec["narration"] == SCRIPT["beats"][i]["text"] and spec["coverage"]["score"] >= 0.8 and spec["world"]["period"]["year"] is not None
    assert os.path.exists(pr.p("storyboard", "preview.html")) and "Scene 2" in open(pr.p("storyboard", "preview.html")).read()
    ws = json.load(open(pr.p("world_state.json")))
    assert ws["scenes"]["2"]["period"]["year"] == 1787 and ws["scenes"]["1"]["location"]["region"] == "thirteen_colonies"
    assert w.calls.count("research") == 1 and not [c for c in w.calls if c.startswith("storyboard")]    # no per-scene AI calls


def test_package_lists_only_the_sources_the_script_uses(monkeypatch):
    pr = project("src")
    patch_provider(monkeypatch, Writer())
    stages.stage_script(Ctx(pr, "script"))
    used = stages.used_sources(pr)
    assert used and all(s["claims"] for s in used)
    claims = json.load(open(pr.p("research", "claims.json")))
    unused = [c for c in claims if not c["used_in_scenes"]]
    assert unused and len(used) <= len(json.load(open(pr.p("research", "sources.json"))))


def test_render_gate_blocks_scenes_that_dont_show_their_narration_unless_allowed():
    pr = project("gate")
    pr.save_script({"title": "x", "topic": "x", "beats": [{"mood": "fun", "text": "a"}, {"mood": "fun", "text": "b"}], "cast": []})
    json.dump(dict(coverage=dict(blocked=[1], failed=[1], per_beat={"0": 1.0, "1": 0.2}, missing={"1": ["13 colonies (region)"]})), open(pr.p("review.json"), "w"))
    from studio import providers as P
    with pytest.raises(P.ProviderError) as e:
        stages.coverage_gate(pr, [0, 1], {}, {})
    assert "scene 2 covers 20%" in str(e.value) and "13 colonies" in str(e.value)
    stages.coverage_gate(pr, [0], {}, {})                                    # a scene that is fine renders
    stages.coverage_gate(pr, [0, 1], {"allow_low_coverage": True}, {})
    stages.coverage_gate(pr, [0, 1], {}, {"coverage_gate": "warn"})


# ---------------------------------------------------------------- estimate
def test_estimate_shows_research_and_a_usage_level_per_kind_of_work(monkeypatch):
    pr = project("est")
    e = estimate.estimate_video(pr)
    assert e["research"]["mode"] == "normal" and e["research"]["max_queries"] == 10 and not e["research"]["covered"]
    assert e["levels"]["Rendering, animation, audio, video"].startswith("LOCAL") and e["usage_level"] in ("LOW", "MEDIUM", "HIGH")
    patch_provider(monkeypatch, Writer())
    stages.stage_script(Ctx(pr, "script"))
    e2 = estimate.estimate_video(project("est2"))
    assert e2["research"]["covered"] and not [i for i in e2["items"] if i["task"] == "research" and i["calls"]]
