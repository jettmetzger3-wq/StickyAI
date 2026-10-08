"""Stickman Studio 2.0: meaning-based visuals. The picture must show what the narrator MEANS (the user's own examples:
"England established 13 colonies along the Atlantic coast", "The colonists wrote the Constitution"), not what keywords
happen to match. Plus world state, the muted test, scene specs and the preview page, reference images and assets."""
import json
import os

import pytest

from studio import cache
from studio.engine.schema import check_scene
from studio.knowledge import analysis as AN, composer as CO, patterns as PT, semantics as SM
from studio.pipeline import assets as AS, coverage as CV, muted as MU, reference as RF, spec as SP, world as WD

TOPIC = "The American Revolution"
COLONIES = "England established 13 colonies along the Atlantic coast."
CONSTITUTION = "The colonists eventually wrote the Constitution."
TEA = "The colonists dumped tea into Boston Harbor during the Boston Tea Party in 1773."


def prep(text, mood="fun", topic=TOPIC):
    a = SM.enrich(AN.analyze(text, mood, [], set()), text, topic)
    return a, SM.requirements(a, text)


def best(text, topic=TOPIC):
    a, reqs = prep(text, topic=topic)
    got = CV.choose(None, dict(mood="fun", text=text), a, reqs, [], 3, {}, topic, PT.best(a))
    fixed, fixes, errs = check_scene(got["scene"], "fun", text)
    assert not errs, errs
    return a, reqs, got, fixed, SM.coverage(reqs, fixed)


# ---------------------------------------------------------------- the user's examples
def test_colonies_sentence_is_a_map_of_the_colonies_not_of_england():
    a, reqs, got, scene, cov = best(COLONIES)
    assert got["pattern"] == "COLONIZATION" and cov["score"] == 1.0
    assert {r["canon"] for r in reqs} >= {"13 colony", "colonial territory", "north america", "atlantic coast"}
    assert scene["bg"]["type"] == "map" and any(e.get("region") == "thirteen_colonies" for e in scene["elements"])
    assert any(e["type"] == "arrow" and e.get("units") for e in scene["elements"])                 # the ship crossing from England
    assert any(e.get("type") == "territory" and "United Kingdom" in (e.get("countries") or []) for e in scene["elements"])


def test_the_old_england_and_france_slide_fails_the_coverage_gate():
    a, reqs = prep(COLONIES)
    old = {"bg": {"type": "map", "style": "dark", "center": [-2.0, 54.4], "width": 30.0},
           "elements": [{"type": "territory", "countries": ["United Kingdom"]}, {"type": "text", "text": "UNITED KINGDOM", "lon": -2, "lat": 54}]}
    cov = SM.coverage(reqs, old)
    assert cov["score"] < SM.COVERAGE_FAIL and any(m["value"] == "13 colonies" for m in cov["must_missing"])


def test_the_constitution_beat_is_the_convention_not_a_generic_crowd_in_parliament():
    a, reqs, got, scene, cov = best(CONSTITUTION)
    assert got["pattern"] == "DOCUMENT_SIGNING" and cov["score"] >= 0.9
    names = {e.get("who") for e in scene["elements"] if e.get("type") == "char"}
    assert {"James Madison", "George Washington"} <= names
    assert any(e.get("type") == "text" and "1787" in e.get("text", "") for e in scene["elements"])
    assert any(e.get("type") == "prop" and e["name"] == "document" and "CONSTITUTION" in str(e.get("params", {}).get("title", "")).upper() for e in scene["elements"])


def test_a_famous_event_is_shown_in_its_real_place_and_year():
    a, reqs, got, scene, cov = best(TEA)
    assert got["pattern"] == "FAMOUS_EVENT" and cov["score"] == 1.0 and scene["bg"]["type"] == "harbor"
    assert any("1773" in e.get("text", "") for e in scene["elements"] if e.get("type") == "text")
    assert [p["name"] for p in a["people"]] == []                         # "Boston Harbor" / "Boston Tea" are not people


