"""Layout validation and local repair (studio/engine/layout.py) and how the pipeline uses it."""
import copy
import json
import os
import random

import pytest

from studio import cache, config
from studio.engine import layout as LY
from studio.engine.schema import check_scene, element_bbox


def scene(*els, bg=None, camera=None):
    sc = {"bg": bg or {"type": "paper"}, "elements": list(els)}
    if camera:
        sc["camera"] = camera
    return sc


def char(x=700, y=890, s=1.1, **kw):
    return dict({"type": "char", "x": x, "y": y, "scale": s, "kind": "tricorn"}, **kw)


def text(t, x=960, y=105, size=70, **kw):
    return dict({"type": "text", "text": t, "x": x, "y": y, "size": size}, **kw)


def bubble(t, x, y, tail=None, **kw):
    b = {"type": "bubble", "text": t, "x": x, "y": y, "size": 44}
    if tail is not None:
        b["tail"] = tail
    return dict(b, **kw)


def kinds(f, sev=("high", "medium")):
    return {x["kind"] for x in f if x["sev"] in sev}


def problems(sc, ctx=None):
    return [x for x in LY.audit(sc, ctx) if x["sev"] in ("high", "medium")]


# ---------------------------------------------------------------- 1. collisions
def test_a_speech_bubble_over_the_title_is_found_and_moved_to_free_space_with_its_tail_on_the_speaker():
    sc = scene(text("Philadelphia, 1787", 960, 105), char(960, 890, 1.1),
               bubble("Hello there, everyone.", 960, 105, tail=[0, 200]))
    assert "bubble_covers_text" in kinds(LY.audit(sc))
    left, fixes, esc = LY.fix_scene(sc)
    assert not problems(sc) and not esc and fixes
    b = next(e for e in sc["elements"] if e["type"] == "bubble")
    body, tip = LY.bubble_geometry(b)
    assert tip is not None and 24 <= tip[1] - body[3] <= 200                 # still a real tail, pointing down at the speaker
    assert abs(tip[0] - 960) < 200


def test_two_overlapping_labels_are_pulled_apart_without_shrinking_the_text():
    sc = scene(text("THE BOSTON TEA PARTY", 960, 400, 60), text("Boston Harbor, 1773", 960, 420, 60))
    assert "text_overlap" in kinds(LY.audit(sc))
    LY.fix_scene(sc)
    assert not problems(sc)
    assert [e["size"] for e in sc["elements"]] == [60, 60]                  # moved, never shrunk


def test_a_label_on_a_board_is_intentional_but_a_bubble_over_it_is_not():
    board = {"type": "board", "x": 960, "y": 400, "title": "VOTES", "lines": ["YES 39", "NO 3"], "size": 50}
    sc = scene(board, text("YES 39", 960, 400, 50), char(300, 890, 1.1))
    assert not problems(sc)
    sc["elements"].append(bubble("Look at this board!", 960, 400, tail=[-500, 300]))
    assert "bubble_covers_text" in kinds(LY.audit(sc))


def test_elements_that_are_never_on_screen_together_do_not_collide():
    a = bubble("First thing I say.", 700, 300, tail=[0, 100], at=0.1, exit=0.5)
    b = bubble("Then I say this.", 700, 300, tail=[0, 100], at=0.5, exit=0.9)
    sc = scene(char(700, 890, 1.1), a, b)
    assert not problems(sc)
    b["at"] = 0.3                                                           # now they overlap in time
    assert "bubble_covers_text" in kinds(LY.audit(sc))


def test_text_over_a_face_is_high_and_is_moved_off_the_head():
    sc = scene(char(960, 890, 1.2), text("NAPOLEON", 960, 560, 56))
    assert any(x["kind"] == "covers_face" and x["sev"] == "high" for x in LY.audit(sc))
    left, fixes, esc = LY.fix_scene(sc)
    assert not problems(sc) and not esc


def test_two_lines_of_one_card_are_a_pair_not_a_collision():
    card = {"type": "shape", "shape": "rect", "x": 960, "y": 425, "w": 820, "h": 210}
    sc = scene(card, text("NAPOLEON BONAPARTE", 960, 395, 56), text("FRENCH GENERAL", 960, 480, 46))
    assert not [x for x in LY.audit(sc) if x["kind"] in ("text_close", "text_overlap")]


