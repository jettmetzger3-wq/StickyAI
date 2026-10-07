"""Props, places, topic kits, custom props and dialogue."""
import json

import pytest

from studio.engine.compiler import build_scene, talk_windows
from studio.engine.custom_props import clean_kit, custom_bounds, draw_custom, to_element_params
from studio.engine.pen import Pen, HATS, KIND_ALIASES
from studio.engine.places import SKYLINES, PAINTERS, skyline_key
from studio.engine.registry import PROPS, PROP_ALIASES, PROP_GROUPS, guess_prop, prop_bounds, resolve_prop
from studio.engine.schema import check_scene, element_bbox, BG_TYPES, overlaps
from studio.pipeline import rules, themes as TH

DESIGNS = {"props": [
    {"name": "Rosetta Stone", "anchor": "bottom", "description": "the Rosetta Stone",
     "parts": [{"shape": "poly", "points": [[18, 100], [82, 100], [86, 30], [60, 8], [20, 20]], "fill": "#5A5A66"},
               {"shape": "line", "points": [[26, 40], [74, 38]], "color": "silver", "width": 1.5},
               {"shape": "text", "text": "ΑΒΓ", "x": 50, "y": 70, "size": 10, "color": "white"}]},
    {"name": "spitfire", "anchor": "center", "description": "Spitfire",
     "parts": [{"shape": "ellipse", "x": 50, "y": 52, "rx": 40, "ry": 8, "fill": "olive"},
               {"shape": "circle", "x": 50, "y": 60, "r": 6, "fill": "navy"}]},
    {"name": "eiffel_tower", "parts": [{"shape": "rect", "x": 0, "y": 0, "w": 9, "h": 9, "fill": "red"}] * 2},
    {"name": "junk", "parts": [{"shape": "blob"}, {"shape": "poly", "points": [[1, 1]]}]},
    "not a design",
]}


def test_every_prop_draws_and_has_bounds():
    assert len(PROPS) > 200
    for name, (anchor, fn, desc) in PROPS.items():
        if name == "custom":
            continue
        assert anchor in ("bottom", "center") and desc
        for s in (0.4, 1.0):
            p = Pen(1, rgba=True, size=(900, 900))
            fn(p, 450, 700 if anchor == "bottom" else 450, s * 0.5, None, {})
            assert p.im.getchannel("A").getbbox(), name
        x0, y0, x1, y1 = prop_bounds(name)
        assert x1 > x0 and y1 > y0, name


def test_groups_and_aliases_cover_the_library():
    grouped = {n for _, ns in PROP_GROUPS for n in ns}
    assert grouped == set(PROPS) - {"custom"}
    assert all(v in PROPS for v in PROP_ALIASES.values())
    assert resolve_prop("Eiffel Tower") == "eiffel_tower" and resolve_prop("U-boat") == "submarine"


def test_prop_guessing_is_careful():
    assert guess_prop("british_warship") == "ship"
    assert guess_prop("gold coin") == "coin"
    assert guess_prop("eifel tower") == "eiffel_tower"
    assert guess_prop("unicorn") is None
    assert guess_prop("napoleon") is None


def test_props_take_flip_and_params():
    for name, k in (("shark", {"flip": True}), ("galleon", {"pirate": True, "flag": "red"}),
                    ("newspaper", {"label": "WAR!"}), ("lighthouse", {"lit": False}), ("chess_piece", {"piece": "knight"}),
                    ("satellite", {"style": "modern"}), ("volcano", {"erupting": False})):
        p = Pen(1, rgba=True, size=(900, 900))
        PROPS[name][1](p, 450, 600, 0.6, None, k)
        assert p.im.getchannel("A").getbbox()


def test_new_backgrounds_build_and_render():
    for t in ("street", "palace", "harbor", "beach", "underwater", "space", "jungle", "mountains", "trench"):
        assert t in BG_TYPES and t in PAINTERS
    for bg in ({"type": "street", "style": "western"}, {"type": "street", "style": "asia", "time": "night"},
               {"type": "underwater"}, {"type": "city", "skyline": "Paris"}, {"type": "city", "skyline": "new york"},
               {"type": "palace", "wall": "#DDE6EE"}):
        fixed, fixes, errs = check_scene({"bg": bg, "elements": [{"type": "text", "text": "HI", "x": 960, "y": 200}]})
        assert not errs and not fixes, (bg, fixes, errs)
        sc = build_scene(fixed, 1, 2.0, "fun", "x")
        assert sc.render_at(1.0).size == (1920, 1080)
    assert skyline_key("Constantinople") == "istanbul" and skyline_key("Atlantis") is None
    for city, items in SKYLINES.items():
        assert all(n in PROPS for n, _, _ in items), city


