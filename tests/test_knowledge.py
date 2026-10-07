"""The knowledge layer: cache, usage ledger, modes, local beat analysis, patterns, composer, director, review."""
import json

import pytest

from studio import cache, usage
from studio.engine import check_scene
from studio.engine.compiler import build_scene
from studio.knowledge import analysis as AN, composer as CO, gazetteer as GZ, patterns as PT, people as PE, props_intel as PI
from studio.pipeline import characters as CH, continuity as CT, director as DR, estimate as EST, flow as FL, modes as MD
from studio.pipeline import review as RV

CAST = [dict(name="Americans", kind="america"), dict(name="British", kind="britain"), dict(name="Washington", kind="tricorn", coat="#2B3F8C"),
        dict(name="French", kind="france"), dict(name="Germany", kind="germany"), dict(name="Napoleon", kind="bicorne", coat="#2B3F8C")]


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear()
    yield
    cache.clear()


# ------------------------------------------------------------------ cache, ledger, modes
def test_cache_roundtrip_stats_and_clear():
    k = cache.key("llm", "claude", "hello")
    assert cache.get("llm", k) is None
    assert cache.put("llm", k, "answer")
    assert cache.get("llm", k) == "answer" and cache.has("llm", k)
    assert cache.stats()["llm"]["entries"] == 1 and cache.stats()["total"]["entries"] == 1
    assert cache.key("a", 1) == cache.key("a", 1) and cache.key("a", 1) != cache.key("a", 2)
    assert cache.clear("llm") == 1 and cache.get("llm", k) is None


def test_cache_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(cache, "load_settings", lambda: {"cache_enabled": False})
    assert not cache.put("llm", "abc", "x") and cache.get("llm", "abc") is None


def test_usage_ledger_summarises_real_and_cached_calls(tmp_path):
    class Pr:
        def p(self, *parts):
            return str(tmp_path.joinpath(*parts))
    pr = Pr()
    usage.record(pr, dict(stage="script", task="script", in_tok=1600, out_tok=4000, secs=20))
    usage.record(pr, dict(stage="storyboard", task="storyboard", in_tok=4000, out_tok=1500, secs=30))
    usage.record(pr, dict(stage="storyboard", task="storyboard", in_tok=4000, out_tok=1500, cached=True))
    s = usage.summary(pr)
    assert s["total"]["calls"] == 2 and s["total"]["cached"] == 1 and s["total"]["tokens"] == 1600 + 4000 + 4000 + 1500
    assert s["by_stage"]["storyboard"]["calls"] == 1


def test_modes_pick_from_options_then_settings():
    assert MD.name_of(opts={"gen_mode": "fast"}) == "fast"
    assert MD.name_of(opts={"gen_mode": "nonsense"}, settings={"gen_mode": "deep"}) == "deep"
    assert MD.name_of(opts={}, settings={}) == "normal"
    assert MD.profile(opts={"gen_mode": "fast"})["research"] is False and MD.profile(opts={"gen_mode": "deep"})["research"] is True
    assert MD.MODES["fast"]["plan_batch"] > MD.MODES["deep"]["plan_batch"]


def test_estimate_orders_the_modes_and_beats_the_old_way():
    from studio.pipeline.costs import Draft
    est = {m: EST.estimate_video(Draft("topic", {"llm": "claude_cli"}, {"minutes": 10, "gen_mode": m})) for m in MD.MODES}
    assert est["fast"]["total"]["tokens"] < est["normal"]["total"]["tokens"] < est["deep"]["total"]["tokens"]
    assert est["normal"]["total"]["tokens"] < est["normal"]["old_way"]["tokens"] and est["normal"]["saved_pct"] > 30
    assert est["fast"]["total"]["calls"] <= 4
    classic = EST.estimate_video(Draft("topic", {"llm": "claude_cli"}, {"minutes": 10, "storyboard_engine": "classic"}))
    assert classic["total"]["tokens"] > est["normal"]["total"]["tokens"]


# ------------------------------------------------------------------ people, places, analysis
def test_known_people_and_the_two_roosevelts():
    assert PE.find("General Washington")["id"] == "washington" and PE.find("Napoleon Bonaparte")["id"] == "napoleon"
    assert PE.find("Roosevelt", 1942)["id"] == "fdr" and PE.find("Roosevelt", 1905)["id"] == "teddy_roosevelt"
    ids = [e["id"] for e, _ in PE.find_in_text("Ben Franklin napped while Hamilton argued and King George fumed.")]
    assert ids == ["franklin", "hamilton", "king_george_iii"]
    lk = PE.look(PE.find("lincoln"))
    assert lk["kind"] == "tophat" and lk["look"] == "beard"