def test_the_colonies_alone_is_a_region_map_and_an_unrelated_topic_is_not_hijacked():
    a, reqs, got, scene, cov = best("The colonies stretched along the Atlantic coast.")
    assert got["pattern"] == "MAP_EXPLANATION" and cov["score"] == 1.0
    b = SM.enrich(AN.analyze("The colonies of Spain stretched across Peru.", "fun", [], set()), "The colonies of Spain stretched across Peru.", "The Spanish Empire")
    assert not b["regions"] and b["map"] is None


def test_meaning_beats_the_directors_wrong_pattern_by_coverage():
    a, reqs = prep(CONSTITUTION)
    wrong = dict(pattern="LAW_BEING_PASSED", slots={}, say=[], needs=[])
    got = CV.choose(wrong, dict(mood="fun", text=CONSTITUTION), a, reqs, [], 3, {}, TOPIC, PT.best(a))
    assert got["pattern"] == "DOCUMENT_SIGNING"
    assert dict(got["tried"])["LAW_BEING_PASSED"] < dict(got["tried"])["DOCUMENT_SIGNING"]


def test_plan_needs_are_scored_like_the_local_ones():
    a, reqs = prep("Franklin charmed the French court.")
    extra = SM.requirements(a, "Franklin charmed the French court.", needs=["Versailles palace", "1778"])
    kinds = {r["value"]: r["kind"] for r in extra}
    assert kinds.get("1778") in ("time", "number") and "Versailles palace" in kinds


def test_missing_pieces_are_patched_in_when_a_plain_addition_can_do_it():
    text = "Napoleon marched into Italy in 1796."
    a, reqs = prep(text)
    sc = {"bg": {"type": "field"}, "elements": [{"type": "prop", "name": "flag", "x": 900, "y": 700}]}
    out = []
    cov = CV.check(0, sc, a, reqs, [], out)
    assert any(e.get("type") == "char" for e in sc["elements"]) and cov["score"] > SM.coverage(reqs, {"bg": {"type": "field"}, "elements": []})["score"]


# ---------------------------------------------------------------- world state and the muted test
def test_world_state_is_inherited_and_a_time_jump_is_flagged():
    beats = [dict(text="In 1773 colonists dumped tea in Boston.", purpose="the protest"), dict(text="Colonists gathered at the harbor."),
             dict(text="In 1701 a school was founded."), dict(text="A century passed and 1900 arrived.")]
    scenes = {i: {"bg": {"type": "harbor"}, "elements": []} for i in range(4)}
    worlds, prev = {}, None
    for i, b in enumerate(beats):
        a = SM.enrich(AN.analyze(b["text"], "fun", [], set()), b["text"], TOPIC)
        prev = worlds[i] = WD.update(prev, scenes[i], a, b, "X")
    assert worlds[1]["period"]["year"] == 1773 and worlds[0]["narrative"]["purpose"] == "the protest"        # scene 2 inherits 1773
    issues = WD.check(worlds, beats, scenes)
    assert any("jumps back" in x["msg"] for x in issues)


def test_muted_test_flags_a_blank_slide_and_accepts_a_story_map():
    a, reqs, got, scene, cov = best(COLONIES)
    blank = {"bg": {"type": "paper"}, "elements": [{"type": "char", "kind": "civ", "x": 900, "y": 890}]}
    beats = [dict(text=COLONIES, mood="fun"), dict(text="Then things changed.", mood="fun")]
    res = MU.run({0: scene, 1: blank}, [a, {}], beats)
    assert res["per_scene"]["0"]["score"] >= 0.8 and res["per_scene"]["1"]["score"] < 0.6 and res["weak"] == [1]
    res2 = MU.run({0: scene}, [a], beats[:1], coverage={"0": 0.2})
    assert res2["per_scene"]["0"]["score"] <= 0.4


