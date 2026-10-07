"""Measure (and guard) the renderer: how long a frame takes for each of the studio's example scenes.

    python scripts/bench_render.py                      # ms per frame for every example scene
    python scripts/bench_render.py --profile            # + where the time goes (cProfile, top functions)
    python scripts/bench_render.py --save base_dir      # keep every rendered frame (PNG) in a folder
    python scripts/bench_render.py --check base_dir     # compare a new run with a saved folder, pixel by pixel

--check is how an optimisation proves it did not change the picture: each frame is compared with the saved one and
reported as identical, "within 2 levels" (rounding noise) or CHANGED (with the largest difference and how many pixels
moved), so a speed-up that alters the look is visible at once. Nothing is written outside --save and nothing is sent
anywhere. Times are CPU seconds of this process (steadier than wall-clock on a busy or shared machine).
"""
import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from studio.engine.compiler import build_scene          # noqa: E402
from studio.engine.core import FPS                      # noqa: E402
from studio.engine.captions import make_captions        # noqa: E402
from studio.engine.schema import check_scene            # noqa: E402
from studio.engine.timing import WordTimer, LEAD, TAIL  # noqa: E402

def fix_the_grain():
    """The renderer used to add a differently random paper grain to every background, so two renders of the very same
    scene never matched. For a fair before/after comparison both runs get the same grain (the current code already
    does; this makes an OLD checkout do too)."""
    import numpy as np
    from PIL import Image
    from studio.engine.core import W, H
    a = np.clip(np.random.default_rng(1234).normal(128.0, 12.0, (H, W)), 0, 255).astype(np.uint8)
    noise = Image.fromarray(a, "L")
    Image.effect_noise = lambda size, sigma: noise.copy()


EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studio", "prompts", "examples.json")


def scenes():
    out = []
    for i, e in enumerate(json.load(open(EXAMPLES))):
        fixed, _, errs = check_scene(e["scene"], e["mood"], e["text"])
        if not errs:
            out.append((e["name"], i, fixed, e["mood"], e["text"]))
    return out


def frame_times(dur, n):
    """n CONSECUTIVE frames from the middle of the scene: that is what a render does, so caches (characters redrawn
    only when their pose changes) behave like they do in a real video."""
    t0 = min(dur * 0.3, max(0.0, dur - 1 / FPS - n / FPS))
    return [min(dur - 1 / FPS, t0 + k / FPS) for k in range(n)]


def run(frames_per_scene, only=None, on_frame=None, prof=None, what="frames"):
    rows = []
    for name, i, scene, mood, text in scenes():
        if only and only not in name:
            continue
        dur = max(3.0, len(text.split()) / 2.6 + LEAD + TAIL)
        t0 = time.process_time()
        if prof and what == "build":
            prof.enable()
        timer = WordTimer(text, dur, LEAD, TAIL, None)
        sc = build_scene(scene, i, dur, mood, text, timer=timer)
        caps = make_captions(text, dur, timer=timer, style="highlight")
        if prof and what == "build":
            prof.disable()
        build = time.process_time() - t0
        t1 = time.process_time()
        if prof and what == "frames":
            prof.enable()
        hashing = 0.0
        for k, t in enumerate(frame_times(dur, frames_per_scene)):
            fr = sc.render_at(t, caps).convert("RGB")
            raw = fr.tobytes()                  # what ffmpeg is fed: part of the cost of a frame
            if prof and what == "frames":
                prof.disable()
            t_hash = time.process_time()
            if on_frame:
                on_frame(f"{name}@{k:02d}", fr)
            hashing += time.process_time() - t_hash     # saving/comparing the picture is not drawing it
            if prof and what == "frames":
                prof.enable()
        if prof and what == "frames":
            prof.disable()
        per = (time.process_time() - t1 - hashing) / frames_per_scene
        rows.append((name, build, per))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=30, help="consecutive frames rendered per scene (30 = one second)")
    ap.add_argument("--only", help="only scenes whose name contains this")
    ap.add_argument("--profile", nargs="?", const="frames", choices=["frames", "build"],
                    help="cProfile either the per-frame drawing (default) or the once-per-scene build")
    ap.add_argument("--save")
    ap.add_argument("--check")
    a = ap.parse_args()
    fix_the_grain()
    pr = cProfile.Profile() if a.profile else None
    stats = dict(same=0, near=0, missing=0, changed=[], saved=0)
    if a.save:
        os.makedirs(a.save, exist_ok=True)

    def on_frame(key, fr):
        if a.save:
            fr.save(os.path.join(a.save, key + ".png"), compress_level=1)
            stats["saved"] += 1
        if a.check:
            import numpy as np
            from PIL import Image
            path = os.path.join(a.check, key + ".png")
            if not os.path.exists(path):
                stats["missing"] += 1
                return
            d = np.abs(np.asarray(fr).astype(np.int16) - np.asarray(Image.open(path).convert("RGB")).astype(np.int16))
            mx = int(d.max())
            if mx == 0:
                stats["same"] += 1
            elif mx <= 2:
                stats["near"] += 1
            else:
                stats["changed"].append((key, mx, float((d.max(axis=2) > 2).mean() * 100)))

    rows = run(a.frames, a.only, on_frame if (a.save or a.check) else None, prof=pr, what=a.profile or "frames")
    total_frames = len(rows) * a.frames
    print(f"{'scene':34s} {'build s':>8s} {'ms/frame':>9s}")
    for name, build, per in sorted(rows, key=lambda r: -r[2]):
        print(f"{name:34s} {build:8.2f} {per * 1000:9.1f}")
    mean = sum(r[2] for r in rows) / max(1, len(rows))
    print(f"\n{len(rows)} scenes, {total_frames} frames: mean {mean * 1000:.1f} ms/frame "
          f"(a 10-minute video is ~18000 frames: ~{mean * 18000 / 60:.1f} min of drawing on one core), "
          f"build (once per scene) {sum(r[1] for r in rows) / max(1, len(rows)):.2f} s")
    if pr:
        s = io.StringIO()
        st = pstats.Stats(pr, stream=s).sort_stats("tottime")
        st.print_stats(14)
        st.print_callers("resize|convert")
        st2 = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        st2.print_stats("studio/engine", 18)
        print(s.getvalue()[:6000])
    if a.save:
        print(f"saved {stats['saved']} frames to {a.save}")
    if a.check:
        total = stats["same"] + stats["near"] + len(stats["changed"])
        print(f"compared with {a.check}: {stats['same']} identical, {stats['near']} within 2 levels (rounding), "
              f"{len(stats['changed'])} CHANGED of {total}" + (f" ({stats['missing']} not in the saved run)" if stats["missing"] else ""))
        for k, mx, pct in sorted(stats["changed"], key=lambda c: -c[2])[:12]:
            print(f"   {k}: largest difference {mx} levels, {pct:.3f}% of pixels moved by more than 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
