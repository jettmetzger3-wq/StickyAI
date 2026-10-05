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


MAKERS = {"fun": make_fun, "tense": make_tense, "somber": make_somber}


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
    return np.zeros(10)


SFX_GAIN = {"pop": 0.10, "whoosh": 0.10, "swish": 0.07, "boom": 0.22, "tick": 0.25}


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


def build_mix(voice_clips, scene_starts, scene_durs, moods, sfx_events, total, out_path, lead=0.15,
              music_beds=None, music_file=None, music_db=-13.0, use_sfx=True):
    """voice_clips: list of mono arrays @ SR, one per scene; sfx_events: [(abs_time, kind)].
    music_beds: optional {mood: array} (e.g. AI-generated tracks); music_file: one uploaded track for all moods."""
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for clip, st in zip(voice_clips, scene_starts):
        place(voice, clip, st + lead)
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
        level = {"fun": 0.55, "tense": 0.55, "somber": 0.45}
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
            if t - last < 0.12 and kind in ("pop", "swish"):
                continue
            place(fx, sfx(kind), t, SFX_GAIN.get(kind, 0.1))
            last = t
    mix = voice + music + fx
    fade = int(1.0 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= max(1.0, np.abs(mix).max() / 0.97)
    sf.write(out_path, mix[: int(total * SR)].astype(np.float32), SR)
    return out_path


def loudnorm(in_path, out_path, I=-15.0, TP=-1.5, LRA=11.0):
    """Two-pass ffmpeg loudnorm to -15 LUFS, true peak -1.5 dB."""
    first = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", in_path, "-af",
                            f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first.stderr, re.S)
    if m:
        st = json.loads(m.group(0))
        af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
              f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:"
              f"linear=true")
    else:
        af = f"loudnorm=I={I}:TP={TP}:LRA={LRA}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-af", af, "-ar", str(SR), out_path], check=True)
    return out_path