def test_a_label_naming_its_own_prop_is_not_flagged_but_text_on_an_important_prop_is():
    sc = scene({"type": "prop", "name": "eiffel_tower", "x": 400, "y": 880, "scale": 1.2}, text("EIFFEL TOWER", 400, 330, 56))
    assert not [x for x in LY.audit(sc) if x["kind"] == "covers_prop"]
    doc = scene({"type": "prop", "name": "document", "x": 960, "y": 520, "scale": 2.4}, text("SOMETHING ELSE", 960, 500, 56))
    assert "covers_prop" in kinds(LY.audit(doc))


def test_a_bubble_tail_crossing_a_label_is_found_and_fixed():
    sc = scene(text("THE SURRENDER AT YORKTOWN", 960, 291, 62), char(700, 890, 1.15),
               bubble("It's over.", 400, 130, tail=[300, 250]))
    assert "tail_crosses" in kinds(LY.audit(sc))
    LY.fix_scene(sc)
    assert "tail_crosses" not in kinds(LY.audit(sc))


def test_a_ship_that_talks_is_a_valid_bubble_target_and_is_not_retargeted_to_a_far_character():
    sc = scene({"type": "prop", "name": "ship", "x": 400, "y": 800, "scale": 1.1}, char(1580, 760, 0.8),
               bubble("Trade with us or else.", 700, 320, tail=[-250, 120]))
    before = copy.deepcopy(sc["elements"][2])
    LY.fix_scene(sc)
    assert sc["elements"][2]["tail"] == before["tail"] or abs(sc["elements"][2]["tail"][0]) > 0
    _, tip = LY.bubble_geometry(sc["elements"][2])
    assert tip[0] < 1000                                                    # still points left, at the ship


# ---------------------------------------------------------------- 2. margins, caption zone, edges
def test_text_cut_off_by_the_frame_edge_is_high_and_moved_inside_the_safe_margin():
    sc = scene(text("THE TREATY OF VERSAILLES", 100, 300, 70), char(1000, 890, 1.1))
    assert any(x["kind"] == "edge" and x["sev"] == "high" for x in LY.audit(sc))
    LY.fix_scene(sc)
    b = element_bbox(sc["elements"][0])
    assert b[0] >= LY.MARGIN["text"] - 1 and not problems(sc)


def test_text_in_the_caption_area_moves_up():
    sc = scene(text("Look at this", 960, 1000, 60), char(400, 890, 1.0))
    assert "caption" in kinds(LY.audit(sc))
    LY.fix_scene(sc)
    assert element_bbox(sc["elements"][0])[3] <= LY.TEXT_BOTTOM + 2


def test_a_character_pushed_against_the_edge_is_flagged_and_a_peeking_host_is_not():
    assert any(x["kind"] in ("edge", "margin") for x in LY.audit(scene(char(1900, 890, 1.0))))
    host = char(1862, 905, 0.85, peek=True, flip=True)
    assert not [x for x in LY.audit(scene(host)) if x["kind"] in ("edge", "margin")]


# ---------------------------------------------------------------- 3. character size and hierarchy
def test_a_speaker_that_is_too_small_is_enlarged_and_stays_inside_the_frame():
    sc = scene(char(1800, 890, 0.45, say=["hello"]), bubble("hello", 1500, 450, tail=[200, 150]))
    assert "char_small" in kinds(LY.audit(sc))
    LY.fix_scene(sc)
    c = sc["elements"][0]
    assert c["scale"] >= LY.CHAR_MIN_SPEAKER - 0.01
    assert c["x"] + 115 * c["scale"] <= LY.W - LY.MARGIN["person"] + 2


def test_a_group_may_be_small_but_a_lone_character_may_not_dominate():
    group = scene(*[char(300 + 350 * k, 890, 0.45) for k in range(4)])
    assert "char_small" not in kinds(LY.audit(group))
    big = scene(char(960, 890, 1.8))
    assert "char_big" in kinds(LY.audit(big))
    LY.fix_scene(big)
    assert big["elements"][0]["scale"] <= LY.CHAR_MAX


def test_neighbours_on_the_same_ground_get_believable_proportions():
    sc = scene(char(500, 890, 1.4, who="A"), char(1500, 890, 0.6, who="B"))
    assert "scale_mismatch" in kinds(LY.audit(sc))
    LY.fix_scene(sc)
    a, b = (e["scale"] for e in sc["elements"])
    assert max(a, b) / min(a, b) <= LY.SCALE_RATIO + 0.02
    assert a > b                                                            # the main character stays the bigger one