def test_gazetteer_finds_cities_and_battles():
    names = [c["name"] for c in GZ.find_in_text("He marched from Paris to Moscow and won at Borodino.")]
    assert names == ["Paris", "Moscow", "Borodino"]
    assert GZ.find("peking")["name"] == "Beijing"


def test_analysis_extracts_people_documents_numbers_and_events():
    a = AN.analyze("The Treaty of Versailles was signed in 1919, and Germany had to pay $33 billion.", "fun", CAST, set())
    assert a["documents"][0]["name"] == "Treaty of Versailles" and a["years"] == [1919]
    assert a["numbers"][0]["kind"] == "money" and "33 billion" in a["numbers"][0]["shown"]
    assert "treaty" in a["events"] and "signing" in a["events"]
    seen = set()
    b = AN.analyze("In 1787 Washington and James Madison met in Philadelphia.", "fun", CAST, seen)
    assert {p["id"] for p in b["people"]} == {"washington", "madison"} and b["intro"]
    assert [p["name"] for p in b["places"]] == ["Philadelphia"]
    assert AN.analyze("Washington spoke again.", "fun", CAST, seen)["intro"] == []          # not new any more
    c = AN.analyze("Suddenly General Howe marched 20,000 men toward New York.", "tense", CAST, set())
    assert [p["name"] for p in c["people"]] == ["General Howe"]                              # New York is not a person
    assert AN.analyze("In the streets, 25 percent of workers rioted.", "tense", [], set())["place_type"] == "street"


# ------------------------------------------------------------------ patterns and the composer
SAMPLES = {
    "DOCUMENT_SIGNING": "In 1787 Madison and Washington signed the Constitution in Philadelphia.",
    "WAR_DECLARATION": "In August 1914 Germany declared war on France.",
    "RIOT": "The angry mob stormed the castle and burned it down.",
    "DEATH_OF_HISTORICAL_FIGURE": "Lincoln was shot at Ford's Theatre in April 1865.",
    "PEACE_TREATY": "The Treaty of Versailles was signed in 1919, and Germany had to accept the blame.",
    "STATISTIC_VISUALIZATION": "The war killed more than 20 million people.",
    "ECONOMIC_CRISIS": "In 1929 the stock market crashed and prices collapsed.",
    "CITY_ESTABLISHING": "In Paris, in 1789, the crowd had run out of bread.",
}


@pytest.mark.parametrize("pid,text", list(SAMPLES.items()))
def test_retriever_picks_the_expected_pattern_family(pid, text):
    a = AN.analyze(text, "fun", CAST, set())
    ids = [p["id"] for p, _ in PT.match(a, (), 3)]
    assert pid in ids


def test_every_pattern_composes_a_valid_scene():
    """The 33 patterns each build a scene the engine accepts with no errors and no warnings."""
    texts = {
        "TIMELINE": "From 1914 to 1918, then 1929 and 1939, the world kept falling apart.",
        "ELECTION": "In the election Lincoln won with 40 percent of the vote.",
        "STORY_MOMENT": "He kept losing at chess to a pigeon.",
    }
    for p in PT.load()["patterns"]:
        text = SAMPLES.get(p["id"]) or texts.get(p["id"]) or "In 1789 in Paris Napoleon argued with Washington about 5,000 men and the Treaty of Paris."
        beat = dict(mood="fun", text=text)
        a = AN.analyze(text, "fun", CAST, set())
        sc = CO.compose(p, beat, a, {}, CO.Ctx(cast=CAST, idx=3))
        if sc is None:
            continue                                       # a pattern may decline a beat it has no ingredients for
        fixed, fixes, errs = check_scene(sc, "fun", text, [], CAST)
        assert not errs, (p["id"], errs)
        assert not build_scene(fixed, 3, 6.0, "fun", text).warnings, p["id"]
    built = [p["id"] for p in PT.load()["patterns"] if CO.compose(p, dict(mood="fun", text=SAMPLES["DOCUMENT_SIGNING"]),
                                                                  AN.analyze(SAMPLES["DOCUMENT_SIGNING"], "fun", CAST, set()), {}, CO.Ctx(cast=CAST))]
    assert len(built) >= 20                                # most patterns can build from a rich beat


