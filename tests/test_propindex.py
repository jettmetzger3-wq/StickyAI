"""The shared prop library and the local prop index: props are picked by lookup, the AI only draws what is truly missing."""
import json

import pytest

from studio.engine import prop_library as PL
from studio.engine.pen import Pen
from studio.engine.registry import PROPS, PROP_ALIASES, PROP_ENUM, PROP_GROUPS, guess_prop, prop_bounds, resolve_prop
from studio.engine.schema import check_scene
from studio.knowledge import composer as CO, propindex as PX

DESIGN = {"name": "Rosetta Stone", "anchor": "bottom", "description": "a carved stone slab",
          "parts": [{"shape": "poly", "points": [[18, 100], [82, 100], [86, 30], [60, 8], [20, 20]], "fill": "#5A5A66"},
                    {"shape": "line", "points": [[26, 40], [74, 38]], "color": "silver", "width": 1.5}]}


@pytest.fixture
def user_library(tmp_path, monkeypatch):
    """A throw-away folder for the user's designs; whatever a test registers is taken out again."""
    monkeypatch.setattr(PL, "user_dir", lambda: str(tmp_path / "prop_library"))
    before = (set(PROPS), set(PL.LIBRARY), list(PROP_ENUM), dict(PROP_ALIASES), [(l, list(n)) for l, n in PROP_GROUPS])
    yield tmp_path / "prop_library"
    for n in set(PROPS) - before[0]:
        PROPS.pop(n, None)
    for n in set(PL.LIBRARY) - before[1]:
        PL.LIBRARY.pop(n, None)
    PROP_ENUM[:] = before[2]
    PROP_ALIASES.clear()
    PROP_ALIASES.update(before[3])
    PROP_GROUPS[:] = [(l, n) for l, n in before[4]]
    PX.reset()


# ---------------------------------------------------------------- the shipped library
def test_shipped_library_is_registered_and_draws():
    shipped = {n for n, d in PL.LIBRARY.items() if d["source"] == "shipped"}
    assert len(shipped) >= 40 and {"pistol", "dagger", "printing_press", "tricorn_hat", "christian_cross"} <= shipped
    for n in shipped | set(PL.VARIANTS):
        anchor, fn, desc = PROPS[n]
        assert anchor in ("bottom", "center") and desc and n in PROP_ENUM
        p = Pen(1, rgba=True, size=(900, 900))
        fn(p, 450, 700 if anchor == "bottom" else 450, 0.5, None, {})
        assert p.im.getchannel("A").getbbox(), n
        x0, y0, x1, y1 = prop_bounds(n)
        assert x1 > x0 and y1 > y0, n
    assert {n for _, names in PROP_GROUPS for n in names} == set(PROPS) - {"custom"}


def test_exact_library_names_beat_looser_aliases_and_variants_keep_settings():
    assert resolve_prop("bread") == "bread" and resolve_prop("canoe") == "canoe" and resolve_prop("rose") == "rose"
    assert resolve_prop("cross") == "xmark" and resolve_prop("christian cross") == "christian_cross"
    assert PL.VARIANTS["tea_chest"]["prop"] == "crate" and PL.VARIANTS["white_flag"]["prop"] == "flag"
    p = Pen(1, rgba=True, size=(900, 900))
    PROPS["tea_chest"][1](p, 450, 700, 0.5, None, {})
    assert p.im.getchannel("A").getbbox()


def test_library_never_replaces_a_prop_drawn_in_code():
    assert PL.register({"name": "cannon", "parts": DESIGN["parts"]}) is None
    assert PL.register({"name": "x", "parts": []}) is None


# ---------------------------------------------------------------- the word table
def test_every_word_points_at_a_real_prop_and_no_vague_words():
    table = json.load(open(PX.WORDS_FILE, encoding="utf-8"))["words"]
    assert len(table) >= 900
    for w, target in table.items():
        assert target in PROPS and target not in PX.NEVER, (w, target)
    for vague in ("will", "bill", "pass", "date", "year", "power", "light", "french", "british", "england", "washington", "president"):
        assert vague not in table, vague
    short = {w for w in table if " " not in w and len(w) <= 3}              # short words are the risky ones: each was reviewed
    assert short <= {"ale", "axe", "bow", "cod", "cub", "fee", "fog", "gun", "hay", "hen", "hog", "ice", "icy", "ink", "jar", "jet",
                     "mob", "nun", "oak", "oar", "ore", "ox", "pen", "pub", "rum", "rye", "spy", "sun", "tax", "tea", "tv", "urn",
                     "car", "cow", "pig", "rat", "cat", "dog"}, sorted(short)


