"""Procedural music (numpy), synthesized sound effects, and the final mix.

Performance rule learned the hard way: never np.convolve big kernels over long audio. Moving averages use
cumulative sums instead.
"""
import json
import os
import re
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter

SR = 44100
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


_ks_cache = {}


def ks(note, dur=1.6, decay=0.996, bright=0.5):
    """Karplus-Strong plucked string (ukulele-ish)."""
    key = (note, dur, decay, bright)
    if key in _ks_cache:
        return _ks_cache[key]
    f = midi(note)
    N = int(SR / f)
    n = int(dur * SR)
    buf = rng.uniform(-1, 1, N)
    buf = lfilter([bright, 1 - bright], [1], buf)
    out = np.zeros(n)
    out[:N] = buf
    for start in range(N, n, N):
        end = min(start + N, n)
        prev = out[start - N:end - N]
        prev2 = out[start - N + 1:end - N + 1]
        if len(prev2) < len(prev):
            prev2 = np.concatenate([prev2, prev2[-1:]])
        out[start:end] = decay * 0.5 * (prev + prev2)
    env = np.exp(-np.linspace(0, dur * 2.2, n))
    out = out * env
    out /= max(1e-9, np.abs(out).max())
    _ks_cache[key] = out
    return out


def sine_note(note, dur, harm=(1, 0.3, 0.12), decay=3.0, attack=0.005):
    t = np.arange(int(dur * SR)) / SR
    f = midi(note)
    s = sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harm))
    env = np.minimum(1, t / attack) * np.exp(-decay * t)
    return s * env


def pad_note(notes, dur, cutoff=1400):
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for n in notes:
        f = midi(n)
        for det in (-0.25, 0.0, 0.25):
            ph = 2 * np.pi * f * (2 ** (det / 12)) * t
            s += (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.3
    b, a = butter(2, cutoff / (SR / 2))
    s = lfilter(b, a, s)
    env = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.4)
    return s * env / max(len(notes), 1)


def noise_hit(dur=0.05, hp=6000):
    n = rng.normal(0, 1, int(dur * SR))
    b, a = butter(2, hp / (SR / 2), "high")
    n = lfilter(b, a, n)
    return n * np.exp(-np.linspace(0, 6, len(n)))


def place(track, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(track) or i < 0:
        return
    j = min(len(track), i + len(sig))
    track[i:j] += sig[: j - i] * gain


CHORDS_FUN = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]          # C G Am F
CHORDS_TENSE = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 56, 59]]        # Am F G E
CHORDS_SOMBER = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]       # Am F C G


def make_fun(total):
    bpm = 100
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR)
    bar, t = 0, 0.0
    pent = [72, 74, 76, 79, 81, 84]
    while t < total:
        ch = CHORDS_FUN[bar % 4]
        pattern = [1, 0, 1, 0.6, 0, 0.6, 1, 0.6]   # D . D U . U D U
        for k, v in enumerate(pattern):
            if v:
                for m, n in enumerate(ch + [ch[0] + 12]):
                    place(tr, ks(n + 12, 0.9, 0.994, 0.6), t + k * beat / 2 + m * 0.012, 0.11 * v)
        for k in (0, 2):
            place(tr, sine_note(ch[0] - 24, beat * 1.6, (1, 0.25), 3.2), t + k * beat, 0.32)
        for k in range(8):
            place(tr, noise_hit(0.05), t + k * beat / 2, 0.035 if k % 2 else 0.05)
        if bar % 2 == 1:
            for k in range(3):
                place(tr, sine_note(pent[rng.integers(len(pent))], 1.2, (1, 0.4, 0.2), 4.0), t + (k * 1.5 + 0.5) * beat, 0.06)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


def make_tense(total):
    bpm = 84
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR * 4)
    bar, t = 0, 0.0
    while t < total:
        ch = CHORDS_TENSE[bar % 4]
        place(tr, pad_note([n - 12 for n in ch], 4 * beat + 0.5, 900), t, 0.18)
        arp = [ch[0], ch[1], ch[2], ch[1]] * 2
        for k, n in enumerate(arp):
            place(tr, ks(n, 0.5, 0.985, 0.4), t + k * beat / 2, 0.09)
        place(tr, sine_note(ch[0] - 24, 0.6, (1, 0.1), 7.0), t, 0.45)
        place(tr, sine_note(ch[0] - 24, 0.6, (1, 0.1), 7.0), t + 2.5 * beat, 0.3)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


