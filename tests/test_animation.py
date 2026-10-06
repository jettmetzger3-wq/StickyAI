"""Animated stickmen, camera shots, crowds, pointers and painted backgrounds."""
from studio.engine.puppet import Puppet, resolve_action
from studio.engine.compiler import build_scene
from studio.engine.schema import check_scene
from studio.engine.core import Scene

TEXT = "Napoleon gave a speech and the soldiers cheered loudly for him."


def test_walk_jump_talk_and_faint_change_the_pose():
    p = Puppet(400, 900, 1.0, {"kind": "france"}, actions=[
        dict(act="walk", t0=0.0, dur=2.0, dx=500, dy=0), dict(act="jump", t0=2.5, dur=0.6),
        dict(act="faint", t0=4.0, dur=0.5)], talk=[(3.2, 3.8)], seed=1)
    _, dx_mid, _, _ = p.state(1.0)
    _, dx_end, _, _ = p.state(2.2)
    assert 100 < dx_mid < 500 and abs(dx_end - 500) < 1
    _, _, dy_air, _ = p.state(2.8)
    assert dy_air < -80                                   # in the air
    mouths = {p.state(3.2 + k / 30)[0]["mouth"] for k in range(15)}
    assert len(mouths) > 1                                # the mouth moves while talking
    pose, _, _, rot = p.state(5.0)
    assert abs(rot) > 80 and pose["eyes"] == "dead"       # fainted and stays down


def test_life_blinks_and_glances_without_any_actions():
    p = Puppet(960, 900, 1.0, {"kind": "civ"}, seed=3)
    states = [p.state(k / 30)[0] for k in range(30 * 12)]
    assert any(s["blink"] for s in states)
    assert {s.get("look") for s in states} - {None, 0}
    img, off = p.image(states[0], "civ", 1)
    assert img is not None and img.width > 50


def test_action_names_are_forgiving():
    assert resolve_action("Walks") == "walk" and resolve_action("no") == "shake_head"
    assert resolve_action("moonwalk") is None


def test_scene_with_crowd_pointer_shots_and_talking():
    scene = {"bg": {"type": "field", "time": "dusk"}, "elements": [
        {"type": "crowd", "kind": "shako", "count": 9, "rows": 2, "x": 1200, "y": 930, "width": 900, "scale": 0.55,
         "do": [{"act": "cheer", "at": "word:cheered"}]},
        {"type": "char", "kind": "bicorne", "x": 400, "y": 900, "pose": "wave"},
        {"type": "bubble", "text": "Glory!", "x": 520, "y": 330, "tail": "left", "at": 0.2},
        {"type": "pointer", "x": 400, "y": 520, "from": "ne", "at": 0.5}],
        "camera": {"shots": [{"at": "word:speech", "zoom": 1.6, "focus": [400, 560], "move": "cut"},
                             {"at": "word:cheered", "zoom": 1.2, "focus": [1200, 700], "move": "whip"}]}}
    fixed, fixes, errs = check_scene(scene, "fun", TEXT)
    assert not errs, errs
    sc = build_scene(fixed, 1, 6.0, "fun", TEXT)
    puppets = [L for L in sc.layers if L.get("puppet")]
    assert len(puppets) == 10
    napoleon = puppets[-1]["puppet"]
    assert napoleon.talk and any(a["act"] == "wave" for a in napoleon.actions)   # bubble -> talks; wave pose -> waves
    assert any(L.get("nudge") for L in sc.layers)
    assert [s["move"] for s in sc.shots] == ["cut", "whip"]
    for t in (0.5, 2.0, 4.6, 5.5):
        assert sc.render_at(t).size == (1920, 1080)


def test_repairs_for_the_new_features():
    scene = {"bg": {"type": "feild", "time": "sunset"}, "elements": [
        {"type": "char", "kind": "civ", "x": 900, "y": 900, "do": ["moonwalk", {"act": "cheer", "at": 0.5}]},
        {"type": "army", "kind": "napoleonic", "count": 99, "x": 5000, "y": 900},
        {"type": "pointer", "x": 500, "y": 500, "from": "upper right"}],
        "camera": {"shots": [{"at": 0.3, "zoom": 9, "center": [500, 500], "move": "zoom"}]}}
    fixed, fixes, errs = check_scene(scene, "somber", "A sad day.")
    assert not errs, errs
    assert fixed["bg"]["type"] == "field" and fixed["bg"]["time"] in ("day", "dawn", "dusk", "night", "storm")
    char = fixed["elements"][0]
    assert char["do"] == []                               # unknown action dropped, cheering dropped (somber)
    crowd = fixed["elements"][1]
    assert crowd["type"] == "crowd" and crowd["count"] == 40 and crowd["x"] < 1920
    assert fixed["elements"][2]["from"] in ("n", "s", "e", "w", "ne", "nw", "se", "sw")
    shot = fixed["camera"]["shots"][0]
    assert shot["zoom"] == 2.2 and shot["focus"] == [500, 500] and shot["move"] in ("cut", "pan", "whip")


def test_every_painted_background_renders():
    for name in ("field", "hills", "desert", "snow", "city", "interior", "battlefield"):
        sc = Scene(1, 3.0, "fun", "x")
        if name == "interior":
            sc.bg_interior()
        else:
            getattr(sc, f"bg_{name}")("night" if name == "city" else "day")
        assert sc.bg.size == (1920, 1080)


def test_dark_map_scene():
    scene = {"bg": {"type": "map", "style": "dark", "center": [10, 47], "width": 30,
                    "territories": [{"countries": ["France"], "color": "#3b5bd6"}]},
             "elements": [{"type": "city", "name": "Vienna", "lon": 16.37, "lat": 48.2, "at": 0.2},
                          {"type": "text", "text": "1796", "x": 960, "y": 120, "at": 0}]}
    fixed, fixes, errs = check_scene(scene, "fun", "In 1796 the French marched on Vienna.")
    assert not errs
    assert fixed["elements"][1]["color"] == "#EBEBF5"     # text turns light on a dark map
    sc = build_scene(fixed, 2, 4.0, "fun", "In 1796 the French marched on Vienna.")
    assert sc.render_at(2.0).size == (1920, 1080)
