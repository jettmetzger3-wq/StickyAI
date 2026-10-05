import json, subprocess, numpy as np, soundfile as sf
from scipy.signal import resample_poly
from render2 import plan, LEAD
from script import SCRIPT
import audio

frames, starts, sdurs = plan()
total = sum(frames) / 30
ev = json.load(open("/tmp/v2/seg/events.json"))
events = []
for k, v in ev.items():
    events += [tuple(e) for e in v]
clips = []
for i in range(len(SCRIPT)):
    x, sr = sf.read(f"/tmp/v2/audio/b_{i:03d}.wav")
    if x.ndim > 1:
        x = x.mean(1)
    clips.append(resample_poly(x, 441, 240))  # 24k -> 44.1k
moods = [m for m, _ in SCRIPT]
audio.build_mix(clips, starts, sdurs, moods, events, total, "/tmp/v2/mix.wav", lead=LEAD)
with open("/tmp/v2/seg/list.txt", "w") as f:
    for i in range(len(SCRIPT)):
        f.write(f"file 's_{i:03d}.mp4'\n")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "/tmp/v2/seg/list.txt",
                "-i", "/tmp/v2/mix.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-shortest", "/tmp/v2/final.mp4"], check=True)
print("total", total)