def make_somber(total):
    bpm = 60
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR * 6)
    bar, t = 0, 0.0
    while t < total:
        ch = CHORDS_SOMBER[bar % 4]
        place(tr, pad_note([n - 12 for n in ch], 4 * beat + 1.0, 700), t, 0.16)
        for k, n in enumerate((ch[0] + 12, ch[2] + 12, ch[1] + 12)):
            place(tr, sine_note(n, 3.0, (1, 0.35, 0.1), 1.3), t + k * 1.3 * beat, 0.07)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


# ---------------- more music styles: epic battle, mystery, triumph, sad
def brass(notes, dur, bright=2600, attack=0.04):
    """A brassy chord: detuned saws with a quick swell, low-passed."""
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for n in notes:
        f = midi(n)
        for det in (-0.12, 0.12):
            ph = f * (2 ** (det / 12)) * t
            s += (2 * (ph % 1) - 1) * 0.3
    b, a = butter(2, bright / (SR / 2))
    s = lfilter(b, a, s)
    env = np.minimum(1, t / attack) * (0.75 + 0.25 * np.exp(-t * 3)) * np.minimum(1, (dur - t) / 0.08)
    return s * env / max(len(notes), 1)


_drum_cache = {}


def drum(kind):
    """big low drum ("taiko"), timpani, snare."""
    if kind in _drum_cache:
        return _drum_cache[kind]
    if kind == "taiko":
        n = int(0.7 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * (48 + 40 * np.exp(-t * 18)) * t) * np.exp(-t * 6)
        x = rng.normal(0, 1, n)
        b, a = butter(2, 500 / (SR / 2))
        s += lfilter(b, a, x) * np.exp(-t * 30) * 0.5
    elif kind == "timpani":
        n = int(1.4 * SR)
        t = np.arange(n) / SR
        s = (np.sin(2 * np.pi * 98 * t) + 0.5 * np.sin(2 * np.pi * 147 * t)) * np.exp(-t * 3.2)
    else:  # snare
        n = int(0.18 * SR)
        t = np.arange(n) / SR
        x = rng.normal(0, 1, n)
        b, a = butter(2, [1500 / (SR / 2), 8000 / (SR / 2)], "band")
        s = lfilter(b, a, x) * np.exp(-t * 28) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 40) * 0.5
    s = s / max(1e-9, np.abs(s).max())
    _drum_cache[kind] = s
    return s


CHORDS_EPIC = [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]]          # Dm Bb F C
CHORDS_MYSTERY = [[57, 60, 64], [56, 60, 64], [53, 57, 60], [52, 55, 59]]       # Am Aaug F Em
CHORDS_TRIUMPH = [[60, 64, 67], [65, 69, 72], [67, 71, 74], [60, 64, 67]]       # C F G C
CHORDS_SAD = [[57, 60, 64], [52, 55, 59], [53, 57, 60], [48, 52, 55]]           # Am Em F C


def make_epic(total):
    bpm = 128
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR * 3)
    bar, t = 0, 0.0
    while t < total:
        ch = CHORDS_EPIC[bar % 4]
        place(tr, brass([n - 12 for n in ch] + [ch[0]], 4 * beat + 0.1, 1800, 0.25), t, 0.22)
        root, fifth = ch[0] - 12, ch[2] - 12
        for k, n in enumerate((root, root, fifth, root, root, fifth, ch[0], fifth)):     # staccato strings
            place(tr, sine_note(n + 12, 0.16, (1, 0.5, 0.33, 0.25), 16), t + k * beat / 2, 0.11)
        for k, g in ((0, 0.6), (1.5, 0.35), (2, 0.5), (3, 0.3), (3.5, 0.3)):            # war drums
            place(tr, drum("taiko"), t + k * beat, g)
        if bar % 4 == 3:
            sw = _noise(int(4 * beat * SR), 3000, 9000) * np.linspace(0, 1, int(4 * beat * SR)) ** 2
            place(tr, sw, t, 0.07)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


def make_mystery(total):
    bpm = 70
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR * 6)
    bar, t = 0, 0.0
    r = np.random.default_rng(11)
    while t < total:
        ch = CHORDS_MYSTERY[bar % 4]
        place(tr, pad_note([45, 52], 4 * beat + 1.0, 450), t, 0.2)                     # low drone
        place(tr, ks(ch[0] - 12, 0.6, 0.98, 0.3), t, 0.1)                               # pizzicato
        place(tr, ks(ch[2] - 12, 0.6, 0.98, 0.3), t + 2 * beat, 0.08)
        for k in range(3):                                                              # music-box bells
            if r.random() < 0.7:
                n = ch[int(r.integers(3))] + 24
                place(tr, sine_note(n, 2.2, (1, 0, 0.45, 0, 0.2), 2.4), t + (k * 1.25 + 0.5) * beat, 0.05)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


