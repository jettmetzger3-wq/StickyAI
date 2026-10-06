import json
import os

from studio.engine import check_scene, validate_scene, build_scene, WordTimer, SCENE_SCHEMA
from studio.engine.schema import element_bbox, camera_safe_rect
from studio.engine.captions import CAPTION_ZONE

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, "..", "studio", "prompts", "examples.json")


def test_schema_is_valid_json_schema():
    import jsonschema
    jsonschema.Draft7Validator.check_schema(SCENE_SCHEMA)


def test_all_examples_validate_and_compile_without_fixes():
    ex = json.load(open(EXAMPLES))
    assert 10 <= len(ex) <= 24
    for i, e in enumerate(ex):
        fixed, fixes, errs = check_scene(e["scene"], e["mood"], e["text"])
        assert errs == [], (e["name"], errs)
        assert fixes == [], (e["name"], fixes)
        sc = build_scene(fixed, i, 8.0, e["mood"], e["text"])
        assert sc.bg is not None
        assert len(sc.layers) >= 3, e["name"]
        assert sc.warnings == [], (e["name"], sc.warnings)


def test_repair_fixes_common_llm_mistakes():
    bad = {
        "bg": {"type": "sunbursts"},
        "elements": [
            {"type": "label", "text": "HELLO", "x": 960, "y": 1050, "size": 80},           # alias + caption zone
            {"type": "character", "kind": "usa", "pose": "celebrate", "mouth": "big smile", "x": 2500, "y": 900},
            {"type": "prop", "name": "battleship", "x": 960, "y": 700},                     # prop alias
            {"type": "prop", "name": "unicorn", "x": 100, "y": 100},                        # unknown -> dropped
            {"type": "territory", "countries": ["Japan"]},                                   # map-only -> dropped
            {"type": "text", "text": "x", "enter": "slide_r", "at": "Britain"},
        ],
    }
    fixed, fixes, errs = check_scene(bad, "fun", "Britain says hello")
    assert errs == []
    types = [e["type"] for e in fixed["elements"]]
    assert types == ["text", "char", "prop", "text"]
    assert fixed["bg"]["type"] == "sunburst"
    txt = fixed["elements"][0]
    assert element_bbox(txt)[3] <= 1080 - CAPTION_ZONE
    ch = fixed["elements"][1]
    assert ch["pose"] == "cheer" and ch["mouth"] in ("smile", "grin")
    assert element_bbox(ch)[2] <= 1920
    assert fixed["elements"][2]["name"] == "ship"
    assert fixed["elements"][3]["enter"] == "slide_right"
    assert fixed["elements"][3]["at"] == "word:Britain"


def test_somber_rules():
    sc = {"bg": {"type": "sunburst"}, "elements": [
        {"type": "char", "kind": "civ", "x": 500, "y": 900, "mouth": "grin", "eyes": "dead", "enter": "pop"},
        {"type": "text", "text": "1945", "x": 960, "y": 200, "idle": "shake", "sfx": "pop"}]}
    fixed, fixes, errs = check_scene(sc, "somber", "")
    assert fixed["bg"]["type"] == "dark"
    c, t = fixed["elements"]
    assert c["mouth"] == "flat" and c["eyes"] == "closed" and c["enter"] == "fade"
    assert t["idle"] == "none" and t["sfx"] == "none" and t["enter"] == "fade"


def test_camera_zoom_keeps_text_visible():
    sc = {"bg": {"type": "paper"}, "camera": {"zoom": [1.0, 1.1], "center": [960, 540]},
          "elements": [{"type": "text", "text": "EDGE", "x": 40, "y": 30, "size": 60}]}
    fixed, fixes, errs = check_scene(sc, "fun", "")
    safe = camera_safe_rect(fixed["camera"])
    bb = element_bbox(fixed["elements"][0])
    assert bb[0] >= safe[0] - 1 and bb[1] >= safe[1] - 1


def test_map_lonlat_offscreen_converted():
    sc = {"bg": {"type": "map", "center": [14, 41], "width": 80},
          "elements": [{"type": "text", "text": "Far away", "lon": 14, "lat": 10, "size": 50}]}
    fixed, fixes, errs = check_scene(sc, "fun", "")
    el = fixed["elements"][0]
    assert "lon" not in el and el["y"] <= 1080 - CAPTION_ZONE


def test_validate_reports_bad_enums():
    errs = validate_scene({"bg": {"type": "spaceship"}, "elements": [{"type": "char", "mouth": "laugh"}]})
    assert any("spaceship" in e for e in errs)
    assert any("laugh" in e for e in errs)


def test_word_trigger_resolution():
    t = WordTimer("Japan declares war on Britain and the Dutch.", 5.0)
    f = t.resolve("word:Britain")
    assert 0.3 < f < 0.8
    assert t.resolve("word:Dutch") > f
    assert t.resolve("word:Britain+0.5") > f
    assert t.resolve(0.25) == 0.25
    assert t.resolve("word:zebra", default=0.1) == 0.1