# ---------------------------------------------------------------- spec + preview
def test_scene_spec_has_the_structured_fields_and_the_preview_page_shows_coverage(tmp_path):
    from studio.pipeline.project import new_project
    pr = new_project("Spec test", "topic", topic="x", options={"minutes": 1})
    a, reqs, got, scene, cov = best(COLONIES)
    beats = [dict(text=COLONIES, mood="fun", purpose="show where the colonies were", visual="map of the 13 colonies", claims=["c1"])]
    w = WD.update(None, scene, a, beats[0], "COLONIZATION")
    specs = SP.write_all(pr, beats, {0: scene}, [a], {0: dict(pattern="COLONIZATION")}, {0: cov}, {0: w}, [8.5], [])
    s = json.load(open(pr.p("storyboard", "specs", "000.json")))
    assert {"scene_id", "duration", "narration", "template", "visual_requirements", "location", "characters", "props", "actions",
            "camera", "transition", "coverage", "world", "scene_hash"} <= set(s)
    assert s["template"] == "COLONIZATION" and s["location"]["type"] == "map" and "highlight_region:thirteen_colonies" in s["actions"]
    assert s["coverage"]["score"] == 1.0 and s["claims"] == ["c1"] and s["transition"]["target_scene"] is None
    page = SP.preview_html("Test", specs, MU.run({0: scene}, [a], beats))
    assert "England established 13 colonies" in page and "Coverage" in page and "100%" in page
    assert SP.write_all(pr, beats, {0: scene}, [a], {0: dict(pattern="COLONIZATION")}, {0: cov}, {0: w}, [8.5], [])[0]["scene_hash"] == s["scene_hash"]   # deterministic


# ---------------------------------------------------------------- reference images and assets
def test_reference_composition_is_rebuilt_with_the_studios_own_assets_and_substitutions_are_reported():
    comp = {"summary": "Washington speaks to soldiers", "background": {"kind": "field"},
            "characters": [{"name": "George Washington", "x": 0.3, "y": 0.92, "size": "large", "pose": "point", "hat": "tricorn"},
                           {"role": "soldiers", "x": 0.7, "y": 0.93, "group": True, "count": 12, "hat": "tricorn", "facing": "left"}],
            "props": [{"name": "american flag", "x": 0.55, "y": 0.5, "size": "large"}, {"name": "spaceship", "x": 0.1, "y": 0.2}],
            "text": [{"text": "VALLEY FORGE", "x": 0.5, "y": 0.12, "size": "large"}], "camera": {"framing": "close", "focus": [0.3, 0.6]}}
    scene, rep = RF.to_scene(comp)
    fixed, fixes, errs = check_scene(scene, "fun", "x")
    assert not errs and rep["missing"] == ["spaceship"] and any("flag" in x for x in rep["substituted"])
    assert any(e.get("who") == "George Washington" for e in fixed["elements"]) and fixed["camera"].get("shots")