def test_a_minor_object_that_outweighs_the_subject_shrinks_but_a_landmark_does_not():
    sc = scene(char(500, 890, 1.0, who="Napoleon"), {"type": "prop", "name": "ship", "x": 1400, "y": 900, "scale": 3.2})
    assert "hierarchy" in kinds(LY.audit(sc, dict(text="Napoleon spoke.")))
    LY.fix_scene(sc, dict(text="Napoleon spoke."))
    assert sc["elements"][1]["scale"] < 3.2
    city = scene(char(500, 890, 1.0), {"type": "prop", "name": "eiffel_tower", "x": 1400, "y": 900, "scale": 2.2})
    assert "hierarchy" not in kinds(LY.audit(city))


# ---------------------------------------------------------------- 4. bubbles
def test_a_bubble_that_points_at_nobody_is_aimed_at_the_nearest_speaker():
    sc = scene(char(1000, 890, 1.1), bubble("Hello.", 560, 300))            # default tail, aims at empty space
    assert any(x["kind"] == "tail_target" for x in LY.audit(sc))
    LY.fix_scene(sc)
    assert not [x for x in LY.audit(sc) if x["kind"] == "tail_target"]


def test_a_bubble_too_small_for_its_words_sizes_itself():
    sc = scene(char(700, 890, 1.1), bubble("This is quite a lot of words to fit in one bubble.", 700, 300, tail=[0, 120], w=200, h=80))
    assert "bubble_fit" in kinds(LY.audit(sc))
    LY.fix_scene(sc)
    assert "w" not in sc["elements"][1] and "bubble_fit" not in kinds(LY.audit(sc))


# ---------------------------------------------------------------- 5. camera
def test_a_close_up_that_cuts_a_label_in_half_is_eased_or_removed():
    sc = scene(text("Philadelphia, 1787", 960, 290), char(960, 890, 1.1),
               camera={"shots": [{"at": 0, "zoom": 1.0}, {"at": 0.4, "zoom": 1.6, "focus": [1100, 600]}]})
    assert LY.cropped(sc, 1.6, [1100, 600])
    LY.fix_scene(sc)
    assert sc["camera"]["shots"][1]["zoom"] < 1.6


def test_the_automatic_close_up_is_switched_off_when_it_would_crop_text():
    sc = scene(text("A WORD IN THE CORNER", 330, 330, 60), char(1500, 890, 1.0, say=["hi"]),
               bubble("hi", 1400, 420, tail=[60, 120]))
    LY.fix_scene(sc)
    cam = sc.get("camera") or {}
    assert cam.get("auto_shots") is False or not LY.cropped(sc, 1.5, (1500, 640))


# ---------------------------------------------------------------- 6. empty and lopsided
def test_everything_on_one_side_is_flagged_low_and_recentered_when_it_is_safe():
    sc = scene(char(240, 890, 1.1), {"type": "prop", "name": "document", "x": 520, "y": 560, "scale": 1.6})
    assert "balance" in {x["kind"] for x in LY.audit(sc)}
    LY.fix_scene(sc)
    assert sc["elements"][0]["x"] > 240


def test_a_scene_with_a_hidden_element_type_is_never_recentered_blindly():
    arrow = {"type": "arrow", "from": [1250, 300], "to": [1650, 300]}
    sc = scene(char(240, 890, 1.1), {"type": "prop", "name": "document", "x": 640, "y": 560, "scale": 1.2}, arrow)
    LY.fix_scene(sc)
    assert sc["elements"][0]["x"] == 240                                    # an arrow can't be shifted safely: nothing moved


# ---------------------------------------------------------------- the repair is safe and cheap
def random_scene(rng):
    els = []
    for _ in range(rng.randint(2, 7)):
        t = rng.choice(["text", "char", "prop", "bubble", "text"])
        x, y = rng.randint(120, 1800), rng.randint(120, 900)
        if t == "text":
            els.append(text(rng.choice(["Paris, 1789", "THE TREATY", "5,000 men", "Boom!"]), x, y, rng.choice([50, 60, 70])))
        elif t == "char":
            els.append(char(x, rng.randint(780, 920), rng.choice([0.5, 0.8, 1.0, 1.3]), who=rng.choice("ABC")))
        elif t == "prop":
            els.append({"type": "prop", "name": rng.choice(["document", "cannon", "trophy", "flag"]), "x": x, "y": y, "scale": rng.choice([0.8, 1.2, 2.0])})
        else:
            els.append(bubble(rng.choice(["Hello!", "What was that?", "I did not sign that."]), x, y, tail=[rng.randint(-100, 100), rng.randint(40, 160)]))
    return scene(*els)


