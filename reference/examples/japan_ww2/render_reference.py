import sys, json, subprocess, os, time
from multiprocessing import Pool
import numpy as np
import soundfile as sf
from engine import *
from script import SCRIPT
import scenes2

LEAD, TAIL = 0.15, 0.32
durs = json.load(open("/tmp/v2/audio/durs.json"))
os.makedirs("/tmp/v2/seg", exist_ok=True)


def plan():
    frames, starts, sdurs = [], [], []
    t = 0
    for i, d in enumerate(durs):
        n = int(round((d + LEAD + TAIL) * FPS))
        frames.append(n)
        starts.append(t / FPS)
        sdurs.append(n / FPS)
        t += n
    return frames, starts, sdurs


def render_scene(i):
    frames, starts, sdurs = plan()
    d = sdurs[i]
    mood, text = SCRIPT[i]
    sc = Scene(i, d, mood, text)
    scenes2.SC[i](sc)
    caps = make_captions(text, d, LEAD, TAIL)
    out = f"/tmp/v2/seg/s_{i:03d}.mp4"
    t0 = time.time()
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                          "-pix_fmt", "yuv420p", "-threads", "1", out], stdin=subprocess.PIPE)
    for fr in sc.render_frames(frames[i], caps):
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    p.wait()
    ev = [(starts[i] + t, k) for t, k in sc.sfx]
    return i, ev, time.time() - t0


if __name__ == "__main__":
    only = [int(a) for a in sys.argv[1:]]
    frames, starts, sdurs = plan()
    idx = only or list(range(len(SCRIPT)))
    # longest first for load balance
    idx.sort(key=lambda i: -frames[i])
    events = {}
    t0 = time.time()
    with Pool(2) as pool:
        for i, ev, dt in pool.imap_unordered(render_scene, idx):
            events[i] = ev
            print(f"scene {i} done {dt:.0f}s  total {time.time()-t0:.0f}s", flush=True)
    json.dump({str(k): v for k, v in events.items()}, open(f"/tmp/v2/seg/events{'_part' if only else ''}.json", "w"))
    print("ALL DONE", time.time() - t0)
