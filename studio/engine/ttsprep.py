"""Text normalization before TTS. Captions keep the original spelling; only the voice hears this version.

Works word by word so we can map TTS timing (when the provider gives it) back to the caption words.
"""
import re

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
PLURAL = {"twenty": "twenties", "thirty": "thirties", "forty": "forties", "fifty": "fifties", "sixty": "sixties",
          "seventy": "seventies", "eighty": "eighties", "ninety": "nineties", "hundred": "hundreds",
          "thousand": "thousands", "ten": "tens"}

DEFAULT_PRONUNCIATIONS = {
    "Manchukuo": "Man-choo-kwoh", "Meiji": "May-jee", "Leyte": "Lay-tee", "Nanjing": "Nahn-jing",
    "Mukden": "Mook-den", "Guadalcanal": "Gwah-dal-ka-nal", "Saipan": "Sigh-pan", "Marianas": "Mary-annas",
    "Hirohito": "Here-oh-hee-toe", "Yamamoto": "Yah-mah-moh-toh", "Iwo": "Ee-woh", "Okinawa": "Oh-kee-nah-wah",
}


def two(n):
    if n < 20:
        return ONES[n]
    t, o = divmod(n, 10)
    return TENS[t] + ("-" + ONES[o] if o else "")


def year(y):
    """1941 -> nineteen forty-one, 1905 -> nineteen oh five, 1900 -> nineteen hundred, 2003 -> two thousand three."""
    if 2000 <= y <= 2009:
        return "two thousand" + ("" if y == 2000 else " " + ONES[y - 2000])
    if y == 1000:
        return "one thousand"
    h, r = divmod(y, 100)
    if r == 0:
        return two(h) + " hundred"
    if r < 10:
        return two(h) + " oh " + ONES[r]
    return two(h) + " " + two(r)


def plural(words):
    last = words.split(" ")[-1]
    if "-" in last:
        head, tail = last.rsplit("-", 1)
        new = head + "-" + PLURAL.get(tail, tail + "s")
    else:
        new = PLURAL.get(last, last + "s")
    return " ".join(words.split(" ")[:-1] + [new])


_YEAR = re.compile(r"^(\W*)(1\d{3}|20\d{2})(s?)(\W*)$")
_SHORT_DECADE = re.compile(r"^(\W*)['’](\d)0s(\W*)$")
_RANGE = re.compile(r"^(\W*)(1\d{3}|20\d{2})[-–](\d{2}|\d{4})(\W*)$")
_PCT = re.compile(r"^(\W*)([\d.,]+)%(\W*)$")
SIMPLE = {"&": "and", "~": "about", "vs.": "versus", "vs": "versus", "BC": "B C", "BCE": "B C E", "AD": "A D",
          "CE": "C E", "WWII": "World War Two", "WW2": "World War Two", "WWI": "World War One", "WW1": "World War One",
          "e.g.": "for example", "etc.": "etcetera", "USSR": "U S S R", "Mr.": "Mister", "Dr.": "Doctor"}


def _core(w):
    m = re.match(r"^(\W*)(.*?)(\W*)$", w)
    return m.group(1), m.group(2), m.group(3)


def prep_word(w):
    m = _YEAR.match(w)
    if m:
        y = int(m.group(2))
        if 1000 <= y <= 2099:
            spoken = year(y)
            if m.group(3):
                spoken = plural(spoken)
            return m.group(1) + spoken + m.group(4)
    m = _SHORT_DECADE.match(w)
    if m:
        return m.group(1) + PLURAL[TENS[int(m.group(2))]] + m.group(3)
    m = _RANGE.match(w)
    if m:
        a = int(m.group(2))
        b = m.group(3)
        b = int(b) if len(b) == 4 else (a // 100) * 100 + int(b)
        return m.group(1) + year(a) + " to " + year(b) + m.group(4)
    m = _PCT.match(w)
    if m:
        return m.group(1) + m.group(2) + " percent" + m.group(3)
    pre, core, post = _core(w)
    if w in SIMPLE:
        return SIMPLE[w]
    if core in SIMPLE:
        return pre + SIMPLE[core] + post
    return w


def prep_words(text, pronunciations=None):
    """Return the spoken form of every whitespace-separated word of `text` ('' for words merged away)."""
    pron = dict(DEFAULT_PRONUNCIATIONS)
    if pronunciations:
        pron.update(pronunciations)
    words = (text or "").split()
    out = [prep_word(w) for w in words]
    lower = {k.lower(): v for k, v in pron.items()}
    multi = sorted([k for k in lower if " " in k], key=lambda k: -len(k.split()))
    i = 0
    while i < len(words):
        matched = False
        for key in multi:
            parts = key.split()
            if i + len(parts) <= len(words) and all(_core(words[i + k])[1].lower() == parts[k] for k in range(len(parts))):
                pre, _, _ = _core(words[i])
                _, _, post = _core(words[i + len(parts) - 1])
                out[i] = pre + lower[key] + post
                for k in range(1, len(parts)):
                    out[i + k] = ""
                i += len(parts)
                matched = True
                break
        if matched:
            continue
        pre, core, post = _core(out[i])
        # possessives: "Hirohito's" -> pronunciation + "'s"
        base, poss = (core[:-2], core[-2:]) if core.lower().endswith("'s") else (core, "")
        if base.lower() in lower:
            out[i] = pre + lower[base.lower()] + poss + post
        i += 1
    return out


def prep(text, pronunciations=None):
    return " ".join(w for w in prep_words(text, pronunciations) if w)


def word_times_from_alignment(text, pronunciations, chars, starts, ends):
    """Map per-character TTS alignment (of the spoken text) back to the original caption words.
    Returns [(start, end)] per original word, or None if the alignment doesn't line up."""
    spoken = prep_words(text, pronunciations)
    joined = "".join(chars)
    target = " ".join(w for w in spoken if w)
    if not chars or not starts:
        return None
    # alignment text may differ slightly (normalization). Walk both strings and match greedily.
    pos = 0
    spans = []
    for w in spoken:
        if not w:
            spans.append(None)
            continue
        idx = joined.find(w[: max(1, min(len(w), 4))], pos)
        if idx < 0:
            idx = pos
        end = min(len(joined), idx + len(w)) - 1
        spans.append((idx, max(idx, end)))
        pos = end + 1
    out = []
    last = 0.0
    for sp in spans:
        if sp is None or sp[0] >= len(starts):
            out.append((last, last))
            continue
        a = float(starts[sp[0]])
        b = float(ends[min(sp[1], len(ends) - 1)])
        out.append((a, max(a, b)))
        last = b
    if len(out) != len(text.split()):
        return None
    _ = target
    return out
