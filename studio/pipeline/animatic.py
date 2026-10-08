"""A quick preview video in seconds: the storyboard stills, each held for its narration, with the voice and the words on top.

Rendering the real video takes minutes to hours (the pictures are drawn frame by frame). The animatic is made from what the
earlier stages already produced (the preview picture of every scene and the recorded narration), so it needs no drawing and
costs nothing: use it to check the pacing, the order and the voice before spending a long render. It is a slideshow: nothing
moves, there are no transitions or music, and the pictures are the storyboard previews (small).
"""
import os
import subprocess

import numpy as np
import soundfile as sf

SIZE = (960, 540)
FPS = 10
SR = 24000


def _frame(pr, i, text, size=SIZE):
    """The picture for scene i: its preview still (or a plain card) with the narration along the bottom."""
    from PIL import Image, ImageDraw
    from ..engine.fonts import font
    path = pr.preview_path(i)
    if os.path.exists(path):
        im = Image.open(path).convert("RGB").resize(size, Image.LANCZOS)
        have = True
    else:
        im = Image.new("RGB", size, (246, 238, 220))
        have = False
    d = ImageDraw.Draw(im, "RGBA")
    f = font("semi", 26)
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > size[0] - 80 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    lines = lines[-4:]
    h = 14 + 34 * len(lines)
    d.rectangle((0, size[1] - h - 8, size[0], size[1]), fill=(20, 20, 30, 190))
    for k, ln in enumerate(lines):
        d.text((40, size[1] - h + 4 + 34 * k), ln, font=f, fill=(255, 255, 255, 255))
    d.text((14, 10), f"{i + 1}" + ("" if have else "  (no picture yet)"), font=font("semi", 22), fill=(120, 120, 130, 255))
    return im


def _track(pr, vb, durs, lead):
    """One narration track as long as the scenes: each line starts `lead` seconds into its scene."""
    from ..engine.dsp import resample_poly
    out = []
    for i, e in enumerate(vb):
        n = int(round(durs[i] * SR))
        seg = np.zeros(n, dtype=np.float32)
        try:
            x, sr = sf.read(pr.audio_path(i), dtype="float32")
            if x.ndim > 1:
                x = x.mean(axis=1)
            if sr != SR:
                from math import gcd
                g = gcd(int(sr), SR)
                x = resample_poly(x, SR // g, int(sr) // g).astype(np.float32)
            a = int(round(lead * SR))
            seg[a:a + len(x)] = x[:max(0, n - a)]
        except (OSError, RuntimeError, ValueError):
            pass                                                  # a missing line is silence, not an error
        out.append(seg)
    return np.concatenate(out) if out else np.zeros(1, dtype=np.float32)


def build(pr, out_path=None):
    """Make final/animatic.mp4. Returns dict(path, seconds, scenes, missing_pictures). Raises ValueError with a plain
    message when there is no voice yet."""
    from ..engine.render import plan_timeline
    from ..engine.timing import LEAD
    beats = (pr.script() or {}).get("beats") or []
    vb = (pr.voice() or {}).get("beats") or []
    if not beats or len(vb) != len(beats) or any(not e for e in vb):
        raise ValueError("record the voice first: the preview video is made from the narration")
    frames, starts, durs = plan_timeline([e["dur"] for e in vb])
    out_path = out_path or pr.p("final", "animatic.mp4")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    work = pr.p("final", "_animatic")
    os.makedirs(work, exist_ok=True)
    listing, missing = [], []
    try:
        for i, b in enumerate(beats):
            img = os.path.join(work, f"{i:03d}.png")
            _frame(pr, i, b.get("text", "")).save(img)
            if not os.path.exists(pr.preview_path(i)):
                missing.append(i)
            listing.append(f"file '{img.replace(chr(92), '/')}'\nduration {durs[i]:.3f}")
        listing.append(f"file '{os.path.join(work, f'{len(beats) - 1:03d}.png').replace(chr(92), '/')}'")     # concat needs the last file twice
        lst = os.path.join(work, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            f.write("\n".join(listing) + "\n")
        wav = os.path.join(work, "narration.wav")
        sf.write(wav, _track(pr, vb, durs, LEAD), SR)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
               "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", out_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg could not make the preview video: " + r.stderr.strip()[-300:])
    finally:
        for fn in os.listdir(work):
            try:
                os.remove(os.path.join(work, fn))
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass
    return dict(path=out_path, seconds=round(sum(durs), 1), scenes=len(beats), missing_pictures=missing)
