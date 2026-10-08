"""The research engine: budget, cache reuse, source quality, claim tracking, stop-and-ask. No network, no AI: a fake
researcher answers in the same JSON the real one is asked for."""
import json

import pytest

from studio.research import budget as BD, claims as CL, sources as SRC, store as ST, engine as EN


class Ctx:
    def __init__(self):
        self.lines = []

    def log(self, m):
        self.lines.append(m)

    warn = log


class Writer:
    id, supports_web = "claude_cli", True


def raw(n_claims=16, n_src=6, primary=True, queries=5):
    srcs = [dict(url=f"https://www.archives.gov/page{i}" if (primary and i == 0) else f"https://example{i}.org/p", title=f"T{i}",
                 organization="National Archives" if i == 0 else "Example", date="2020") for i in range(n_src)]
    return dict(summary="The colonies revolted against Britain over taxes and rights.",
                timeline=[dict(year=1765 + i, event=f"event {i} happened in the colonies") for i in range(8)],
                people=[dict(name=n, role="r", years="1732-1799", look="l", trait="t") for n in ("George Washington", "King George III", "Thomas Jefferson", "Benjamin Franklin", "John Adams")],
                places=[dict(name="Boston", note="Massachusetts colony")], documents=[dict(name="Declaration of Independence", lines=["WE HOLD THESE TRUTHS"])],
                numbers=[dict(claim="Colonies at the start", value="13")], visuals=["Washington crossing the Delaware"],
                claims=[dict(claim=f"In {1765 + i} something specific happened to colony number {i} and the crown.", url=srcs[i % n_src]["url"],
                             evidence="the page says so", confidence="high") for i in range(n_claims)],
                sources=srcs, queries_used=[f"query {i}" for i in range(queries)], gaps=[])


def call_factory(answers):
    seen = []

    def call(llm, system, prompt, label, web):
        seen.append((label, prompt))
        return answers[min(len(seen) - 1, len(answers) - 1)]
    call.seen = seen
    return call


@pytest.fixture(autouse=True)
def fresh_cache(tmp_path, monkeypatch):
    from studio import config
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))


# ---------------------------------------------------------------- config / budget
def test_modes_and_overrides():
    n = BD.resolve_config({}, {}, "normal")
    assert (n["mode"], n["max_queries"], n["max_sources"]) == ("normal", 10, 15)
    f = BD.resolve_config({}, {}, "fast")
    d = BD.resolve_config({}, {"research_mode": "deep"}, "fast")
    assert f["max_queries"] < n["max_queries"] < d["max_queries"]
    custom = BD.resolve_config({"research": {"max_queries": 3, "reuse_cached_research": False}}, {}, "normal")
    assert custom["max_queries"] == 3 and custom["reuse_cached_research"] is False and custom["max_sources"] == 15


def test_budget_tracks_repeats_sources_and_exhaustion():
    b = BD.Budget(BD.resolve_config({}, {}, "fast"))
    b.charge_queries(["Boston Tea Party", "boston tea  party!", "stamp act", "a", "b"])
    b.charge_sources(["https://a.org/x#top", "https://a.org/x/"])
    r = b.report()
    assert r["repeated_queries"] == 1 and r["sources"] == 1 and r["queries"] == 4
    assert b.exhausted() and b.remaining()["queries"] == 0 and r["overrun"] == []
    b.charge_queries(["extra"])
    assert b.report()["overrun"]


# ---------------------------------------------------------------- sources
@pytest.mark.parametrize("url, tier", [
    ("https://www.archives.gov/founding-docs/constitution", "archive"), ("https://www.loc.gov/item/x/", "archive"),
    ("https://www.si.edu/object/x", "museum"), ("https://history.princeton.edu/x", "academic"),
    ("https://www.britannica.com/event/x", "encyclopedia"), ("https://en.wikipedia.org/wiki/X", "tertiary"),
    ("https://somebody.blogspot.com/2020/x", "avoid"), ("https://www.nps.gov/bost/", "government"), ("not a url", "none")])
def test_source_tiers(url, tier):
    assert SRC.quality(url)["tier"] == tier


def test_confidence_is_capped_by_the_source():
    assert CL.confidence("high", "https://www.archives.gov/x") == "high"
    assert CL.confidence("high", "https://en.wikipedia.org/wiki/X") == "medium"
    assert CL.confidence("high", "https://a.blogspot.com/x") == "low"
    assert CL.confidence("high", "") == "unverified"


# ---------------------------------------------------------------- engine
def test_first_research_saves_the_four_files_and_tracks_sources():
    ctx, call = Ctx(), call_factory([raw()])
    cfg = BD.resolve_config({}, {}, "normal")
    r = EN.research_topic(ctx, Writer(), call, "The American Revolution", 5, cfg)
    assert r.sufficient and not r.cached and len(call.seen) == 1
    assert "at most 10 web searches" in call.seen[0][1] and "at most 15 sources" in call.seen[0][1]
    import os
    d = os.path.join(ST.root(), "american-revolution")
    assert sorted(os.listdir(d)) == ["brief.json", "claims.json", "metadata.json", "research.md", "sources.json"]
    c = json.load(open(os.path.join(d, "claims.json")))[0]
    assert {"claim", "source", "url", "organization", "date", "evidence", "confidence", "used_in_scenes"} <= set(c)
    assert "American Revolution" in open(os.path.join(d, "research.md")).read()


