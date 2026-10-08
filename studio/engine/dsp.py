"""butter / lfilter / resample_poly that keep working when Windows blocks one of scipy's compiled files.

The studio only needs these three signal-processing functions. `scipy.signal` is the normal source, but importing it also
imports `scipy.stats` (for one peak-finding function the studio never calls), and on PCs with an Application Control
policy (Smart App Control, WDAC, AppLocker) the compiled file `scipy/stats/_stats_pythran*.pyd` can be blocked:

    ImportError: DLL load failed while importing _stats_pythran: An Application Control policy has blocked this file.

So, in order:
  1. scipy.signal, exactly as before (identical results; this is what runs almost everywhere);
  2. scipy.signal again, without scipy.stats (a stand-in provides the one name it asks for; same results);
  3. numpy only: the same Butterworth design (bilinear transform), a filter run as its impulse response through an FFT, and
     a windowed-sinc resampler. Close to scipy's output (the tests compare), not bit-for-bit.
`BACKEND` says which one is in use; the studio logs it when it is not "scipy".
"""
import sys
import types

import numpy as np


def _load_scipy_signal():
    try:
        from scipy import signal
        return signal, "scipy"
    except ImportError:
        pass
    # Something in scipy's import chain is blocked. The known culprit is scipy.stats: forget the half-loaded modules and
    # import scipy.signal against a one-function stand-in for it (find_peaks_cwt is the only user; the studio never calls it).
    for name in [m for m in sys.modules if m.split(".")[:2] in (["scipy", "signal"], ["scipy", "stats"])]:
        sys.modules.pop(name, None)
    stub = types.ModuleType("scipy.stats")
    stub.scoreatpercentile = lambda a, per, limit=(), interpolation_method="fraction", axis=None: np.percentile(a, per, axis=axis)
    sys.modules["scipy.stats"] = stub
    try:
        from scipy import signal
        return signal, "scipy (without scipy.stats)"
    except ImportError:
        return None, "numpy"
    finally:
        if sys.modules.get("scipy.stats") is stub:      # never leave the stand-in around for code that wants the real one
            del sys.modules["scipy.stats"]


# ---------------------------------------------------------------- the numpy-only versions
def butter_np(N, Wn, btype="low"):
    """Butterworth filter coefficients (b, a) like scipy.signal.butter(N, Wn, btype) for 'low', 'high' and 'band'
    (Wn as a fraction of the Nyquist frequency)."""
    Wn = np.atleast_1d(np.asarray(Wn, dtype=float))
    fs2 = 4.0                                              # scipy works with fs = 2, so the bilinear constant is 2 * fs
    warped = fs2 * np.tan(np.pi * Wn / 2.0)
    m = np.arange(-N + 1, N, 2)
    p = -np.exp(1j * np.pi * m / (2 * N))                  # the analog prototype's poles
    z = np.array([], dtype=complex)
    k = 1.0
    degree = N
    if btype in ("low", "lowpass"):
        wo = warped[0]
        p, k = wo * p, k * wo ** degree
    elif btype in ("high", "highpass"):
        wo = warped[0]
        k = k * np.real(1.0 / np.prod(-p))
        p = wo / p
        z = np.zeros(degree, dtype=complex)
    elif btype in ("band", "bandpass"):
        bw, wo = warped[1] - warped[0], np.sqrt(warped[0] * warped[1])
        p_lp = p * bw / 2.0
        root = np.sqrt(p_lp ** 2 - wo ** 2 + 0j)
        p = np.concatenate([p_lp + root, p_lp - root])
        z = np.zeros(degree, dtype=complex)
        k = k * bw ** degree
    else:
        raise ValueError(f"unsupported filter type {btype!r}")
    deg = len(p) - len(z)
    zz = (fs2 + z) / (fs2 - z)
    pz = (fs2 + p) / (fs2 - p)
    zz = np.concatenate([zz, -np.ones(deg, dtype=complex)])
    k = k * np.real(np.prod(fs2 - z) / np.prod(fs2 - p))
    return k * np.real(np.poly(zz)), np.real(np.poly(pz))


def _impulse_response(b, a, tol=1e-10, max_len=1 << 17):
    """The filter's response to a single 1, long enough that what is left is below `tol` (stable filters die away)."""
    b, a = np.atleast_1d(np.asarray(b, float)), np.atleast_1d(np.asarray(a, float))
    b, a = b / a[0], a / a[0]
    if len(a) == 1:
        return b
    n = 2048
    while True:
        h = np.zeros(n)
        for i in range(n):
            acc = b[i] if i < len(b) else 0.0
            for j in range(1, min(i, len(a) - 1) + 1):
                acc -= a[j] * h[i - j]
            h[i] = acc
        tail = np.max(np.abs(h[-256:]))
        if tail < tol * max(1.0, np.max(np.abs(h))) or n >= max_len:
            return h
        n *= 2


def _fft_convolve(x, h):
    n = len(x) + len(h) - 1
    size = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(h, size), size)[:n]


def lfilter_np(b, a, x, axis=-1):
    """scipy.signal.lfilter with zero initial state: the filter is run as its (truncated) impulse response."""
    x = np.asarray(x, dtype=float)
    h = _impulse_response(b, a)
    if x.ndim == 1:
        return _fft_convolve(x, h)[:len(x)]
    moved = np.moveaxis(x, axis, -1)
    out = np.stack([_fft_convolve(row, h)[:moved.shape[-1]] for row in moved.reshape(-1, moved.shape[-1])])
    return np.moveaxis(out.reshape(moved.shape), -1, axis)


def resample_poly_np(x, up, down, half_len=10, beta=5.0, block=1 << 18):
    """Resample by up/down with a Kaiser-windowed sinc, evaluated only where an output sample is needed."""
    x = np.asarray(x, dtype=float)
    if up == down:
        return x.copy()
    n_out = int(np.ceil(len(x) * up / down))
    cut = min(1.0, up / down)                              # below the new Nyquist when going down
    taps = int(np.ceil(half_len / cut))                    # input samples on each side of an output position
    pad = np.concatenate([np.zeros(taps), x, np.zeros(taps + 1)])
    out = np.empty(n_out)
    offs = np.arange(-taps + 1, taps + 1)
    norm = np.i0(beta)
    for s in range(0, n_out, block):
        m = np.arange(s, min(s + block, n_out))
        t = m * down / up                                   # position in input samples
        base = np.floor(t).astype(int)
        d = (base[:, None] + offs[None, :]) - t[:, None]    # distance from the output position to each input sample
        r = np.clip(np.abs(d) * cut / half_len, 0.0, 1.0)
        w = np.i0(beta * np.sqrt(1.0 - r ** 2)) / norm
        k = cut * np.sinc(cut * d) * w
        k[np.abs(d) * cut > half_len] = 0.0
        out[m] = np.sum(pad[base[:, None] + offs[None, :] + taps] * k, axis=1)
    return out


_signal, BACKEND = _load_scipy_signal()

if _signal is not None:
    butter, lfilter, resample_poly = _signal.butter, _signal.lfilter, _signal.resample_poly
else:
    butter, lfilter, resample_poly = butter_np, lfilter_np, resample_poly_np