def test_a_repair_never_adds_a_problem_and_never_raises_the_cost_fuzz():
    rng = random.Random(7)
    worse = 0
    for _ in range(150):
        sc = random_scene(rng)
        before = LY.findings(LY.build_items(sc), sc)
        c0, p0 = LY.total_cost(before), LY._problems(before)
        LY.fix_scene(sc)
        after = LY.findings(LY.build_items(sc), sc)
        assert LY._problems(after) <= p0 or all(k[0] == "camera" for k in LY._problems(after) - p0), (LY._problems(after) - p0)
        if LY.total_cost(after) > c0 + 1.0:
            worse += 1
    assert worse == 0


def test_a_second_repair_changes_nothing():
    rng = random.Random(3)
    for _ in range(60):
        sc = random_scene(rng)
        LY.fix_scene(sc)
        snap = copy.deepcopy(sc)
        _, fixes, _ = LY.fix_scene(sc)
        assert sc == snap and not fixes


def test_a_scene_that_cannot_be_rearranged_escalates_and_a_fixable_one_does_not():
    crowded = scene(*[text(f"LABEL NUMBER {k}", 960, 400, 96) for k in range(16)])
    left, fixes, esc = LY.fix_scene(crowded)
    assert esc and any(x["sev"] == "high" for x in left)
    ok = scene(text("Title", 960, 105), char(700, 890, 1.1))
    assert LY.fix_scene(ok)[2] is False


def test_a_clean_scene_is_left_exactly_as_it_was_and_scores_one():
    sc = scene(text("Paris, 1789", 960, 105, 76), char(700, 890, 1.15, who="Napoleon"), char(1300, 890, 0.95, who="Washington"))
    snap = copy.deepcopy(sc)
    left, fixes, esc = LY.fix_scene(sc)
    assert sc == snap and not fixes and LY.score(left) == 1.0 and not esc


# ---------------------------------------------------------------- the built-in patterns are laid out well from the start
def test_every_pattern_composes_without_layout_problems_and_needs_no_repair():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tk", os.path.join(os.path.dirname(__file__), "test_knowledge.py"))
    tk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tk)
    from studio.knowledge import analysis as AN, composer as CO, patterns as PT
    texts = {"TIMELINE": "From 1914 to 1918, then 1929 and 1939, the world kept falling apart.",
             "ELECTION": "In the election Lincoln won with 40 percent of the vote.", "STORY_MOMENT": "He kept losing at chess to a pigeon."}
    checked = 0
    for p in PT.load()["patterns"]:
        text_ = tk.SAMPLES.get(p["id"]) or texts.get(p["id"]) or "In 1789 in Paris Napoleon argued with Washington about 5,000 men and the Treaty of Paris."
        a = AN.analyze(text_, "fun", tk.CAST, set())
        sc = CO.compose(p, dict(mood="fun", text=text_), a, {}, CO.Ctx(cast=tk.CAST, idx=3))
        if sc is None:
            continue
        fixed, _, errs = check_scene(sc, "fun", text_, [], tk.CAST)
        assert not errs
        bad = problems(fixed, dict(text=text_))
        assert not bad, (p["id"], [x["msg"] for x in bad])
        snap = copy.deepcopy(fixed)
        _, fixes, _ = LY.fix_scene(fixed, dict(text=text_))
        assert not [f for f in fixes if "moved" in f or "scale" in f], (p["id"], fixes)
        checked += 1
    assert checked >= 25


# ---------------------------------------------------------------- the whole video
def test_every_title_in_a_video_gets_the_same_size_and_height():
    scenes = {k: scene(text("Paris, 1789", 960, 105, 70), char(700, 890, 1.1)) for k in range(4)}
    scenes[4] = scene(text("Vienna, 1815", 960, 125, 92), char(700, 890, 1.1))
    rows = LY.consistency(scenes)
    assert [r["beat"] for r in rows] == [4] and rows[0]["fixed"]
    t = scenes[4]["elements"][0]
    assert t["size"] == 70 and t["y"] == 105