def test_repeating_the_topic_reuses_the_cache_without_any_ai():
    cfg = BD.resolve_config({}, {}, "normal")
    EN.research_topic(Ctx(), Writer(), call_factory([raw()]), "American Revolution", 5, cfg)
    call = call_factory([raw()])
    r = EN.research_topic(Ctx(), Writer(), call, "the American Revolution", 5, cfg)
    assert r.cached and call.seen == [] and r.report["cached_hits"] > 0 and r.report["queries"] == 0


def test_a_new_angle_researches_only_the_missing_part():
    cfg = BD.resolve_config({}, {}, "normal")
    EN.research_topic(Ctx(), Writer(), call_factory([raw()]), "American Revolution", 5, cfg)
    more = raw(n_claims=3, n_src=2)
    more["claims"][0]["claim"] = "The Boston Tea Party destroyed 342 chests of tea in December 1773."
    call = call_factory([more])
    r = EN.research_topic(Ctx(), Writer(), call, "The Boston Tea Party in the American Revolution", 5, cfg)
    assert len(call.seen) == 1 and "Research ONLY these gaps" in call.seen[0][1] and "boston" in call.seen[0][1].lower()
    assert any("342 chests" in c["claim"] for c in r.claims) and len(r.claims) > 16


def test_stops_and_asks_when_the_budget_is_spent_and_evidence_is_thin():
    cfg = BD.resolve_config({"research": {"max_queries": 2}}, {}, "normal")
    thin = raw(n_claims=4, n_src=2, primary=False, queries=2)
    with pytest.raises(BD.ResearchBudgetReached) as e:
        EN.research_topic(Ctx(), Writer(), call_factory([thin]), "The Stamp Act", 5, cfg)
    info = e.value.info
    assert info["gaps"] and info["budget"]["queries"] == 2 and info["proposal"]["queries"] >= 3


def test_an_approved_top_up_is_its_own_small_budget_and_never_asks_again():
    cfg = BD.resolve_config({"research": {"max_queries": 2}}, {}, "normal")
    thin = raw(n_claims=4, n_src=2, primary=False, queries=2)
    with pytest.raises(BD.ResearchBudgetReached):
        EN.research_topic(Ctx(), Writer(), call_factory([thin]), "The Stamp Act", 5, cfg)
    call = call_factory([raw(n_claims=14, n_src=5, queries=3)])
    r = EN.research_topic(Ctx(), Writer(), call, "The Stamp Act", 5, cfg, grant=dict(queries=4, sources=6, seconds=90))
    assert "at most 4 web searches" in call.seen[0][1] and r.report["max_queries"] == 4


def test_no_web_means_no_invented_sources():
    class NoWeb:
        id, supports_web = "gemini", False
    cfg = BD.resolve_config({}, {}, "normal")
    answer = raw()                                      # a writer that returns urls anyway must not get credit for them
    r = EN.research_topic(Ctx(), NoWeb(), call_factory([answer]), "Napoleon", 5, cfg)
    assert all(c["url"] == "" and c["confidence"] == "unverified" for c in r.claims) and r.sources == []


def test_sources_over_the_limit_are_dropped_and_noted():
    cfg = BD.resolve_config({"research": {"max_sources": 3}}, {}, "normal")
    with pytest.raises(BD.ResearchBudgetReached):
        EN.research_topic(Ctx(), Writer(), call_factory([raw(n_src=8, n_claims=16)]), "Salem", 5, cfg)
    saved = ST.load("salem")
    assert len(saved["sources"]) <= 3 and any("sources returned" in o for o in saved["metadata"]["budget"]["overrun"])


# ---------------------------------------------------------------- claims <-> script
def test_claims_link_to_the_beats_that_use_them_and_unsupported_items_are_found():
    cfg = BD.resolve_config({}, {}, "normal")
    r = EN.research_topic(Ctx(), Writer(), call_factory([raw()]), "American Revolution", 5, cfg)
    beats = [dict(text="In 1767 something specific happened to colony number 2 and the crown."),
             dict(text="Washington lost 9000 men at Valmy in 1792."), dict(text="Hi!", host="intro")]
    used = CL.link_scenes(r.claims, beats)
    assert used[0] and not used[1]
    assert any(0 in c["used_in_scenes"] for c in r.claims)
    items = CL.unsupported_items(beats, r.claims, r.brief)
    assert {"beat": 1, "kind": "year", "item": "1792"} in items and {"beat": 1, "kind": "num", "item": "9000"} in items
    assert not [i for i in items if i["beat"] == 0]
    src = CL.used_sources(r.claims, r.sources)
    assert src and all(s["claims"] for s in src)


def test_evidence_check_skips_common_country_names_and_year_gaps_the_script_itself_explains():
    from studio.research import claims as CL
    beats = [{"text": "In 1781 the war was won at Yorktown."}, {"text": "Six years later, in 1787, they met in England."},
             {"text": "Nine years later they stopped."}]
    claims = [dict(claim="Yorktown fell in 1781 and Philadelphia met in 1787.", evidence="")]
    items = CL.unsupported_items(beats, claims, {})
    assert not [x for x in items if x["beat"] == 1]                          # "Six" is 1787-1781, "England" is common knowledge
    assert any(x["beat"] == 2 and x["item"] == "9" for x in items)           # a gap nothing explains is still checked