def make_triumph(total):
    bpm = 112
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR * 3)
    bar, t = 0, 0.0
    melody = [[72, 76, 79, 76], [77, 81, 84, 81], [79, 83, 86, 83], [84, 79, 76, 72]]
    while t < total:
        ch = CHORDS_TRIUMPH[bar % 4]
        for k, d in ((0, 0.75), (0.75, 0.25), (1, 1.0), (2.5, 0.5), (3, 1.0)):          # da-da-DAA fanfare rhythm
            place(tr, brass([n - 12 for n in ch], d * beat + 0.05, 3000), t + k * beat, 0.2)
        for k, n in enumerate(melody[bar % 4]):
            place(tr, sine_note(n, beat * 0.95, (1, 0.6, 0.4, 0.2), 2.0, 0.01), t + k * beat, 0.07)
        place(tr, drum("timpani"), t, 0.4)
        place(tr, drum("timpani"), t + 2 * beat, 0.25)
        if bar % 2 == 1:
            for k in range(8):
                place(tr, drum("snare"), t + 3 * beat + k * beat / 8, 0.05 + 0.02 * k)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


def make_sad(total):
    bpm = 66
    beat = 60 / bpm
    tr = np.zeros(int(total * SR) + SR * 6)
    bar, t = 0, 0.0
    melody = [[76, 74, 72, None], [71, 72, 74, 71], [72, 69, None, 72], [71, 67, None, None]]
    while t < total:
        ch = CHORDS_SAD[bar % 4]
        place(tr, pad_note([ch[0] - 24, ch[0] - 12], 4 * beat + 1.0, 800), t, 0.22)    # cello
        place(tr, pad_note([n for n in ch], 4 * beat + 1.0, 1100), t, 0.09)
        for k, n in enumerate(melody[bar % 4]):                                         # piano
            if n:
                place(tr, sine_note(n, 2.5, (1, 0.5, 0.25, 0.12), 1.6), t + k * beat, 0.08)
        t += 4 * beat
        bar += 1
    return tr[: int(total * SR)]


MAKERS = {"fun": make_fun, "tense": make_tense, "somber": make_somber, "epic": make_epic, "mystery": make_mystery,
          "triumph": make_triumph, "sad": make_sad}
MUSIC_STYLES = tuple(MAKERS)
BASE_MOOD = {"epic": "tense", "mystery": "tense", "triumph": "fun", "sad": "somber"}

STYLE_WORDS = {
    "epic": ("battle", "war ", "attack", "charge", "invade", "invaded", "invasion", "siege", "army", "armies",
             "troops", "cannon", "marched", "fought", "fight", "clash", "bombard", "soldiers", "cavalry"),
    "mystery": ("secret", "mystery", "mysterious", "spy", "spies", "disappeared", "vanished", "unknown", "hidden",
                "conspiracy", "plot", "legend", "curse", "nobody knows", "no one knows", "strange", "rumor"),
    "triumph": ("won", "victory", "victorious", "triumph", "conquered", "crowned", "glory", "celebrated",
                "succeeded", "independence", "liberated", "freedom", "champion", "greatest"),
    "sad": ("lonely", "alone", "exile", "exiled", "heartbroken", "abandoned", "forgotten", "starved", "orphan",
            "never saw", "goodbye"),
}


def _has(text, words):
    low = " " + str(text or "").lower() + " "
    return any((" " + w) in low for w in words)


def music_style(text, mood, scene=None):
    """Which music plays under a beat: the mood, made more specific by what's happening."""
    els = [e.get("type") for e in ((scene or {}).get("elements") or []) if isinstance(e, dict)]
    battle_scene = any(t in ("battle", "front") for t in els) or \
        any(isinstance(e, dict) and e.get("type") == "prop" and e.get("do") for e in (scene or {}).get("elements") or [])
    if mood == "somber":
        return "sad" if _has(text, STYLE_WORDS["sad"]) else "somber"
    if _has(text, STYLE_WORDS["triumph"]) and not _has(text, ("lost", "defeat")):
        return "triumph"
    if mood == "tense" and (battle_scene or _has(text, STYLE_WORDS["epic"])):
        return "epic"
    if mood == "tense" and _has(text, STYLE_WORDS["mystery"]):
        return "mystery"
    return mood if mood in MAKERS else "fun"


def smooth_styles(styles, durs, min_len=6.0):
    """Don't switch music for one short beat: a style lasting under min_len seconds between two beats of the
    same style takes theirs."""
    out = list(styles)
    i = 0
    while i < len(out):
        j = i
        while j + 1 < len(out) and out[j + 1] == out[i]:
            j += 1
        run = sum(durs[i:j + 1])
        if run < min_len and 0 < i and j + 1 < len(out) and out[i - 1] == out[j + 1]:
            for k in range(i, j + 1):
                out[k] = out[i - 1]
        i = j + 1
    return out