def test_the_same_person_keeps_one_size_across_scenes_and_only_scenes_we_may_change_are_changed():
    scenes = {k: scene(char(700, 890, 1.1, who="Napoleon")) for k in range(4)}
    scenes[4] = scene(char(700, 890, 0.7, who="Napoleon"))
    rows = LY.consistency(scenes, only={0, 1})
    assert rows and not rows[0]["fixed"] and scenes[4]["elements"][0]["scale"] == 0.7
    rows = LY.consistency(scenes)
    assert rows[0]["fixed"] and scenes[4]["elements"][0]["scale"] == 1.1


# ---------------------------------------------------------------- the pipeline
@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "d"))
    cache.clear()
    yield
    cache.clear()


def test_the_storyboard_review_repairs_layout_and_reports_it(isolated):
    from studio.pipeline import review as RV
    sc = scene(text("Philadelphia, 1787", 960, 105), char(960, 890, 1.1), bubble("Hello there, everyone.", 960, 105, tail=[0, 200]))
    beats = [dict(mood="fun", text="Hello there, everyone, in Philadelphia in 1787.")]
    rep = RV.run({0: sc}, beats, [{}], registry=[])
    assert rep["layout"]["mean"] == 1.0 and not rep["layout"]["open"] and not rep["layout"]["escalate"]
    assert [x for x in rep["issues"] if x["check"] == "layout" and x["fixed"]]
    assert "layout" in rep["scores"]


def test_the_storyboard_review_lists_what_it_could_not_fix_and_flags_the_scene(isolated):
    from studio.pipeline import review as RV
    sc = scene(*[text(f"LABEL NUMBER {k}", 960, 400, 96) for k in range(16)])
    rep = RV.run({0: sc}, [dict(mood="fun", text="x")], [{}], registry=[])
    assert rep["layout"]["escalate"] == [0] and rep["layout"]["open"]
    assert [x for x in rep["issues"] if x["check"] == "layout" and not x["fixed"] and x["severity"] == "high"]


def test_rendering_repairs_scenes_first_saves_the_repair_and_blocks_what_cannot_be_fixed(isolated):
    from studio.pipeline import stages
    from studio.pipeline.project import new_project, write_json, read_json
    from studio.pipeline.runner import Ctx
    from studio import providers as P
    pr = new_project("Layout gate", "topic", topic="x", options=dict(minutes=1))
    beats = [dict(mood="fun", text="Hello there, everyone."), dict(mood="fun", text="Labels everywhere.")]
    os.makedirs(os.path.dirname(pr.scene_path(0)), exist_ok=True)
    write_json(pr.scene_path(0), scene(text("Philadelphia, 1787", 960, 105), char(960, 890, 1.1), bubble("Hello there, everyone.", 960, 105, tail=[0, 200])))
    write_json(pr.scene_path(1), scene(*[text(f"LABEL NUMBER {k}", 960, 400, 96) for k in range(16)]))
    left = stages.layout_prepare(Ctx(pr, "render"), pr, beats)
    assert 0 not in left and 1 in left                                       # scene 0 was repaired; scene 1 can't be
    saved = read_json(pr.scene_path(0))
    assert not problems(saved)                                               # the repair was written back with the scene
    with pytest.raises(P.ProviderError) as e:
        stages.layout_gate(left, [0, 1], {}, {})
    assert "scene 2" in str(e.value) and "layout" in str(e.value)
    stages.layout_gate(left, [0], {}, {})                                    # a fine scene renders
    stages.layout_gate(left, [0, 1], {"allow_layout_issues": True}, {})
    stages.layout_gate(left, [0, 1], {}, {"layout_gate": "warn"})


def test_the_hosts_cameo_is_dropped_when_it_would_land_on_something():
    from studio.pipeline import stages
    beats = [dict(mood="fun", text="and then WHAT happened next")]
    clear = scene(text("Title", 960, 105), char(500, 890, 1.0))
    settings = {}
    with_cameo = stages.as_rendered(clear, 0, beats, settings, plan={0: ("WHAT", "surprise")}, opts={})
    assert len(with_cameo["elements"]) > len(clear["elements"])             # nothing in the way: the cameo is there
    busy = scene(text("Title", 960, 105), char(1560, 890, 1.1), bubble("Big news!", 1660, 450, tail=[120, 56]))
    without = stages.as_rendered(busy, 0, beats, settings, plan={0: ("WHAT", "surprise")}, opts={})
    assert len(without["elements"]) == len(busy["elements"])                # the cameo would have landed on a character
