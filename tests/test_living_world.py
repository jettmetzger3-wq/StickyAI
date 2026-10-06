"""Weather and light, action moments, living maps, charts and timelines, music styles and stings, mood narration,
and the AI-facing docs that teach them."""
import json

import numpy as np

from studio.engine.compiler import build_scene
from studio.engine.schema import check_scene


def scene(sc_json, mood="fun", text="x", dur=5.0, idx=0):
    fixed, fixes, errs = check_scene(sc_json, mood, text)
    assert errs == [], errs
    return build_scene(fixed, idx, dur, mood, text), fixed, fixes


def differ(a, b):
    return np.abs(np.asarray(a.convert("RGB"), dtype=np.int16) - np.asarray(b.convert("RGB"), dtype=np.int16)).mean()


# ------------------------------------------------------------------ weather and light
def test_weather_from_the_narration_and_not_indoors():
    _, s, fixes = scene({"bg": {"type": "snow"}, "elements": []}, "tense", "The army froze in the Russian winter.")
    assert s["weather"]["type"] == "snow" and any("snow" in f for f in fixes)
    _, s, _ = scene({"bg": {"type": "field", "time": "storm"}, "elements": []}, "tense", "A thunderstorm broke out.")
    assert s["weather"]["type"] == "storm"
    _, s, fixes = scene({"bg": {"type": "interior"}, "weather": "rain", "elements": []})
    assert "weather" not in s and any("indoors" in f for f in fixes)
    _, s, _ = scene({"bg": {"type": "harbor"}, "elements": []}, "fun", "He tied burning fuses into his beard.")
    assert "weather" not in s                                   # a burning beard is not a burning city


def test_snow_storm_and_nightfall_change_the_frames():
    plain, _, _ = scene({"bg": {"type": "hills"}, "elements": []})
    snowy, _, _ = scene({"bg": {"type": "hills"}, "weather": "snow", "elements": []})
    assert differ(plain.render_at(2.0), snowy.render_at(2.0)) > 0.3
    a, b = snowy.render_at(1.0), snowy.render_at(1.5)            # flakes fall
    assert differ(a, b) > 0.1
    storm, _, _ = scene({"bg": {"type": "battlefield"}, "weather": "storm", "elements": []}, "tense")
    assert any(k == "thunder" for _, k in storm.sfx)
    night, s, _ = scene({"bg": {"type": "city"}, "light": "nightfall", "elements": []})
    assert s["light"]["to"] == "night"
    early, late = np.asarray(night.render_at(0.1)).mean(), np.asarray(night.render_at(4.9)).mean()
    assert late < early - 20                                    # night fell during the scene


def test_weather_has_its_own_ambience():
    from studio.engine.audio import ambience_kind, make_ambience
    assert ambience_kind({"bg": {"type": "field"}, "weather": {"type": "rain"}}) == "rain"
    assert ambience_kind({"bg": {"type": "field"}, "weather": "storm"}) == "storm"
    assert len(make_ambience("rain", 4.0)) > 0


# ------------------------------------------------------------------ action moments
def test_props_fire_sink_collapse_and_explode():
    sc, s, _ = scene({"bg": {"type": "battlefield"}, "elements": [
        {"type": "prop", "name": "cannon", "x": 400, "y": 900, "do": [{"act": "shoot", "at": 0.2, "target": [1500, 800]}]},
        {"type": "prop", "name": "castle", "x": 1500, "y": 880, "do": [{"act": "crumble", "at": 0.4}]}]}, "tense")
    assert s["elements"][0]["do"][0]["act"] == "fire" and s["elements"][1]["do"][0]["act"] == "collapse"
    kinds = [k for _, k in sc.sfx]
    assert kinds.count("boom") >= 2 and "rumble" in kinds       # the shot and the cannonball landing
    before, after = sc.render_at(0.5), sc.render_at(4.8)
    assert differ(before, after) > 1.0                          # the castle is rubble now
    sea, _, _ = scene({"bg": {"type": "sea"}, "elements": [{"type": "prop", "name": "galleon", "x": 960, "y": 700,
                                                            "scale": 0.7, "do": [{"act": "sink", "at": 0.1}]}]}, "tense")
    assert "splash" in [k for _, k in sea.sfx]
    assert differ(sea.render_at(0.4), sea.render_at(4.9)) > 1.0


def test_explosion_prop_bursts_and_somber_scenes_do_not_explode():
    sc, _, _ = scene({"bg": {"type": "paper"}, "elements": [{"type": "prop", "name": "explosion", "x": 960, "y": 480}]})
    assert "boom" in [k for _, k in sc.sfx]
    _, s, fixes = scene({"bg": {"type": "dark"}, "elements": [{"type": "prop", "name": "tank", "x": 960, "y": 880,
                                                               "do": [{"act": "explode"}]}]}, "somber")
    assert "do" not in s["elements"][0] and any("explode" in f for f in fixes)