# ---------------- stings: short musical hits on big moments
STINGS = {
    "triumph": ("won", "victory", "victorious", "triumph", "conquered", "crowned", "independence", "liberated"),
    "reveal": ("but then", "suddenly", "betrayed", "turns out", "turned out", "secretly", "little did", "plot twist",
               "until one day", "however"),
    "fail": ("failed", "disaster", "catastrophe", "oops", "flopped", "went wrong", "embarrassing", "bankrupt",
             "humiliat", "fiasco"),
    "war": ("declared war", "war broke out", "invaded", "invasion began", "the battle began", "attacked"),
}


def find_sting(text, mood):
    """(kind, trigger word) for the beat, or None. No stings in sad moments."""
    if mood == "somber":
        return None
    low = " " + str(text or "").lower() + " "
    for kind in ("reveal", "war", "triumph", "fail"):
        if kind == "fail" and mood != "fun":
            continue
        for w in STINGS[kind]:
            if (" " + w) in low:
                return kind, w.split()[0]
    return None


def sting(kind):
    """A 1-2 second musical hit."""
    out = np.zeros(int(2.4 * SR))
    if kind == "triumph":
        place(out, brass([55, 59, 62], 0.22, 3200), 0.0, 0.8)
        place(out, brass([60, 64, 67, 72], 1.5, 3400), 0.24, 1.0)
        place(out, drum("timpani"), 0.24, 0.6)
    elif kind == "reveal":                     # dun dun DUNNN
        for k, (notes, d) in enumerate((([45, 52], 0.22), ([46, 53], 0.22), ([44, 51], 1.6))):
            place(out, brass(notes, d, 1500, 0.02), k * 0.3, 1.0)
        place(out, drum("timpani"), 0.6, 0.8)
    elif kind == "fail":                       # sad trombone: wah wah wah wahhh
        for k, (n, d) in enumerate(((58, 0.3), (57, 0.3), (56, 0.3), (55, 1.1))):
            tt = np.arange(int(d * SR)) / SR
            f = midi(n) * (1 + (0.02 * np.sin(2 * np.pi * 6 * tt) if k == 3 else 0))
            ph = np.cumsum(f) / SR
            s = (2 * (ph % 1) - 1)
            b, a = butter(2, 900 / (SR / 2))
            s = lfilter(b, a, s) * np.minimum(1, tt / 0.03) * np.minimum(1, (d - tt) / 0.06)
            place(out, s, k * 0.34, 0.9)
    elif kind == "war":
        place(out, drum("taiko"), 0.0, 1.0)
        place(out, brass([38, 45, 50, 53], 1.4, 1600, 0.01), 0.0, 1.0)
    return out / max(1e-9, np.abs(out).max())


