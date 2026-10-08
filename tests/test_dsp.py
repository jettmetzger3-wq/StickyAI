"""The signal-processing stand-ins: the numpy-only versions agree with scipy, and the studio still starts when Windows blocks
scipy's compiled stats file ("DLL load failed while importing _stats_pythran: An Application Control policy has blocked this file")."""
import os
import subprocess
import sys

import numpy as np
import pytest
from scipy import signal

from studio.engine import dsp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100


@pytest.mark.parametrize("wn,kind", [(80 / (SR / 2), "high"), (900 / (SR / 2), "low"), (300 / (SR / 2), "low"),
                                     ([1500 / (SR / 2), 8000 / (SR / 2)], "band"), ([500 / (SR / 2), 700 / (SR / 2)], "band")])
def test_the_numpy_butterworth_matches_scipy(wn, kind):
    b0, a0 = signal.butter(2, wn, kind)
    b1, a1 = dsp.butter_np(2, wn, kind)
    assert np.allclose(b0, b1, rtol=1e-8, atol=1e-12) and np.allclose(a0, a1, rtol=1e-8, atol=1e-12)


def test_the_numpy_filter_matches_scipy_on_real_looking_audio():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(SR * 3) * 0.3 + np.sin(2 * np.pi * 220 * np.arange(SR * 3) / SR)
    for wn, kind in ((80 / (SR / 2), "high"), (900 / (SR / 2), "low"), ([1500 / (SR / 2), 8000 / (SR / 2)], "band")):
        b, a = signal.butter(2, wn, kind)
        ref, got = signal.lfilter(b, a, x), dsp.lfilter_np(b, a, x)
        assert np.max(np.abs(ref - got)) < 1e-6, kind
    fir = ([0.4, 0.6], [1])
    assert np.allclose(signal.lfilter(*fir, x), dsp.lfilter_np(*fir, x), atol=1e-12)


@pytest.mark.parametrize("up,down", [(147, 80), (147, 160), (2, 1), (1, 2)])
def test_the_numpy_resampler_matches_scipy_closely(up, down):
    n = 24000
    t = np.arange(n) / n
    x = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 3100 * t) + 0.1 * np.sin(2 * np.pi * 7000 * t)
    ref, got = signal.resample_poly(x, up, down), dsp.resample_poly_np(x, up, down)
    assert len(ref) == len(got)
    mid = slice(2000, -2000)                                 # the very ends differ by how each pads
    assert np.sqrt(np.mean((ref[mid] - got[mid]) ** 2)) < 2e-3 * np.sqrt(np.mean(ref[mid] ** 2)) + 1e-4


def run_blocked(blocked_prefixes, code):
    """Run `code` in a fresh Python where importing any of the given scipy modules fails like a blocked file."""
    prog = f"""
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if any(name == p or name.startswith(p + ".") for p in {blocked_prefixes!r}):
            raise ImportError("DLL load failed while importing " + name.split(".")[-1] + ": An Application Control policy has blocked this file.")
sys.meta_path.insert(0, Block())
{code}
"""
    return subprocess.run([sys.executable, "-c", prog], cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_when_the_stats_file_is_blocked_scipy_signal_still_loads_without_it():
    r = run_blocked(["scipy.stats"], """
from studio.engine import dsp, audio
import numpy as np
print(dsp.BACKEND)
b, a = dsp.butter(2, 0.1)
y = dsp.lfilter(b, a, np.ones(100))
print(abs(y[-1] - 1) < 1e-3)
try:
    import scipy.stats
    print("stats-importable")
except ImportError:
    print("stats-still-blocked")
""")
    assert r.returncode == 0, r.stderr[-800:]
    out = r.stdout.split()
    assert out[0] == "scipy" and "without" in r.stdout and "True" in r.stdout and "stats-still-blocked" in r.stdout


def test_when_scipy_signal_cannot_load_at_all_the_studio_still_starts_on_numpy():
    r = run_blocked(["scipy.signal", "scipy.stats"], """
from studio.engine import dsp, audio
import numpy as np
print(dsp.BACKEND)
b, a = audio.butter(2, 80 / (audio.SR / 2), "high")
print(len(audio.lfilter(b, a, np.random.randn(5000))))
from studio.pipeline import stages
print(len(stages.resample(np.random.randn(2400), 24000)))
""")
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.split()[0] == "numpy" and "5000" in r.stdout and "4410" in r.stdout


def test_the_normal_path_is_untouched():
    r = run_blocked([], "from studio.engine import dsp; print(dsp.BACKEND)")
    assert r.returncode == 0 and r.stdout.strip() == "scipy"