def test_background_aliases_and_text_on_dark_places():
    fixed, fixes, _ = check_scene({"bg": {"type": "throne room"}, "elements": []})
    assert fixed["bg"]["type"] == "palace"
    fixed, _, _ = check_scene({"bg": {"type": "city", "skyline": "Gotham"}, "elements": []})
    assert "skyline" not in fixed["bg"]
    fixed, _, _ = check_scene({"bg": {"type": "space"}, "elements": [{"type": "text", "text": "1969", "x": 960, "y": 200}]})
    assert fixed["elements"][0]["color"] == "#EBEBF5"
    fixed, _, _ = check_scene({"bg": {"type": "street", "style": "wild west"}, "elements": []})
    assert fixed["bg"]["style"] == "western"


# ------------------------------------------------------------------ custom props
def test_custom_prop_designs_are_cleaned():
    kit = clean_kit(DESIGNS, PROPS)
    assert [d["name"] for d in kit] == ["rosetta_stone", "spitfire"]     # library names and junk are dropped
    stone = kit[0]
    assert stone["anchor"] == "bottom" and len(stone["parts"]) == 3
    b = custom_bounds(to_element_params(stone))
    assert b[3] > 0 >= b[1] - 1 and b[2] > b[0]
    p = Pen(1, rgba=True, size=(600, 600))
    draw_custom(p, 300, 500, 1.0, None, to_element_params(stone))
    assert p.im.getchannel("A").getbbox()


def test_scenes_use_custom_props_by_name():
    kit = clean_kit(DESIGNS, PROPS)
    scene = {"bg": {"type": "palace"}, "elements": [
        {"type": "prop", "name": "Rosetta stone", "x": 700, "y": 880},
        {"type": "icons", "icon": "spitfire", "count": 5, "x": 960, "y": 400, "scale": 0.3},
        {"type": "prop", "name": "custom", "params": {"parts": [{"shape": "circle", "x": 50, "y": 50, "r": 9}]}},
        {"type": "prop", "name": "rosetta stone", "x": 1300, "y": 880}]}
    fixed, fixes, errs = check_scene(scene, "fun", "x", kit)
    assert not errs
    props = [e for e in fixed["elements"] if e["type"] == "prop"]
    assert len(props) == 2 and all(e["name"] == "custom" and e["params"]["design"] == "rosetta_stone" for e in props)
    assert any("without shapes" in f for f in fixes)
    icons = next(e for e in fixed["elements"] if e["type"] == "icons")
    assert icons["icon"] == "custom" and icons["params"]["anchor"] == "center"
    sc = build_scene(fixed, 0, 3.0, "fun", "x")
    assert sc.warnings == [] and sc.render_at(2.0).size == (1920, 1080)
    # without the kit the same name is simply unknown
    fixed2, fixes2, _ = check_scene(scene, "fun", "x")
    assert not any(e.get("name") == "custom" for e in fixed2["elements"] if e["type"] == "prop")


# ------------------------------------------------------------------ topic kits
def test_theme_kits_are_valid():
    for key, th in TH.THEMES.items():
        assert th["label"] and th["words"] and th["lines"]
        assert all(p in PROPS for p in th["props"]), key
        assert all(k in HATS or k in KIND_ALIASES for k in th["kinds"]), key
        for bg in th["places"]:
            fixed, fixes, errs = check_scene({"bg": dict(bg), "elements": []})
            assert not errs and not fixes, (key, bg)


def test_detect_themes():
    assert TH.detect("Napoleon's Invasion of Russia", "Napoleon", [{"text": "The army marched to Moscow in 1812."}])[:2] \
        == ["france", "russia"]
    assert TH.detect("The Golden Age of Pirates", "pirates", [{"text": "Pirates ruled the Caribbean sea."}])[0] == "sea"
    assert TH.detect("Untitled", "", [{"text": "Something happened."}]) == []
    block = TH.kit_block(["france", "sea"])
    assert '"skyline":"paris"' in block and "galleon" in block and "Vive" in block
    assert TH.beat_themes("They sailed from Paris to the open ocean", ["russia"])[:2] in (["sea", "france"], ["france", "sea"])