# ---------------- sfx
def sfx(kind):
    if kind == "pop":
        n = int(0.08 * SR)
        t = np.arange(n) / SR
        f = 700 * np.exp(-t * 18) + 250
        ph = 2 * np.pi * np.cumsum(f) / SR
        return np.sin(ph) * np.exp(-t * 45) * 0.9
    if kind in ("whoosh", "swish"):
        d = 0.35 if kind == "whoosh" else 0.22
        n = int(d * SR)
        x = rng.normal(0, 1, n)
        out = np.zeros(n)
        seg = n // 8
        for k in range(8):
            fc = 600 + 2600 * (k / 7 if kind == "swish" else np.sin(np.pi * k / 7))
            b, a = butter(2, [max(100, fc * 0.6) / (SR / 2), min(fc * 1.4, SR / 2 - 100) / (SR / 2)], "band")
            out[k * seg:(k + 1) * seg] = lfilter(b, a, x[k * seg:(k + 1) * seg])
        env = np.sin(np.linspace(0, np.pi, n)) ** 2
        return out * env * 0.8
    if kind == "boom":
        n = int(1.2 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * (55 * np.exp(-t * 1.5) + 30) * t) * np.exp(-t * 3.0)
        x = rng.normal(0, 1, n)
        b, a = butter(2, 300 / (SR / 2))
        s += lfilter(b, a, x) * np.exp(-t * 4) * 0.8
        return s / np.abs(s).max() * 0.9
    if kind == "tick":
        out = np.zeros(int(2.0 * SR))
        for k in range(4):
            place(out, noise_hit(0.02, 3000), k * 0.5)
        return out / max(1e-9, np.abs(out).max()) * 0.6
    if kind == "tick1":
        x = noise_hit(0.018, 3500)
        return x / max(1e-9, np.abs(x).max()) * 0.6
    if kind in ("step", "step_soft"):
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        x = rng.normal(0, 1, n)
        b, a = butter(2, (500 if kind == "step" else 350) / (SR / 2))
        s = lfilter(b, a, x) * np.exp(-t * 55) + np.sin(2 * np.pi * 90 * t) * np.exp(-t * 60) * 0.6
        return s / max(1e-9, np.abs(s).max()) * (0.8 if kind == "step" else 0.5)
    if kind == "jump":
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        f = 260 + 900 * t / 0.22
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.22)
        return s * 0.7
    if kind == "thud":
        n = int(0.4 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * (70 * np.exp(-t * 6) + 40) * t) * np.exp(-t * 10)
        x = rng.normal(0, 1, n)
        b, a = butter(2, 400 / (SR / 2))
        s += lfilter(b, a, x) * np.exp(-t * 25) * 0.6
        return s / max(1e-9, np.abs(s).max()) * 0.9
    if kind == "cheer":
        n = int(1.6 * SR)
        t = np.arange(n) / SR
        out = np.zeros(n)
        for k in range(6):                      # a few voices: noisy vowels with their own pitch wobble
            x = rng.normal(0, 1, n)
            fc = rng.uniform(700, 1600)
            b, a = butter(2, [fc * 0.7 / (SR / 2), fc * 1.3 / (SR / 2)], "band")
            am = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(3, 7) * t + rng.uniform(0, 6))
            out += lfilter(b, a, x) * am
        env = np.minimum(1, t / 0.15) * np.exp(-np.maximum(0, t - 0.5) * 2.2)
        return out / max(1e-9, np.abs(out).max()) * env * 0.9
    if kind.startswith("sting:"):
        return sting(kind.split(":", 1)[1])
    if kind == "rumble":
        n = int(2.4 * SR)
        t = np.arange(n) / SR
        s = _noise(n, 30, 220) * np.minimum(1, t / 0.08) * np.exp(-t * 1.4)
        for k in range(7):                          # stones knocking
            place(s, noise_hit(0.03, 900) * rng.uniform(0.3, 0.7), rng.uniform(0.1, 1.6))
        return s / max(1e-9, np.abs(s).max()) * 0.9
    if kind == "splash":
        n = int(2.2 * SR)
        t = np.arange(n) / SR
        s = _noise(n, 300, 4000) * np.exp(-t * 3.5) * 0.8
        for k in range(14):                         # glugs
            place(s, _chirp(rng.uniform(250, 420), rng.uniform(500, 900), 0.06) * 0.5, 0.6 + k * 0.1)
        return s / max(1e-9, np.abs(s).max()) * 0.8
    if kind == "clang":
        n = int(0.7 * SR)
        t = np.arange(n) / SR
        s = sum(np.sin(2 * np.pi * f0 * t) * np.exp(-t * d) * g
                for f0, d, g in ((1840, 7, 1.0), (2630, 9, 0.7), (3790, 12, 0.5), (5110, 16, 0.35)))
        hit = noise_hit(0.01, 5000)
        s[:len(hit)] += hit * 0.6
        return s / max(1e-9, np.abs(s).max()) * 0.8
    if kind == "thunder":
        n = int(2.6 * SR)
        t = np.arange(n) / SR
        crack = _noise(n, 300, 3000) * np.exp(-t * 9) * 0.7
        rumble = _noise(n, 25, 160) * (np.minimum(1, t / 0.25) * np.exp(-np.maximum(0, t - 0.3) * 1.3))
        rumble *= 0.75 + 0.25 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * 0.9 * t + 1)
        s = crack + rumble * 1.2
        return s / max(1e-9, np.abs(s).max()) * 0.95
    if kind.startswith("blip"):
        # one "syllable" of cartoon talk: a short vowel-ish tone, pitch from the character
        try:
            hz = float(kind.split(":")[1])
        except (IndexError, ValueError):
            hz = 330.0
        hz *= rng.uniform(0.88, 1.15)
        n = int(rng.uniform(0.05, 0.085) * SR)
        t = np.arange(n) / SR
        ph = 2 * np.pi * hz * t
        s = np.sign(np.sin(ph)) * 0.35 + np.sin(ph) * 0.65 + 0.3 * np.sin(2 * ph + 0.5)
        env = np.minimum(1, t / 0.006) * np.minimum(1, (t[-1] - t + 1e-4) / 0.02)
        return s * env * 0.7
    return np.zeros(10)


SFX_GAIN = {"pop": 0.10, "whoosh": 0.10, "swish": 0.07, "boom": 0.22, "tick": 0.25, "tick1": 0.12, "step": 0.05,
            "step_soft": 0.035, "jump": 0.05, "thud": 0.16, "cheer": 0.10, "blip": 0.028, "thunder": 0.2, "rumble": 0.2,
            "splash": 0.14, "clang": 0.09, "sting": 0.16}


