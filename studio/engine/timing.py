"""Word timing inside a scene.

A scene lasts lead + speech + tail seconds. Word start times come either from real TTS alignment
(ElevenLabs returns per-character times) or are spread in proportion to character count.
"""
import re

LEAD, TAIL = 0.15, 0.32

_strip = re.compile(r"[^\w'%$-]+", re.UNICODE)


def norm_word(w):
    return _strip.sub("", w.lower()).strip("'-")


class WordTimer:
    def __init__(self, text, dur, lead=LEAD, tail=TAIL, word_times=None):
        """word_times: optional list of (start, end) seconds relative to the start of the speech audio,
        one entry per whitespace-separated word of `text`."""
        self.text = text or ""
        self.words = self.text.split()
        self.dur = float(dur)
        self.lead, self.tail = lead, tail
        self.speech = max(self.dur - lead - tail, 0.3)
        n = len(self.words)
        if word_times and len(word_times) == n and n:
            self.starts = [lead + float(a) for a, b in word_times]
            self.ends = [lead + float(b) for a, b in word_times]
        else:
            lens = [len(w) + 1 for w in self.words] or [1]
            total = float(sum(lens))
            acc, self.starts, self.ends = 0.0, [], []
            for L in lens:
                self.starts.append(lead + self.speech * acc / total)
                acc += L
                self.ends.append(lead + self.speech * acc / total)
        self.keys = [norm_word(w) for w in self.words]

    def find(self, phrase, nth=0):
        """Index of the first word of the nth occurrence of `phrase` (one or more words), or None."""
        target = [norm_word(p) for p in str(phrase).split() if norm_word(p)]
        if not target:
            return None
        hits = 0
        for i in range(len(self.keys) - len(target) + 1):
            ok = True
            for k, t in enumerate(target):
                w = self.keys[i + k]
                # prefix match allows "Britain" to hit "Britain's" and "war" to hit "wars"
                if not (w == t or (len(t) >= 3 and w.startswith(t))):
                    ok = False
                    break
            if ok:
                if hits == nth:
                    return i
                hits += 1
        # fall back to a substring search inside words (e.g. "oil" inside "oil-rich")
        for i, w in enumerate(self.keys):
            if target[0] in w:
                return i
        return None

    def word_time(self, phrase, nth=0):
        i = self.find(phrase, nth)
        if i is None:
            return None
        return self.starts[i]

    def frac(self, phrase, nth=0, default=0.0):
        t = self.word_time(phrase, nth)
        if t is None:
            return default
        return min(max(t / max(self.dur, 1e-3), 0.0), 0.97)

    def resolve(self, at, default=0.0):
        """Turn an `at` value into a fraction of the scene. Accepts 0..1 numbers, 'word:xxx',
        'word:xxx+0.3' (seconds offset) or {'word': 'xxx', 'offset': 0.3, 'nth': 1}."""
        if at is None:
            return default
        if isinstance(at, (int, float)):
            return min(max(float(at), 0.0), 0.98)
        word, off, nth = None, 0.0, 0
        if isinstance(at, dict):
            word = at.get("word")
            off = float(at.get("offset", 0) or 0)
            nth = int(at.get("nth", 0) or 0)
            if word is None and "at" in at:
                return self.resolve(at["at"], default)
        elif isinstance(at, str):
            s = at.strip()
            if s.lower().startswith("word:"):
                s = s[5:]
                m = re.match(r"^(.*?)([+-]\d+(?:\.\d+)?)s?$", s)
                if m and m.group(1).strip():
                    s, off = m.group(1), float(m.group(2))
                word = s.strip()
            else:
                try:
                    return min(max(float(s), 0.0), 0.98)
                except ValueError:
                    word = s
        if not word:
            return default
        t = self.word_time(word, nth)
        if t is None:
            return default
        return min(max((t + off) / max(self.dur, 1e-3), 0.0), 0.97)