# ---------------------------------------------------------------- finding props in a narration
def test_a_word_that_is_a_prop_wins_then_meaning_answers():
    assert PX.pick("The cannon fired at dawn.") == "cannon"
    assert PX.pick("Troops marched through the night.") == "helmet"
    assert PX.pick("They signed the treaty in the hall.") == "scroll"
    assert PX.pick("Smugglers hid the gunpowder in the cellar.") == "keg"
    assert PX.pick("Two gentlemen settled it with a duel at dawn.") == "pistol"
    assert PX.pick("Nothing in this sentence is an object.") is None
    got = PX.find("The merchants loaded cargo while soldiers watched the harbor.")
    assert {"dock", "crate", "helmet"} <= {g["name"] for g in got} and {g["kind"] for g in got} == {"name", "word"}


def test_skip_and_never_props():
    assert PX.pick("A crowd gathered and the cannon fired", skip=("cannon",)) is None
    assert PX.pick("The people cheered") is None and PX.pick("a puppet show") is None


def test_the_year_removes_what_did_not_exist():
    assert PX.pick("Television sets filled the living rooms in 1955.") == "tv"
    assert PX.pick("In 1650 the family talked about television.") is None       # the meaning table respects the year
    assert PX.fits("telephone", 1700) is False and PX.fits("telephone", 1900) is True and PX.fits("pistol", 1500) is False
    assert PX.fits("anvil", None) and PX.first_year("tricorn_hat") == 1680 and PX.first_year("cannon") == 1326


def test_words_that_are_also_verbs_need_a_noun_position():
    assert PX.pick("Prices rose sharply after the war.") is None
    assert PX.pick("She held a red rose in her hand.") == "rose"
    assert PX.pick("They had to cross the river at night.") is None
    assert PX.pick("A wooden cross stood on the hill.") == "christian_cross"
    assert PX.pick("The statue of liberty welcomed them.") == "statue_of_liberty"


def test_composer_uses_the_index():
    assert CO.prop_in_text("Soldiers waited for orders.", skip=("crowd",)) == "helmet"
    assert CO.prop_in_text("The newspaper printed it.", skip=("crowd",)) == "newspaper"
    assert CO.prop_in_text("Nothing to see here.") is None


def test_guess_prop_uses_meaning_as_the_last_step():
    assert guess_prop("colonial_musketeer") == "musket"
    assert guess_prop("british_warship") == "ship"
    assert guess_prop("unicorn") is None and guess_prop("napoleon") is None


def test_coverage_concepts_include_what_a_prop_means():
    from studio.knowledge import semantics as SM
    scene = {"bg": {"type": "paper"}, "elements": [{"type": "prop", "name": "keg", "x": 900, "y": 800}]}
    assert "gunpowder" in SM.scene_concepts(scene)


# ---------------------------------------------------------------- gaps
def test_missing_objects_are_remembered_and_forgotten_once_the_library_has_them(tmp_path, monkeypatch, user_library):
    monkeypatch.setattr(PX, "gaps_path", lambda: str(tmp_path / "gaps.json"))
    assert PX.note_gap("quetzal feather headdress", "The king wore a quetzal feather headdress.")
    assert PX.note_gap("quetzal feather headdress")
    assert not PX.note_gap("cannon")                                     # a prop exists: not a gap
    rows = PX.gaps()
    assert rows[0][0] == "quetzal feather headdress" and rows[0][1] == 2 and "king" in rows[0][2]
    d = dict(DESIGN, name="quetzal_feather_headdress", description="a quetzal feather headdress")
    assert PL.add_user_design(d)
    PX.reset()
    assert PX.gaps() == []                                               # learned: no longer missing