def test_sword_duel_clashes():
    sc, s, _ = scene({"bg": {"type": "field"}, "elements": [
        {"type": "char", "kind": "knight", "x": 800, "y": 900, "prop": "sword", "do": [{"act": "duel", "dur": 2}]},
        {"type": "char", "kind": "samurai", "x": 1120, "y": 900, "flip": True, "prop": "sword",
         "do": [{"act": "slash", "dur": 2}]}]})
    assert s["elements"][0]["do"][0]["act"] == "slash"
    assert sum(1 for _, k in sc.sfx if k == "clang") >= 3


def test_sword_follows_the_arm():
    from studio.engine.pen import Pen
    up, out = Pen(1, rgba=True, size=(700, 900)), Pen(1, rgba=True, size=(700, 900))
    up.stick(350, 860, 1.0, "civ", arms="down", prop="sword", shadow=False)
    out.stick(350, 860, 1.0, "civ", arms=((45, -60), (88, -14)), prop="sword", shadow=False)
    assert out.im.getbbox()[2] > up.im.getbbox()[2] + 100        # thrust forward, the blade reaches much further


# ------------------------------------------------------------------ living maps
EUROPE = {"type": "map", "center": [14, 41], "width": 60, "style": "dark"}


def test_empire_grows_with_the_year_ticking():
    sc, s, _ = scene({"bg": EUROPE, "elements": [
        {"type": "empire", "name": "ROME", "steps": [{"at": 0.05, "year": -264, "countries": ["Italy"]},
                                                     {"at": 0.5, "year": 117, "region": "roman_empire_117"}]},
        {"type": "city", "name": "Rome", "lon": 12.5, "lat": 41.9, "capital": True}]})
    assert s["elements"][0]["steps"][0]["year"] == -264
    from studio.engine.livemap import YearLabel
    years = [L["dyn"].__self__ for L in sc.layers if L.get("dyn") is not None and isinstance(getattr(L["dyn"], "__self__", None), YearLabel)]
    assert years and years[0].year_at(0.1) == -264 and years[0].year_at(4.9) == 117
    assert differ(sc.render_at(1.0), sc.render_at(4.9)) > 2.0     # much more red at the end


def test_route_draws_itself_and_lon_lat_lists_are_read_as_coordinates():
    sc, s, fixes = scene({"bg": {"type": "map", "center": [70, 38], "width": 110}, "elements": [
        {"type": "trade_route", "points": [[116.4, 39.9], [69.2, 41.3], [28.9, 41.0]], "icon": "camel", "dur": 3,
         "at": 0.1}]})
    r = s["elements"][0]
    assert r["type"] == "route" and r["points"][0] == {"lon": 116.4, "lat": 39.9}
    route = [L["dyn"].__self__ for L in sc.layers if L.get("dyn") is not None and hasattr(L["dyn"], "__self__")][0]
    a1 = np.asarray(route.frame(route.t0 + 0.6).getchannel("A")).sum()
    a2 = np.asarray(route.frame(route.t0 + 2.9).getchannel("A")).sum()
    assert a2 > a1 * 1.5


def test_closer_map_after_a_wider_one_zooms_in():
    from studio.engine.render import pick_transition
    from studio.engine.livemap import view_zoom, compose_mapzoom
    from PIL import Image
    eu = {"bg": {"type": "map", "center": [10, 50], "width": 40}, "elements": []}
    fr = {"bg": {"type": "map", "center": [2.5, 46.5], "width": 13}, "elements": []}
    far = {"bg": {"type": "map", "center": [140, 35], "width": 30}, "elements": []}
    assert pick_transition(eu, fr, 3) == "mapzoom" and pick_transition(fr, eu, 3) == "mapzoom"
    assert pick_transition(eu, far, 3) == "cut"
    info = view_zoom(eu["bg"], fr["bg"])
    assert info[0] == "in" and 2.5 < info[3] < 3.5
    a, b = Image.new("RGB", (1920, 1080), (200, 0, 0)), Image.new("RGB", (1920, 1080), (0, 0, 200))
    assert compose_mapzoom(a, b, info, 0.99).getpixel((960, 540))[2] > 150


def test_region_shot_frames_a_country():
    sc, _, _ = scene({"bg": EUROPE, "elements": [], "camera": {"shots": [{"at": 0.5, "region": "Italy"}]}})
    assert sc.shots and sc.shots[0]["z"] > 1.2