def test_composed_signing_scene_has_a_real_document_and_the_right_people():
    text = SAMPLES["DOCUMENT_SIGNING"]
    a = AN.analyze(text, "fun", CAST, set())
    sc = CO.compose("DOCUMENT_SIGNING", dict(mood="fun", text=text), a, {}, CO.Ctx(cast=CAST))
    doc = next(e for e in sc["elements"] if e.get("name") in ("document", "scroll"))
    assert doc["params"]["title"] == "THE CONSTITUTION" and "People" in " ".join(doc["params"]["text"])
    kinds = {e.get("who"): e.get("kind") for e in sc["elements"] if e.get("type") == "char"}
    assert kinds.get("Washington") == "tricorn"                                   # cast look wins
    assert any(isinstance(e.get("at"), str) and e["at"].startswith("word:") for e in sc["elements"])    # timed to the narration


def test_same_place_keeps_the_same_background_between_scenes():
    c = CO.Ctx(cast=CAST, idx=1)
    t1, t2 = "The two argued in the palace.", "Then the king shouted at his advisor in the palace."
    s1 = CO.compose("TWO_PEOPLE_TALK", dict(mood="fun", text=t1), AN.analyze(t1, "fun", CAST, set()), {}, c)
    s2 = CO.compose("TWO_PEOPLE_TALK", dict(mood="fun", text=t2), AN.analyze(t2, "fun", CAST, set()), {}, c)
    assert s1["bg"] == s2["bg"]


def test_prop_intelligence_writes_real_text():
    a = AN.analyze("The Treaty of Versailles was signed in 1919.", "fun", [], set())
    d = PI.doc_for(a)
    assert d["title"] == "TREATY OF VERSAILLES" and any("Germany" in x for x in d["lines"]) and d["prop"] == "scroll"
    assert PI.headline_for(AN.analyze("Germany declared war on France.", "tense", [], set())) == "WAR DECLARED"
    assert PI.slogan_for(AN.analyze("Workers went on strike for better wages.", "tense", [], set())) == "FAIR WAGES!"
    assert PI.weapon_for_year(1200) == "sword" and PI.weapon_for_year(1776) == "musket" and PI.weapon_for_year(1944) == "cannon"
    with PI.docs_scope({"stamp act": ("THE STAMP ACT", ["A tax on paper"], "document")}):
        assert PI.doc_for(AN.analyze("Parliament passed the Stamp Act.", "fun", [], set()))["lines"] == ["A tax on paper"]


def test_documents_show_their_text_in_the_prop():
    sc = build_scene({"bg": {"type": "paper"}, "elements": [{"type": "prop", "name": "document", "x": 960, "y": 540, "scale": 2.5,
                      "params": {"title": "Constitution", "text": ["We the People"], "stamp": "RATIFIED"}}]}, 0, 4.0, "fun", "x")
    assert not sc.warnings
    sc.render_at(3.0)


# ------------------------------------------------------------------ characters, continuity, review
def test_character_registry_keeps_the_whole_look_and_adds_known_people():
    script = {"title": "The Constitution", "cast": [dict(name="Washington", kind="tricorn", hat_color="black")],
              "beats": [dict(mood="fun", text="In 1787 Washington and James Madison met."), dict(mood="fun", text="Ben Franklin napped.")]}
    reg = CH.build(script)
    names = {e["name"] for e in reg}
    assert {"Washington", "James Madison", "Benjamin Franklin"} <= names
    w = next(e for e in reg if e["name"] == "Washington")
    assert w["coat"] == "#2B3F8C" and w["role"] and w["beats"] == [0]            # coat comes from the people list
    CH.merge_into_script(script, reg)
    assert all("coat" in c and "role" in c for c in script["cast"])


def test_normalize_script_no_longer_drops_coat_and_beard():
    from studio.pipeline.stages import normalize_script
    s = normalize_script({"title": "t", "beats": [dict(mood="fun", text="Hello there, history.", part="hook")],
                          "cast": [dict(name="Lincoln", kind="tophat", hat_color="black", coat="#222222", look="beard", role="president")]})
    c = s["cast"][0]
    assert c["coat"] == "#222222" and c["look"] == "beard" and c["role"] == "president" and s["beats"][0]["part"] == "hook"


