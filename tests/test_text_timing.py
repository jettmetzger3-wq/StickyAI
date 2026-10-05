from studio.engine.captions import chunk_words, caption_timings, make_captions
from studio.engine.timing import WordTimer, LEAD, TAIL
from studio.engine.ttsprep import year, prep, prep_words, word_times_from_alignment


# ------------------------------------------------------------------ captions
def test_chunks_have_at_most_7_words_and_split_on_punctuation():
    text = ("December 1941. Japan, a country a bit smaller than California, declares war on the United States, "
            "an industrial giant that can outbuild it many times over.")
    words = text.split()
    chunks = chunk_words(words)
    assert all(len(c) <= 8 for c in chunks)  # 7 + a merged 1-word tail at most
    assert sum(len(c) for c in chunks) == len(words)
    first = [words[i] for i in chunks[0]]
    assert first == ["December", "1941."]  # sentence end breaks the chunk


def test_caption_timing_is_proportional_and_covers_the_speech():
    text = "one two three four five six seven. eight nine ten eleven twelve thirteen fourteen."
    dur = 6.0
    caps = caption_timings(text, dur)
    assert abs(caps[0][0] - LEAD) < 1e-6
    assert abs(caps[-1][1] - dur) < 1e-6
    for (a0, a1, _), (b0, b1, _) in zip(caps, caps[1:]):
        assert abs(a1 - b0) < 1e-6 and a1 > a0
    # equal character counts -> roughly equal durations
    d0 = caps[0][1] - caps[0][0]
    d1 = caps[1][0] - caps[0][0]
    assert abs(d0 - d1) < 1e-6


def test_caption_timing_uses_real_word_times_when_given():
    text = "Rome falls fast"
    wt = [(0.0, 0.4), (1.0, 1.4), (2.0, 2.5)]
    t = WordTimer(text, 3.5, word_times=wt)
    assert abs(t.starts[1] - (LEAD + 1.0)) < 1e-9
    assert abs(t.word_time("fast") - (LEAD + 2.0)) < 1e-9


def test_caption_images_render():
    caps = make_captions("Hello there, general Kenobi. You are a bold one.", 4.0)
    assert caps and all(im.mode == "RGBA" and im.width < 1920 for _, _, im in caps)


# ------------------------------------------------------------------ year normalization
def test_years():
    assert year(1941) == "nineteen forty-one"
    assert year(1905) == "nineteen oh five"
    assert year(1900) == "nineteen hundred"
    assert year(2003) == "two thousand three"
    assert year(2019) == "twenty nineteen"
    assert year(1066) == "ten sixty-six"


def test_prep_text():
    assert prep("December 7th, 1941.") == "December 7th, nineteen forty-one."
    assert prep("the 1930s") == "the nineteen thirties"
    assert prep("in the 1900s") == "in the nineteen hundreds"
    assert prep("the '60s") == "the sixties"
    assert prep("from 1939-45") == "from nineteen thirty-nine to nineteen forty-five"
    assert prep("80% of its oil") == "80 percent of its oil"
    assert "Man-choo-kwoh" in prep("a puppet state called Manchukuo.")
    assert prep("Hirohito's palace") == "Here-oh-hee-toe's palace"
    assert prep("Rome in 476 AD") == "Rome in 476 A D"


def test_custom_and_multiword_pronunciations_keep_word_mapping():
    pron = {"Pearl Harbor": "Purl Harbor", "Leyte": "Lay-tee"}
    words = prep_words("Attack on Pearl Harbor, then Leyte.", pron)
    assert words == ["Attack", "on", "Purl Harbor,", "", "then", "Lay-tee."]


def test_word_times_from_alignment():
    text = "In 1941 Japan"
    spoken = prep(text)  # "In nineteen forty-one Japan"
    chars = list(spoken)
    starts = [i * 0.05 for i in range(len(chars))]
    ends = [s + 0.05 for s in starts]
    wt = word_times_from_alignment(text, None, chars, starts, ends)
    assert len(wt) == 3
    assert wt[0][0] == 0.0
    assert abs(wt[2][0] - spoken.index("Japan") * 0.05) < 1e-9