# ------------------------------------------------------------------ charts and timelines
def test_bar_chart_alias_grows_to_its_values():
    sc, s, _ = scene({"bg": {"type": "paper"}, "elements": [{"type": "bar_chart", "title": "Armies", "data": [
        {"label": "France", "value": "73,000"}, {"label": "Britain", "value": 68000}]}]})
    ch = s["elements"][0]
    assert ch["type"] == "chart" and ch["style"] == "bar" and ch["data"][0]["value"] == 73000
    chart = [L["dyn"].__self__ for L in sc.layers if L.get("dyn") is not None and hasattr(L["dyn"], "__self__")][0]
    assert "73,000" in chart.text.cache or chart.frame(4.9) is not None
    chart.frame(4.9)
    assert "73,000" in chart.text.cache and "68,000" in chart.text.cache


def test_timeline_compare_and_split_compile():
    sc, s, _ = scene({"bg": {"type": "paper"}, "elements": [{"type": "timeline", "events": [
        {"year": "1789", "label": "Revolution"}, {"year": 1815, "label": "Waterloo"}]}]})
    assert [e["year"] for e in s["elements"][0]["events"]] == [1789, 1815]
    assert sum(1 for _, k in sc.sfx if k == "pop") >= 2
    sc, s, _ = scene({"bg": {"type": "paper"}, "elements": [{"type": "versus", "items": [
        {"label": "In", "value": 600000}, {"label": "Out", "value": 100000}]}]})
    assert s["elements"][0]["type"] == "compare"
    split, _, _ = scene({"bg": {"type": "street"}, "elements": [{"type": "then_now", "left": "1850", "right": "TODAY"}]})
    im = split.render_at(2.0).convert("RGB")
    left, right = np.asarray(im.crop((100, 300, 800, 700))), np.asarray(im.crop((1120, 300, 1820, 700)))
    sat = lambda a: (a.max(axis=2).astype(int) - a.min(axis=2)).mean()
    assert sat(left) < sat(right)                               # the "then" side is sepia


# ------------------------------------------------------------------ music and narration
def test_music_styles_follow_the_story():
    from studio.engine.audio import music_style, smooth_styles, MAKERS, sfx
    assert music_style("Napoleon's army marched on Moscow", "tense") == "epic"
    assert music_style("Nobody knows where the treasure went", "tense") == "mystery"
    assert music_style("France won the war", "fun") == "triumph"
    assert music_style("He died alone in exile", "somber") == "sad"
    assert music_style("They had lunch", "fun") == "fun"
    assert smooth_styles(["fun", "epic", "fun"], [6, 3, 6]) == ["fun", "fun", "fun"]
    assert smooth_styles(["fun", "epic", "epic"], [6, 4, 5]) == ["fun", "epic", "epic"]
    for k in ("epic", "mystery", "triumph", "sad"):
        x = MAKERS[k](4.0)
        assert len(x) == 4 * 44100 and np.abs(x).max() > 0.01
    for k in ("triumph", "reveal", "fail", "war"):
        assert np.abs(sfx("sting:" + k)).max() > 0.5


def test_stings_land_on_the_word_and_keep_their_distance():
    from studio.pipeline.stages import sting_events
    beats = [{"text": "France won at Austerlitz.", "mood": "fun"},
             {"text": "But then Russia attacked.", "mood": "tense"},
             {"text": "Then everyone mourned.", "mood": "somber"},
             {"text": "It was a total disaster.", "mood": "fun"}]
    ev = sting_events(beats, [0, 6, 12, 30], [6, 6, 6, 5], {})
    assert ev[0][1] == "sting:triumph" and 0.5 < ev[0][0] < 3.0
    assert [k for _, k in ev] == ["sting:triumph", "sting:fail"]   # the twist was too soon after; no sting when sad


def test_narrator_slows_down_for_sad_parts():
    from studio.pipeline.stages import narration
    sad, fun = narration("somber", 1.2, "kokoro"), narration("fun", 1.2, "kokoro")
    assert sad[0] < 1.2 < fun[0] and sad[1] > 0.3 and fun[1] == 0.0
    assert 0.7 <= narration("somber", 0.75, "elevenlabs")[0]


# ------------------------------------------------------------------ what the AI is taught
def test_docs_and_examples_teach_the_new_features():
    from studio.prompts import scene_language, scene_language_compact, storyboard_prompt, load_examples
    full, short = scene_language(), scene_language_compact()
    for word in ("weather", "light", "empire", "route", "chart", "timeline", "compare", "split", "slash", "collapse",
                 "capital", "region"):
        assert word in full and word in short, word
    assert len(short) < len(full) / 3
    blob = json.dumps(load_examples())
    for word in ('"empire"', '"route"', '"chart"', '"timeline"', '"split"', '"weather"', '"slash"', '"fire"'):
        assert word in blob, word
    beats = [{"mood": "fun", "text": "Napoleon wins."}]
    small = storyboard_prompt([(0, beats[0])], beats, [], "T", examples=3, compact=True)
    big = storyboard_prompt([(0, beats[0])], beats, [], "T")
    assert len(small) < len(big) / 3 and "army_speech" not in small and "EXAMPLES" in small