def test_variety_pass_changes_only_new_repeats():
    scenes = {0: {"bg": {"type": "paper"}}, 1: {"bg": {"type": "paper"}}, 2: {"bg": {"type": "field"}},
              3: {"bg": {"type": "field"}}, 4: {"bg": {"type": "field"}}, 5: {"bg": {"type": "map", "center": [0, 0]}},
              6: {"bg": {"type": "map", "center": [0, 0]}}}
    changes = TH.vary(scenes, list(range(7)), editable={1, 4, 6})
    changed = {i for i, _ in changes}
    assert changed == {1, 4}
    assert scenes[1]["bg"]["color"] != scenes[0]["bg"].get("color")
    assert scenes[3]["bg"].get("time") is None and scenes[4]["bg"]["time"] == "dusk"


# ------------------------------------------------------------------ dialogue
def _bubbles(fixed):
    return [e for e in fixed["elements"] if e["type"] == "bubble"]


def test_say_lines_become_bubbles_over_the_speaker():
    scene = {"bg": {"type": "field"}, "elements": [
        {"type": "text", "text": "Italy, 1796", "x": 960, "y": 110, "size": 76},
        {"type": "crowd", "kind": "shako", "x": 1250, "y": 930, "count": 12, "rows": 2, "flip": True,
         "say": [{"text": "Vive l'Empereur!", "at": 0.7}]},
        {"type": "char", "kind": "bicorne", "x": 420, "y": 900,
         "say": ["Soldiers! Forty centuries look down upon you!", {"text": "CHARGE!", "at": "word:charge"}]}]}
    text = "Napoleon motivated his men, and then they charge."
    fixed, fixes, errs = check_scene(scene, "fun", text)
    assert not errs and not fixes
    b = _bubbles(fixed)
    assert len(b) == 3
    assert all("say" not in e for e in fixed["elements"])
    speech = [x for x in b if x["at"] != 0.7]
    assert speech[0]["exit"] == "word:charge" and speech[1]["at"] == "word:charge"
    title = element_bbox(fixed["elements"][0])
    for x in b:
        bb = element_bbox(x)
        assert bb[0] >= 0 and bb[2] <= 1920 and bb[1] >= 0 and bb[3] <= 900
        assert not overlaps(bb, title)
    sc = build_scene(fixed, 0, 6.0, "fun", text)
    talk = talk_windows(sc, fixed["elements"])
    nap = next(i for i, e in enumerate(fixed["elements"]) if e.get("kind") == "bicorne")
    assert nap in talk and len(talk[nap]) == 2
    assert sc.render_at(4.0).size == (1920, 1080)


def test_somber_say_lines_fade_in():
    fixed, _, errs = check_scene({"bg": {"type": "dark"}, "elements": [
        {"type": "char", "kind": "civ", "x": 960, "y": 900, "say": ["We will remember."]}]}, "somber", "x")
    assert not errs and _bubbles(fixed)[0]["enter"] == "fade"


def test_dialogue_is_added_when_someone_speaks():
    cast = [{"name": "Napoleon", "kind": "bicorne"}]
    scene = {"bg": {"type": "field"}, "elements": [
        {"type": "char", "kind": "civ", "x": 1500, "y": 900, "scale": 1.3},
        {"type": "char", "kind": "bicorne", "x": 400, "y": 900},
        {"type": "crowd", "kind": "shako", "x": 1100, "y": 930}]}
    assert TH.ensure_dialogue(scene, "Napoleon motivated his men before the battle.", "fun", cast, ["france"], 1)
    nap = scene["elements"][1]
    assert nap["say"] and scene["elements"][2]["say"][0]["text"]
    assert "say" not in scene["elements"][0]
    # nobody speaks in the narration -> nothing added; existing bubbles are respected
    s2 = {"elements": [{"type": "char", "kind": "civ"}]}
    assert not TH.ensure_dialogue(s2, "The harvest was poor that year.", "fun")
    s3 = {"elements": [{"type": "char", "kind": "civ"}, {"type": "bubble", "text": "hi"}]}
    assert not TH.ensure_dialogue(s3, "He said hello.", "fun")
    assert TH.line_for("Thousands were killed when the army attacked.", "somber") is None