# ---------------------------------------------------------------- designs kept for good
def test_an_ai_designed_prop_is_kept_and_reused_by_name(user_library):
    d = PL.add_user_design(DESIGN)
    assert d and d["name"] == "rosetta_stone" and (user_library / "rosetta_stone.json").exists()
    assert "rosetta_stone" in PROPS and "rosetta_stone" in PROP_ENUM
    assert PL.add_user_design(DESIGN) is None                            # never overwritten
    assert PL.add_user_design(dict(DESIGN, name="cannon")) is None       # never shadows a built-in
    PX.reset()
    assert PX.pick("Scholars studied the Rosetta Stone.") == "rosetta_stone"
    # a scene that names it stores the shapes inside the scene (a saved scene renders anywhere)
    scene, fixes, errs = check_scene({"bg": {"type": "field"}, "elements": [{"type": "prop", "name": "rosetta stone", "x": 900, "y": 880}]},
                                     "fun", "The Rosetta Stone", [], [])
    assert not errs and scene["elements"][0]["name"] == "custom" and scene["elements"][0]["params"]["parts"]
    # a new session finds it again
    PL.LIBRARY.pop("rosetta_stone"), PROPS.pop("rosetta_stone")
    PL.load(force=True)
    assert "rosetta_stone" in PL.LIBRARY and PL.LIBRARY["rosetta_stone"]["source"] == "user"


def test_a_broken_design_file_is_reported_not_fatal(user_library):
    user_library.mkdir()
    (user_library / "bad.json").write_text("{not json")
    (user_library / "tiny.json").write_text(json.dumps({"name": "tiny", "parts": []}))
    PL.load(force=True)
    assert any("bad.json" in e for e in PL.ERRORS) and any("tiny.json" in e for e in PL.ERRORS)
    assert "pistol" in PL.LIBRARY


def test_library_props_change_the_render_key_only_for_scenes_that_use_them(user_library):
    plain = {"bg": {"type": "paper"}, "elements": [{"type": "prop", "name": "cannon", "x": 900, "y": 800}]}
    uses = {"bg": {"type": "paper"}, "elements": [{"type": "prop", "name": "pistol", "x": 900, "y": 800}]}
    assert PL.fingerprint(plain) == "" and PL.fingerprint([plain, None]) == ""
    fp = PL.fingerprint(uses)
    assert len(fp) == 8 and PL.fingerprint([plain, uses]) == fp
    saved = PL.LIBRARY["pistol"]["parts"]
    try:
        PL.LIBRARY["pistol"]["parts"] = saved[:-1]
        assert PL.fingerprint(uses) != fp
    finally:
        PL.LIBRARY["pistol"]["parts"] = saved
    from studio.pipeline import stages
    assert stages.engine_key([plain]) == stages.ENGINE_VERSION and str(stages.engine_key([uses])).startswith(f"{stages.ENGINE_VERSION}+")


# ---------------------------------------------------------------- the AI is asked only for what is missing
def _ctx(tmp_path):
    from studio.pipeline import new_project
    pr = new_project("Props", "topic", topic="Props", options={})
    logs = []

    class Ctx:
        project = pr
        log = staticmethod(logs.append)
        warn = staticmethod(logs.append)
    return Ctx, logs


def test_the_plan_decides_what_is_worth_an_ai_drawing(tmp_path, monkeypatch, user_library):
    from studio.pipeline import stages
    monkeypatch.setattr(PX, "gaps_path", lambda: str(tmp_path / "gaps.json"))
    beats = [{"text": "Soldiers carried gunpowder to the fort.", "mood": "tense"},
             {"text": "Scholars found the Rosetta Stone near the Nile.", "mood": "fun"}]
    plan = {0: {"needs": ["gunpowder", "13 colonies"]}, 1: {"needs": ["Rosetta Stone", "1799"]}}
    wanted = stages.unmet_objects(plan, beats)
    assert [w for w, _ in wanted] == ["Rosetta Stone"] and "Nile" in wanted[0][1]       # gunpowder -> keg: already there

    Ctx, logs = _ctx(tmp_path)
    calls = []

    def fake(ctx, llm, system, prompt, **kw):
        calls.append(prompt)
        return {"props": [DESIGN]}
    monkeypatch.setattr(stages, "call_llm", fake)
    script = {"title": "T", "topic": "t"}
    kit = stages.design_props(Ctx, object(), script, beats, [], "", [], wanted=wanted)
    assert len(calls) == 1 and "Rosetta Stone" in calls[0] and "NARRATION" not in calls[0] and len(calls[0]) < 2500
    assert [d["name"] for d in kit] == ["rosetta_stone"] and "rosetta_stone" in PL.LIBRARY
    assert (user_library / "rosetta_stone.json").exists()
    # the next video that needs it asks nobody
    PX.reset()
    assert stages.unmet_objects(plan, beats) == []
    calls.clear()
    other = [dict(beats[0]), dict(beats[1], text="Scholars read the Rosetta Stone again.")]
    stages.design_props(Ctx, object(), {"title": "T2", "topic": "t"}, other, [], "", [], wanted=[])
    assert calls == [] and any("no AI call" in m for m in logs)


