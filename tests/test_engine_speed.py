"""The speed-ups must not change the picture: cropped layer finishing, the shared paper grain, the faster share copy."""
import os
import random
import shutil
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

from studio.engine import core
from studio.engine.core import finish_layer, paper_grain, W, H
from studio.engine.pen import Pen


def old_finish(im):
    """What Scene._finish did before: convert and downsample the whole 4K canvas, then cut to the drawn part."""
    im = im.convert("RGBa").resize((W, H), Image.LANCZOS).convert("RGBA")
    bb = im.getchannel("A").getbbox()
    if not bb:
        return None, (0, 0)
    return im.crop(bb), (bb[0], bb[1])


@pytest.mark.parametrize("seed", range(10))
def test_finish_layer_gives_the_same_pixels_as_converting_the_whole_canvas(seed):
    r = random.Random(seed)
    p = Pen(seed, rgba=True)
    for _ in range(r.randint(1, 4)):
        x, y = r.randint(0, W), r.randint(0, H)
        if seed % 4 == 0:
            x = r.choice([0, 3, W - 4, W])          # drawings touching the screen edges
        if seed % 4 == 1:
            y = r.choice([0, 5, H - 3, H])
        p.circ(x, y, r.randint(5, 90), (200, 60, 60), r.choice([0, 4]))
        p.line([(x, y), (x + r.randint(-200, 200), y + r.randint(-200, 200))], r.randint(2, 12), (20, 20, 30), 1.0)
    a, b = old_finish(p.im), finish_layer(p.im)
    assert a[1] == b[1] and a[0].size == b[0].size
    diff = np.abs(np.asarray(a[0]).astype(int) - np.asarray(b[0]).astype(int))
    assert diff.max() <= 1, "a cut canvas may only differ by filter rounding"
    assert (diff > 0).mean() < 1e-4


def test_an_empty_layer_stays_empty():
    assert finish_layer(Pen(1, rgba=True).im) == (None, (0, 0))


def test_paper_grain_is_the_same_every_time_and_has_the_old_strength():
    g = paper_grain()
    assert g is paper_grain() and g.size == (W, H)
    a = np.asarray(g.convert("L")).astype(float)
    assert abs(a.mean() - 128) < 1 and 11 < a.std() < 13


def test_two_renders_of_a_background_are_identical(monkeypatch):
    def bg():
        sc = core.Scene(0, 3.0, "fun", "x")
        sc.bg_paper()
        return np.asarray(sc.bg)
    assert np.array_equal(bg(), bg())


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_share_copy_is_small_720p_and_under_the_size_cap(tmp_path):
    from studio.engine.render import share_copy
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=4",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", src], check=True)
    for height, want in ((720, 720), (480, 480), (0, 1080)):
        out = str(tmp_path / f"share_{height}.mp4")
        path, kbps = share_copy(src, out, max_mb=1.0, duration=4.0, height=height)
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=height",
                               "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
        assert int(info) == want
        assert os.path.getsize(path) < 1.0 * 1024 * 1024 * 1.15           # capped bitrate: never far over the size asked
        assert 120 <= kbps <= 300
    small = str(tmp_path / "small_src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", "scale=640:360", "-c:v", "libx264",
                    "-preset", "ultrafast", "-c:a", "aac", small], check=True)
    out = str(tmp_path / "no_upscale.mp4")
    share_copy(small, out, max_mb=1.0, duration=4.0, height=720)
    h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=height", "-of", "csv=p=0",
                        out], capture_output=True, text=True).stdout.strip()
    assert int(h) == 360, "a small video is never scaled up"


def test_the_benchmark_script_runs():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, os.path.join(here, "scripts", "bench_render.py"), "--frames", "1", "--only", "outro"],
                       capture_output=True, text=True, cwd=here, timeout=300)
    assert r.returncode == 0, r.stderr[-400:]
    assert "ms/frame" in r.stdout