@pytest.mark.parametrize("mood,text", [
    ("fun", "Napoleon motivated his men before crossing the Alps in 1800."),
    ("tense", "Britain refused to sign, and its navy blocked every French port."),
    ("somber", "Hundreds of thousands died in the Russian winter."),
    ("fun", "Paris threw him a huge party with wine and cheese."),
    ("fun", "The pirates buried their treasure on an island."),
])
def test_rule_scenes_follow_the_topic(mood, text):
    cast = [{"name": "Napoleon", "kind": "bicorne"}, {"name": "Britain", "kind": "britain"}]
    vt = TH.detect("Napoleon and the sea", "Napoleon", [{"text": text}])
    sc = rules.rule_scene({"text": text, "mood": mood}, 3, cast, vt)
    fixed, fixes, errs = check_scene(sc, mood, text)
    assert not errs and fixed["elements"]
    if mood != "somber":
        assert fixed["bg"]["type"] not in ("paper", "sunburst")      # a themed place, not a blank page


def test_examples_show_the_new_features():
    from studio.prompts import load_examples, scene_language
    ex = load_examples()
    blob = json.dumps(ex)
    assert '"say"' in blob and '"harbor"' in blob and '"underwater"' in blob and '"street"' in blob
    doc = scene_language()
    assert "DIALOGUE" in doc and "eiffel_tower" in doc and "skyline" in doc and "CUSTOM PROPS" in doc


def test_storyboard_stage_uses_kit_custom_props_and_dialogue(monkeypatch):
    """The storyboard step with a stand-in writer: designs props once, uses them, adds dialogue, varies repeats."""
    from studio import providers as P
    from studio.pipeline import new_project, stages
    from studio.pipeline.runner import Ctx

    calls = []

    class FakeLLM:
        id, label, paid, supports_images = "fake", "Fake writer", False, False

        def available(self):
            return True, ""

        def complete(self, system, prompt, schema=None, images=(), label="", **kw):
            calls.append(label)
            if label == "props":
                return json.dumps(DESIGNS), {}
            scene = lambda els: {"bg": {"type": "field"}, "elements": els}
            return json.dumps({"scenes": [
                {"beat": 0, "scene": scene([{"type": "char", "kind": "bicorne", "x": 400, "y": 900},
                                            {"type": "crowd", "kind": "shako", "x": 1200, "y": 930}])},
                {"beat": 1, "scene": scene([{"type": "prop", "name": "rosetta stone", "x": 900, "y": 880}])},
                {"beat": 2, "scene": {"bg": {"type": "paper"}, "elements": [{"type": "text", "text": "x", "x": 960, "y": 300}]}},
            ]}), {}

    monkeypatch.setattr(stages, "provider", lambda meta, stage, ctx=None, task=None: FakeLLM())
    monkeypatch.setattr(stages, "render_previews", lambda *a, **k: None)
    pr = new_project("Napoleon in Egypt", "topic", topic="Napoleon in Egypt", options={"minutes": 1, "storyboard_engine": "classic"})
    pr.save_script({"title": "Napoleon in Egypt", "topic": "Napoleon", "cast": [{"name": "Napoleon", "kind": "bicorne"}],
                    "beats": [{"mood": "fun", "text": "Napoleon motivated his men under the pyramids."},
                              {"mood": "fun", "text": "His scholars found the Rosetta Stone near the Nile."},
                              {"mood": "fun", "text": "Then the British fleet showed up."}]})
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    assert calls.count("props") == 1
    assert [d["name"] for d in pr.prop_kit()] == ["rosetta_stone", "spitfire"]
    s0, s1, s2 = (json.load(open(pr.scene_path(i))) for i in range(3))
    assert any(e["type"] == "bubble" for e in s0["elements"])             # Napoleon got a line, the crowd answers
    assert s1["elements"][0]["name"] == "custom"
    assert s1["bg"].get("time") == "dusk"                               # same field twice in a row -> varied
    sb = json.load(open(pr.p("storyboard.json")))
    assert "egypt" in sb["themes"] and "france" in sb["themes"]
    # a second run reuses the designed props instead of asking again
    stages.stage_storyboard(Ctx(pr, "storyboard"), force=True)
    assert calls.count("props") == 1