# ---------------- ambience (a quiet bed of sound for each kind of place)
def _noise(n, lo, hi):
    x = rng.normal(0, 1, n)
    if lo and hi:
        b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], "band")
    elif hi:
        b, a = butter(2, hi / (SR / 2))
    else:
        b, a = butter(2, lo / (SR / 2), "high")
    y = lfilter(b, a, x)
    return y / max(1e-9, np.abs(y).max())


def _events(out, sig_fn, every, jitter=0.5):
    t = rng.uniform(0, every)
    while t < len(out) / SR:
        place(out, sig_fn(), t)
        t += every * rng.uniform(1 - jitter, 1 + jitter)


def _mixed(parts):
    """Sum signals that start at different times: parts = [(seconds, signal), ...]."""
    n = max(int(t0 * SR) + len(s) for t0, s in parts)
    out = np.zeros(n)
    for t0, s in parts:
        a = int(t0 * SR)
        out[a:a + len(s)] += s
    return out


def _chirp(f0, f1, d):
    n = int(d * SR)
    t = np.arange(n) / SR
    f = f0 + (f1 - f0) * t / d
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2


def make_ambience(kind, seconds=16.0):
    """A loopable ambience bed, peak about 1.0."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    slow = lambda f, ph=0: 0.5 + 0.5 * np.sin(2 * np.pi * f * t + ph)
    if kind in ("waves", "harbor"):
        swell = slow(1 / 8.0) ** 2 * 0.8 + 0.2
        out += _noise(n, 150, 1800) * swell
        if kind == "harbor":
            _events(out, lambda: _mixed([(0, _chirp(1500, 900, 0.35) * 0.25), (0.4, _chirp(1400, 800, 0.3) * 0.2)]), 5.0)
    elif kind == "wind":
        out += _noise(n, 200, 900) * (0.4 + 0.6 * slow(1 / 6.0) * slow(1 / 2.3, 1.0))
    elif kind == "birds":
        out += _noise(n, 200, 800) * 0.25 * slow(1 / 7.0)
        _events(out, lambda: _mixed([(k * 0.09, _chirp(rng.uniform(2500, 4200), rng.uniform(3000, 5200), 0.07) * 0.25)
                                     for k in range(int(rng.integers(2, 5)))]), 1.6)
    elif kind == "jungle":
        out += _noise(n, 5000, 7500) * 0.18 * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 14 * t)))
        _events(out, lambda: _chirp(rng.uniform(1800, 3500), rng.uniform(2500, 4500), rng.uniform(0.08, 0.2)) * 0.3, 0.8)
        out += _noise(n, 80, 300) * 0.2
    elif kind in ("street", "crowd", "city", "room"):
        level = {"street": 1.0, "crowd": 1.3, "city": 0.6, "room": 0.35}[kind]
        for k in range(5):                        # murmuring voices
            am = np.clip(np.sin(2 * np.pi * rng.uniform(2.5, 5) * t + rng.uniform(0, 6)), 0, None) * slow(1 / rng.uniform(3, 7), k)
            out += _noise(n, rng.uniform(250, 500), rng.uniform(900, 1600)) * am * 0.3 * level
        if kind == "city":
            out += _noise(n, 40, 200) * 0.5
    elif kind == "battle":
        out += _noise(n, 30, 160) * 0.5
        _events(out, lambda: sfx("boom") * 0.5, 3.0)
        _events(out, lambda: noise_hit(0.03, 1500) * 0.6, 0.35, 0.9)
    elif kind == "underwater":
        out += _noise(n, 30, 250) * 0.6 * (0.6 + 0.4 * slow(1 / 5.0))
        _events(out, lambda: _chirp(300, rng.uniform(700, 1200), 0.06) * 0.4, 0.6, 0.9)
    elif kind == "space":
        out += (np.sin(2 * np.pi * 55 * t) + np.sin(2 * np.pi * 55.4 * t) + 0.5 * np.sin(2 * np.pi * 82.5 * t)) * 0.25
        out += _noise(n, 100, 400) * 0.15
    elif kind == "night":
        crick = (np.sin(2 * np.pi * 4500 * t) * (np.sin(2 * np.pi * 30 * t) > 0.3) * (np.sin(2 * np.pi * 0.7 * t) > 0))
        out += crick * 0.25 + _noise(n, 150, 600) * 0.15
    elif kind == "storm":
        out += _noise(n, 1500, 9000) * 0.5 + _noise(n, 60, 300) * 0.3
        _events(out, lambda: sfx("boom") * 0.6, 6.0)
    elif kind == "rain":
        out += _noise(n, 1200, 8000) * 0.55 * (0.85 + 0.15 * slow(1 / 5.0)) + _noise(n, 100, 500) * 0.12
        _events(out, lambda: noise_hit(0.012, 4000) * 0.35, 0.05, 0.9)
    elif kind == "fire":
        out += _noise(n, 100, 600) * 0.3
        _events(out, lambda: noise_hit(0.01, 2500) * 0.8, 0.12, 0.9)
    else:
        return np.zeros(n)
    # make it loop smoothly
    xf = int(1.0 * SR)
    out[:xf] = out[:xf] * np.linspace(0, 1, xf) + out[-xf:] * np.linspace(1, 0, xf)
    out = out[:-xf]
    return out / max(1e-9, np.abs(out).max())


AMBIENCE_FOR = {"sea": "waves", "beach": "waves", "harbor": "harbor", "underwater": "underwater", "street": "street",
                "city": "city", "palace": "room", "interior": "room", "field": "birds", "hills": "birds",
                "mountains": "wind", "snow": "wind", "desert": "wind", "jungle": "jungle", "battlefield": "battle",
                "trench": "battle", "space": "space", "night": "night"}


WEATHER_AMBIENCE = {"rain": "rain", "storm": "storm", "snow": "wind", "blizzard": "wind", "fog": "wind",
                    "ash": "fire"}


def ambience_kind(scene):
    """The ambience for a scene from its weather or background (and time of day); None for maps and plain pages."""
    bg = (scene or {}).get("bg") or {}
    t = bg.get("type")
    w = (scene or {}).get("weather")
    w = (w.get("type") if isinstance(w, dict) else w) or None
    if w:
        from .weather import norm_weather
        wk = WEATHER_AMBIENCE.get(norm_weather(w))
        if wk:
            return wk
    kind = AMBIENCE_FOR.get(t)
    if bg.get("time") == "storm" and t not in ("interior", "palace", "space", "underwater"):
        return "storm"
    if bg.get("time") == "night" and kind in ("birds", "wind"):
        return "night"
    return kind


def movavg(x, k):
    """Moving average via cumulative sums (O(n), safe on 10+ minute audio)."""
    k = max(1, int(k))
    if len(x) <= k:
        return np.full(len(x), float(np.mean(x)) if len(x) else 0.0)
    c = np.cumsum(np.concatenate([[0.0], x]))
    out = (c[k:] - c[:-k]) / k
    pad = len(x) - len(out)
    return np.concatenate([np.full(pad // 2, out[0]), out, np.full(pad - pad // 2, out[-1])])


def load_audio(path, sr=SR):
    """Decode any audio file (mp3, wav, m4a...) to mono float32 at `sr` using ffmpeg."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "a.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(sr), out], check=True)
        x, _ = sf.read(out, dtype="float32")
    return x.astype(np.float64)