def test_continuity_holds_the_time_of_day_but_lets_time_pass_naturally():
    beats = [dict(mood="fun", text="The army camped in the field."), dict(mood="fun", text="The army camped in the field again."),
             dict(mood="fun", text="Still the army camped there.")]
    an = [AN.analyze(b["text"], "fun", [], set()) for b in beats]
    scenes = {0: {"bg": {"type": "field", "time": "day"}, "elements": []}, 1: {"bg": {"type": "field", "time": "dusk"}, "elements": []},
              2: {"bg": {"type": "field", "time": "day"}, "elements": []}}
    iss = CT.check(scenes, an, [], beats)
    assert scenes[1]["bg"]["time"] == "dusk"                    # day -> dusk is time passing: left alone
    assert scenes[2]["bg"]["time"] == "dusk" and any("time of day" in i["msg"] for i in iss)     # dusk -> day with no reason: held


def test_review_fixes_blank_props_missing_numbers_and_anachronisms():
    beats = [dict(mood="fun", text="In 1776 a tank rolled into Philadelphia."), dict(mood="somber", text="25,000 men died.")]
    an = [AN.analyze(b["text"], b["mood"], [], set()) for b in beats]
    scenes = {0: {"bg": {"type": "city"}, "elements": [{"type": "prop", "name": "tank", "x": 900, "y": 800},
                                                       {"type": "prop", "name": "document", "x": 300, "y": 500, "scale": 2}]},
              1: {"bg": {"type": "sunburst"}, "elements": [{"type": "char", "kind": "civ", "x": 900, "y": 900}]}}
    rep = RV.run(scenes, beats, an, [], [3.0, 3.0])
    assert not any(e.get("name") == "tank" for e in scenes[0]["elements"])
    doc = next(e for e in scenes[0]["elements"] if e.get("name") == "document")
    assert doc["params"]["title"] and any(e["type"] == "counter" for e in scenes[1]["elements"])
    assert scenes[1]["bg"]["type"] == "dark" and rep["fixed"] >= 5 and rep["scores"]["history"] == 1.0


def test_flow_checker_finds_jumps_and_keeps_numbers():
    jumpy = [dict(mood="fun", text="The Cold War nearly ended the world in 1962."),
             dict(mood="fun", text="So what was the Cold War? A long standoff between two superpowers."),
             dict(mood="fun", text="Sugar prices in Brazil doubled that spring."),
             dict(mood="fun", text="Then missiles appeared in Cuba and everyone panicked.")]
    assert [i for i, _ in FL.seams(jumpy)] == [2]
    assert FL.keeps_facts("It was 1962 and 13 days.", "In 1962, for 13 days, the world held its breath.")
    assert not FL.keeps_facts("It was 1962 and 13 days.", "It was a long time ago.")


# ------------------------------------------------------------------ the director
def test_parse_plan_is_tolerant_and_rejects_unknown_patterns():
    got = DR.parse_plan({"plan": [{"beat": 3, "pattern": "document signing", "slots": {"signer": "Madison"}, "say": [{"who": "Madison", "text": "Ow."}]},
                                  {"beat": 4, "pattern": "NO_SUCH"}, {"pattern": "RIOT"}]}, [3, 4, 5])
    assert got[3]["pattern"] == "DOCUMENT_SIGNING" and got[4]["pattern"] == PT.CUSTOM and got[5]["pattern"] == "RIOT"
    assert got[3]["slots"] == {"signer": "Madison"}