def test_without_a_plan_the_old_whole_story_request_is_kept(tmp_path, monkeypatch, user_library):
    from studio.pipeline import stages
    Ctx, _ = _ctx(tmp_path)
    seen = []
    monkeypatch.setattr(stages, "call_llm", lambda ctx, llm, system, prompt, **kw: (seen.append(prompt), {"props": [DESIGN]})[1])
    stages.design_props(Ctx, object(), {"title": "T", "topic": "t"}, [{"text": "The stone was found.", "mood": "fun"}], [], "", [])
    assert len(seen) == 1 and "NARRATION" in seen[0]


def test_coverage_patch_shows_a_missing_object_without_creating_a_layout_problem(tmp_path, monkeypatch):
    from studio.engine import layout as LY
    from studio.knowledge import semantics as SM
    from studio.pipeline import coverage as CV
    monkeypatch.setattr(PX, "gaps_path", lambda: str(tmp_path / "gaps.json"))
    scene = {"bg": {"type": "paper"}, "elements": [
        {"type": "text", "text": "THE POWDER STORE", "x": 960, "y": 200, "size": 80, "color": "navy"},
        {"type": "char", "kind": "civ", "x": 600, "y": 900, "scale": 1.0}]}
    a = {"text": "They hid the gunpowder.", "years": [1775]}
    reqs = [dict(SM._req("object", "gunpowder", ["gunpowder"], "must", "test"))]
    cov = SM.coverage(reqs, scene)
    assert cov["missing"]
    added = CV.patch(scene, cov, a, [])
    assert added and any(e.get("name") == "keg" for e in scene["elements"])
    assert not [f for f in LY.audit(scene, dict(text=a["text"])) if f["sev"] in ("high", "medium")]
    assert SM.coverage(reqs, scene)["score"] == 1.0
    # nothing matches: written to the gap list instead
    cov2 = SM.coverage([SM._req("object", "quetzal headdress", ["quetzal headdress"], "must", "test")], scene)
    assert CV.patch(scene, cov2, a, []) == [] and PX.gaps()[0][0] == "quetzal headdress"


# ---------------------------------------------------------------- the command line
def test_props_seed_draws_only_what_is_missing_after_asking(tmp_path, monkeypatch, capsys, user_library):
    from studio import props_cli
    import studio.research_cli as rc
    monkeypatch.setattr(PX, "gaps_path", lambda: str(tmp_path / "gaps.json"))
    PX.note_gap("quetzal feather headdress", "The king wore a quetzal feather headdress.")
    asked = []

    class Fake:
        label, paid = "Fake writer", False
    monkeypatch.setattr(rc, "_llm", lambda name: Fake())
    monkeypatch.setattr(rc, "_call_factory", lambda llm: (lambda l, system, prompt, label, web:
                                                          (asked.append(prompt), {"props": [dict(DESIGN, name="quetzal_feather_headdress")]})[1]))
    a = type("A", (), dict(words="", max=8, writer="", yes=False))()
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert props_cli.cmd_seed(a) == 0 and asked == []                                  # asked first: "n" draws nothing
    assert "Estimate: 1 request" in capsys.readouterr().out
    a.yes = True
    props_cli.cmd_seed(a)
    assert len(asked) == 1 and "quetzal feather headdress" in asked[0]
    PX.reset()
    assert PX.gaps() == [] and "quetzal_feather_headdress" in PL.LIBRARY
    assert props_cli.cmd_seed(a) == 0 and len(asked) == 1                                # nothing left to draw: no request


def test_props_list_and_gaps_commands(capsys):
    from studio import props_cli
    props_cli.cmd_list(type("A", (), dict(names=True))())
    out = capsys.readouterr().out
    assert "hand-drawn" in out and "pistol" in out and "tea_chest" in out
    props_cli.cmd_gaps(type("A", (), dict(limit=5))())
    assert capsys.readouterr().out