def loop_to(x, n, xf=int(1.5 * SR)):
    """Loop a track to n samples with a short crossfade at each seam."""
    if len(x) == 0:
        return np.zeros(n)
    if len(x) >= n:
        return x[:n].copy()
    xf = min(xf, len(x) // 4)
    step = len(x) - xf
    fade_in = np.ones(len(x))
    fade_out = np.ones(len(x))
    if xf:
        fade_in[:xf] = np.linspace(0, 1, xf)
        fade_out[-xf:] = np.linspace(1, 0, xf)
    out = np.zeros(n + len(x))
    pos, first = 0, True
    while pos < n:
        seg = x * fade_out if first else x * fade_out * fade_in
        out[pos:pos + len(x)] += seg
        pos += step
        first = False
    return out[:n]


def polish_voice(x):
    """Broadcast-style narration: cut the rumble below 80 Hz, add a little presence around 2.5-5 kHz (clearer
    words), and even out the level with a gentle compressor (3:1 above -20 dB, smooth attack and release)."""
    if len(x) < SR // 10 or not np.any(x):
        return x
    b, a = butter(2, 80 / (SR / 2), "high")
    y = lfilter(b, a, x)
    b, a = butter(2, [2500 / (SR / 2), 5000 / (SR / 2)], "band")
    y = y + lfilter(b, a, y) * 0.3
    peak = max(1e-9, np.abs(y).max())
    y = y / peak
    env = np.sqrt(movavg(y * y, int(0.02 * SR)) + 1e-12)
    thr, ratio = 10 ** (-20 / 20), 3.0
    gain = np.where(env > thr, (thr / env) ** (1 - 1 / ratio), 1.0)
    gain = movavg(gain, int(0.05 * SR))              # no pumping: the gain moves slowly
    y = y * gain
    return y / max(1e-9, np.abs(y).max())


def build_mix(voice_clips, scene_starts, scene_durs, moods, sfx_events, total, out_path, lead=0.15,
              music_beds=None, music_file=None, music_db=-13.0, use_sfx=True, ambiences=None, ambience_db=-25.0,
              talk_blips=True, action_sounds=True, voice_polish=True):
    """voice_clips: list of mono arrays @ SR, one per scene; sfx_events: [(abs_time, kind)].
    music_beds: optional {mood: array} (e.g. AI-generated tracks); music_file: one uploaded track for all moods."""
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for clip, st in zip(voice_clips, scene_starts):
        place(voice, clip, st + lead)
    if voice_polish:
        voice = polish_voice(voice)
    voice *= 0.85 / max(1e-6, np.abs(voice).max())
    # music beds with ~1.2 s crossfades when the mood changes
    if music_file:
        bed = loop_to(load_audio(music_file), n)
        music = bed / max(1e-6, np.abs(bed).max())
    else:
        used = sorted(set(moods)) or ["fun"]
        beds = {}
        for m in used:
            if music_beds and music_beds.get(m) is not None:
                beds[m] = loop_to(np.asarray(music_beds[m], dtype=np.float64), n)
            else:
                beds[m] = MAKERS.get(m, make_fun)(total + 2)
        gains = {k: np.zeros(n) for k in beds}
        for st, d, m in zip(scene_starts, scene_durs, moods):
            a, b = int(st * SR), int((st + d) * SR)
            gains[m if m in gains else used[0]][a:b] = 1.0
        xf = int(1.2 * SR)
        music = np.zeros(n)
        level = {"fun": 0.55, "tense": 0.55, "somber": 0.45, "epic": 0.6, "mystery": 0.5, "triumph": 0.6,
                 "sad": 0.45}
        for k, bed in beds.items():
            g = movavg(gains[k], xf)
            L = min(n, len(bed))
            bnorm = bed / max(1e-6, np.abs(bed).max())
            music[:L] += bnorm[:L] * g[:L] * level.get(k, 0.5)
        music /= max(1e-6, np.abs(music).max())
    # music sits ~10-15 dB under the voice, with light ducking while someone talks
    env = movavg(np.abs(voice), int(0.3 * SR))
    duck = 1 - 0.35 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    music = music * (10 ** (music_db / 20)) * 0.85 * duck
    fx = np.zeros(n)
    if use_sfx:
        last = -1
        for t, kind in sorted(sfx_events):
            if kind.startswith("blip"):
                if talk_blips:
                    place(fx, sfx(kind), t, SFX_GAIN["blip"])
                continue
            if kind in ("step", "step_soft", "jump", "thud", "cheer") and not action_sounds:
                continue
            if t - last < 0.12 and kind in ("pop", "swish"):
                continue
            place(fx, sfx(kind), t, SFX_GAIN.get(kind.split(":")[0], 0.1))
            last = t
    # ambience: a quiet bed of sound for each place, crossfaded between scenes and ducked under the voice
    amb = np.zeros(n)
    if ambiences:
        beds = {}
        gains = {}
        for st, d, k in zip(scene_starts, scene_durs, ambiences):
            if not k:
                continue
            if k not in beds:
                beds[k] = loop_to(make_ambience(k), n)
                gains[k] = np.zeros(n)
            gains[k][int(st * SR):int((st + d) * SR)] = 1.0
        for k, bed in beds.items():
            amb += bed[:n] * movavg(gains[k], int(0.8 * SR))
        amb *= (10 ** (ambience_db / 20)) * (1 - 0.4 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1))
    mix = voice + music + fx + amb
    fade = int(1.0 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    sf.write(out_path, mix[: int(total * SR)].astype(np.float32), SR)
    return out_path


def measure_lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s*(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def loudnorm(in_path, out_path, I=-15.0, TP=-1.5, LRA=11.0):
    """Normalize to -15 LUFS, true peak -1.5 dB. First try a clean two-pass linear gain; if peaks stop that
    from reaching the target (more than 0.7 LU short), fall back to ffmpeg's dynamic mode."""
    first = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", in_path, "-af",
                            f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first.stderr, re.S)
    if m:
        st = json.loads(m.group(0))
        af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
              f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:"
              f"linear=true")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-af", af, "-ar", str(SR), out_path], check=True)
        got = measure_lufs(out_path)
        if got is not None and abs(got - I) <= 0.7:
            return out_path
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-af", f"loudnorm=I={I}:TP={TP}:LRA={LRA}",
                    "-ar", str(SR), out_path], check=True)
    return out_path