def test_reference_analysis_is_cached_and_needs_a_writer_that_can_see(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(b"\x89PNG fake")
    cache.clear()

    class Eyes:
        id, label, supports_images, calls = "eyes", "Eyes", True, 0

        def complete(self, system, prompt, schema=None, images=(), label="", **kw):
            Eyes.calls += 1
            assert images and "do not describe artistic style" in prompt.lower()
            return json.dumps({"summary": "s", "characters": [], "props": []}), {}

    first, c1 = RF.analyze(Eyes(), str(img))
    second, c2 = RF.analyze(Eyes(), str(img))
    assert (c1, c2, Eyes.calls) == (False, True, 1) and first == second

    class Blind:
        id, label, supports_images = "blind", "Blind", False
    with pytest.raises(RuntimeError):
        RF.analyze(Blind(), str(tmp_path / "other.png")) if (tmp_path / "other.png").write_bytes(b"x") else None


def test_asset_lookup_reuses_before_creating():
    assert AS.find("prop", "teapot") == ("teapot", "exact")
    assert AS.find("prop", "british warship")[0] == "ship" or AS.find("prop", "british warship")[0] is not None
    assert AS.find("prop", "quantum flux capacitor") == (None, "")
    assert AS.find("hat", "tricorn")[0] == "tricorn" and AS.find("person", "Washington")[0] == "washington"
    assert AS.find("region", "thirteen_colonies")[0] == "thirteen_colonies"
    assert AS.missing({"bg": {"type": "harbor"}, "elements": [{"type": "prop", "name": "zzz_nothing"}]}) == [("prop", "zzz_nothing")]
    assert AS.inventory()["props"] > 200


# ---------------------------------------------------------------- found while checking the American Revolution demo frames
def test_an_event_can_be_told_two_ways_and_only_the_surrender_variant_claims_surrender():
    from studio.knowledge import analysis as AN, semantics as SM
    surrender = "Then in 1781 Cornwallis surrendered at Yorktown, and the war was finally won."
    siege = "The siege of Yorktown lasted three weeks."
    a = SM.enrich(AN.analyze(surrender), surrender)
    b = SM.enrich(AN.analyze(siege), siege)
    assert a["context"]["label"] == "THE SURRENDER AT YORKTOWN" and "surrender" in a["context"]["concepts"]
    assert b["context"]["label"] == "YORKTOWN" and "surrender" not in b["context"]["concepts"]


def test_a_named_far_country_is_drawn_on_the_map_but_only_a_founding_verb_sends_a_ship():
    from studio.knowledge import analysis as AN, semantics as SM
    far = "Thirteen British colonies sat along the Atlantic coast, an ocean away from England."
    founded = "England established 13 colonies along the Atlantic coast."
    m1 = SM.enrich(AN.analyze(far), far)["map"]
    m2 = SM.enrich(AN.analyze(founded), founded)["map"]
    assert m1["origin"]["name"].lower().startswith("england") or "britain" in m1["origin"]["name"].lower() or m1["origin"]
    assert m1["ship"] is False and m2["ship"] is True


def test_the_boston_tea_party_has_a_sailing_ship_not_a_modern_one():
    from studio.knowledge import semantics as SM
    tea = next(e for e in SM.CTX["events"] if e["id"] == "boston_tea_party")
    assert "galleon" in [p["name"] for p in tea["props"]] and "ship" not in [p["name"] for p in tea["props"]]


def test_a_look_in_words_becomes_a_hat_and_coat_for_people_we_dont_know():
    from studio.knowledge import people as PE
    from studio.pipeline import research as RS
    assert PE.look_from_text("red coat", "1738-1805") == {"coat": "#C8302B", "kind": "tricorn"}
    assert PE.look_from_text("round glasses") == {"kind": "glasses"}
    assert PE.look_from_text("plain coat", "1736-1799") == {}
    cast = RS.cast_from_brief({"people": [dict(name="Charles Cornwallis", role="British general", years="1738-1805", look="red coat", trait="proud"),
                                          dict(name="George Washington", role="general", years="1732-1799", look="blue coat, tricorn hat", trait="calm")]})
    assert cast[0]["coat"] == "#C8302B" and cast[0]["kind"] == "tricorn"
    assert "coat" not in cast[1]                     # people.json already knows Washington's look: the curated one wins


def test_a_close_up_never_cuts_a_label_or_bubble_in_half():
    from studio.pipeline import review as RV
    sc = {"elements": [{"type": "bubble", "text": "Shake on it?", "x": 232, "y": 283, "size": 44},
                       {"type": "text", "text": "Philadelphia, 1787", "x": 960, "y": 105, "size": 70}],
          "camera": {"shots": [{"at": 0, "zoom": 1.0}, {"at": 0.4, "zoom": 1.6, "focus": [960, 610]}]}}
    out = []
    RV.check_camera(0, sc, {}, out)
    assert sc["camera"]["shots"][1]["zoom"] == 1.0 and out and out[0]["fixed"]
    fine = {"elements": [{"type": "text", "text": "1787", "x": 960, "y": 300, "size": 70}],
            "camera": {"shots": [{"at": 0, "zoom": 1.6, "focus": [960, 540]}]}}
    out = []
    RV.check_camera(0, fine, {}, out)
    assert fine["camera"]["shots"][0]["zoom"] == 1.6 and not out
