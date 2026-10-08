"""The local script quality pass: what it flags, what it leaves alone, and that it joins the one smoothing request."""
from studio.pipeline import flow as FL, quality as QL
from studio.pipeline.stages import clean_line


def beats(*texts, host=()):
    return [dict(mood="fun", text=t, **({"host": True} if i in host else {})) for i, t in enumerate(texts)]


GOOD = beats("Rome almost never existed, and the reason is a bad day for a goat.",
             "So in 753 BC two brothers argued about where to build a city, and that argument had a body count.",
             "Romulus won, which is why the city is called Rome and not Remia.",
             "But a city of runaways needs wives, so he threw a party and invited the neighbours.",
             "The neighbours came, and the party went very badly for them.")


def test_a_clean_script_has_nothing_to_fix():
    assert QL.problems(GOOD) == [] and QL.fix_list(GOOD) == []
    rep = QL.report(dict(beats=GOOD))
    assert rep["problems"] == [] and rep["stats"]["beats"] == 5 and rep["stats"]["longest"] >= rep["stats"]["shortest"]


def test_a_greeting_or_a_rambling_hook_is_a_flat_opening():
    b = beats("Hello everyone and welcome to the channel, today we look at Rome.", *[x["text"] for x in GOOD[1:]])
    p = QL.problems(b)
    assert p[0][0] == 0 and p[0][2] == "high" and "greeting" in p[0][1]
    b = beats("In this video we explain Rome.", *[x["text"] for x in GOOD[1:]])
    assert QL.problems(b)[0][2] == "high"
    long_hook = " ".join(["word"] * 40) + "."
    assert "hook is 40 words" in QL.problems(beats(long_hook, *[x["text"] for x in GOOD[1:]]))[0][1]


def test_a_trailing_ending_is_flagged_but_a_real_payoff_is_not():
    for end in ("And the empire fell because of", "The empire fell, and that's about it.", "So yeah."):
        p = QL.problems(beats(*[x["text"] for x in GOOD[:4]], end))
        assert p and p[-1][0] == 4 and p[-1][2] == "high", end
    assert QL.problems(beats(*[x["text"] for x in GOOD[:4]], "And that is why Rome fell, one bad dinner at a time.")) == []


def test_repeated_phrases_and_openers_name_the_third_use():
    t = ["The army marched to the river and waited.", "Then the army marched to the river again.", "Soon the army marched to the river once more.",
         "Meanwhile, nothing else happened at all."]
    rep = {i: w for i, w, _ in QL.problems(beats(*t))}
    assert 2 in rep and "army marched to" in rep[2] and 0 not in rep and 1 not in rep
    same = beats("The king ruled badly.", "The king taxed everyone.", "The king lost the war.", "The king fled at night.")
    assert any("opens with 'the king'" in w for _, w, _ in QL.problems(same))


def test_machine_sounding_words_and_long_beats():
    p = {i: w for i, w, _ in QL.problems(beats("Rome fell.", "It was a pivotal moment in the rich tapestry of history.", "x " * 45))}
    assert "pivotal" in p[1] and "words is a lot" in p[2]


def test_host_beats_are_not_story_and_numbers_are_never_touched():
    b = beats("Hey, I'm Sticky, welcome back!", "The empire fell in 476 AD after a very long and tired decline.", host=(0,))
    assert QL.problems(b) == []                                    # the host's greeting is allowed to be a greeting
    assert FL.keeps_facts("It fell in 476 AD.", "In 476 AD it finally fell.")


def test_notes_are_never_rewritten_but_are_reported():
    same_len = beats(*["The army marched along the river road today."] * 6)
    n = QL.notes(same_len)
    assert any(x["kind"] == "pacing" for x in n)
    names = beats("Rome fell.", "Then the army reached Przemysl and Szczecin.")
    assert any(x["kind"] == "pronounce" for x in QL.notes(names))


def test_the_fix_list_joins_flow_seams_and_quality_in_one_line_per_beat():
    b = beats(*[x["text"] for x in GOOD[:2]], "Sugar prices in Brazil doubled that spring and nobody noticed anything pivotal.", GOOD[3]["text"])
    items = dict(QL.fix_list(b))
    assert 2 in items and "doesn't pick up" in items[2] and "pivotal" in items[2] and ";" in items[2]
    assert QL.worth_asking([(2, "x")], b) is False                      # one ordinary problem is not worth a request
    assert QL.worth_asking([(0, "x")], beats("Hello and welcome everyone.", "Rome fell.", "It rose.", "It fell again.")) is True   # a bad opening is


def test_smooth_flow_asks_once_for_everything_and_only_flagged_beats(monkeypatch):
    from studio.pipeline import stages
    b = beats("Hello and welcome to a video about Rome.", "The army marched to the river and waited.", "Then the army marched to the river again.",
              "Soon the army marched to the river once more.", "Rome fell.")
    script = dict(title="Rome", beats=[dict(x) for x in b])
    calls = []

    class Ctx:
        project = None
        log = staticmethod(lambda m: None)
        warn = staticmethod(lambda m: None)
        progress = staticmethod(lambda *a, **k: None)

    def fake(ctx, llm, system, prompt, **kw):
        calls.append(prompt)
        return {"rewrites": [{"beat": 0, "text": "Rome was founded over a stolen goat, and that is only the start."},
                             {"beat": 3, "text": "By dawn the army had crossed the river and the siege began."},
                             {"beat": 4, "text": "Rome fell."}]}
    monkeypatch.setattr(stages, "call_llm", fake)

    class LLM:
        paid = False
    fixed = stages.smooth_flow(Ctx, LLM(), script)
    assert len(calls) == 1 and ">>> [0]" in calls[0] and ">>> [3]" in calls[0] and "greeting" in calls[0]
    assert fixed == [0, 3] and script["beats"][0]["text"].startswith("Rome was founded") and script["beats"][1]["text"] == b[1]["text"]
    assert clean_line("a — b") == "a, b"