def test_director_builds_scenes_with_few_calls_and_reuses_cached_plans():
    beats = [dict(mood="fun", text=SAMPLES["DOCUMENT_SIGNING"]), dict(mood="tense", text=SAMPLES["WAR_DECLARATION"]),
             dict(mood="fun", text="He kept losing at chess to a pigeon."), dict(mood="tense", text=SAMPLES["RIOT"])]
    script = {"title": "t", "beats": beats, "cast": CAST}
    reg = CH.build(script)
    an = DR.analyses_for(beats, CH.as_cast(reg))
    calls = []

    class Ctx:
        def warn(self, m):
            raise AssertionError(m)

    def call(llm, system, prompt, label):
        calls.append((label, len(prompt)))
        return {"plan": [{"beat": 0, "pattern": "DOCUMENT_SIGNING", "slots": {"signer": "Madison", "doc_title": "THE CONSTITUTION"}},
                         {"beat": 1, "pattern": "WAR_DECLARATION", "slots": {"message": "WAR!"}},
                         {"beat": 2, "pattern": "CUSTOM"},
                         {"beat": 3, "pattern": "RIOT", "slots": {"target": "castle"}, "say": [{"who": "", "text": "Down with them!"}]}]}

    class FakeLLM:
        id = "fake"

    prof = MD.profile(opts={"gen_mode": "normal"})
    scenes, custom, info = DR.build(Ctx(), FakeLLM(), script, [0, 1, 2, 3], reg, an, None, prof, call)
    assert len(calls) == 1 and sorted(scenes) == [0, 1, 3] and custom == [2]
    assert info[0]["pattern"] == "DOCUMENT_SIGNING" and info[3]["source"] == "plan"
    assert calls[0][1] < 12000                              # a whole batch of plan requests, not a 16,000-token manual per batch
    scenes2, custom2, _ = DR.build(Ctx(), FakeLLM(), script, [0, 1, 2, 3], reg, an, None, prof, call)
    assert len(calls) == 1 and custom2 == [2] and sorted(scenes2) == [0, 1, 3]       # the plans came from the cache


def test_director_without_an_ai_composes_locally_and_uses_the_catch_all():
    beats = [dict(mood="fun", text=SAMPLES["WAR_DECLARATION"]), dict(mood="fun", text="He kept losing at chess to a pigeon.")]
    script = {"title": "t", "beats": beats, "cast": CAST}
    reg = CH.build(script)
    an = DR.analyses_for(beats, CH.as_cast(reg))

    class Ctx:
        def warn(self, m):
            raise AssertionError(m)

    scenes, custom, info = DR.build(Ctx(), None, script, [0, 1], reg, an, None, MD.profile(opts={"gen_mode": "fast"}), None)
    assert custom == [] and info[0]["pattern"] == "WAR_DECLARATION" and info[1]["pattern"] == "STORY_MOMENT"


def test_call_llm_answers_repeat_questions_from_the_cache_and_logs_them(tmp_path, monkeypatch):
    from studio.pipeline import stages
    from studio.pipeline.project import new_project

    n = []

    class L:
        id, short, paid = "fake", "Fake", False

        def complete(self, system, prompt, **kw):
            n.append(1)
            return json.dumps({"ok": 1}), {"in_tok": 10, "out_tok": 5}

    class C:
        stage, msg = "script", ""

        def __init__(self, project):
            self.project = project

        def check_cancel(self):
            pass

        def log(self, m):
            pass

        def working(self, *a, **k):
            import contextlib
            return contextlib.nullcontext()

    pr = new_project("cache test", "topic", topic="x")
    c = C(pr)
    assert stages.call_llm(c, L(), "sys", "prompt A", label="script") == {"ok": 1}
    assert stages.call_llm(c, L(), "sys", "prompt A", label="script") == {"ok": 1}
    assert len(n) == 1                                                              # the second one cost nothing
    assert stages.call_llm(c, L(), "sys", "prompt A", label="script", cache=False) == {"ok": 1} and len(n) == 2
    s = usage.summary(pr)
    assert s["total"]["calls"] == 2 and s["total"]["cached"] == 1


def test_three_letter_names_count_only_when_written_like_names():
    from studio.knowledge import people as PE
    ids = lambda t: [e["id"] for e, _ in PE.find_in_text(t)]
    assert ids("Nixon visited Mao in China in 1972.") == ["nixon", "mao"]
    assert "robert_e_lee" in ids("Lee surrendered at Appomattox.")
    assert "fdr" in ids("FDR spoke on the radio.") and "kennedy" in ids("JFK was shot in Dallas.")
    assert ids("the lee side of the ship, a mao of jade") == []


def test_a_visit_between_two_named_leaders_is_a_two_person_scene():
    from studio.knowledge import analysis as AN, patterns as PT
    a = AN.analyze("Nixon visited Mao in China in 1972, shocking everyone by shaking hands.")
    pid, sc = PT.best(a)
    assert pid == "TWO_PEOPLE_TALK" and sc >= PT.CONFIDENT
