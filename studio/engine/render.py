"""Rendering: scene JSON -> frames -> MP4 segment (raw RGB piped into ffmpeg), stills, and concat."""
import os
import subprocess
import time

from .core import W, H, FPS
from .compiler import build_scene
from .captions import make_captions
from .timing import WordTimer, LEAD, TAIL


def plan_timeline(voice_durs, lead=LEAD, tail=TAIL):
    """Scene duration = voice length + lead + tail, rounded to whole frames.
    Returns (frames, starts, durs) with starts/durs in seconds."""
    frames, starts, durs = [], [], []
    t = 0
    for d in voice_durs:
        n = max(int(round((float(d) + lead + tail) * FPS)), FPS)
        frames.append(n)
        starts.append(t / FPS)
        durs.append(n / FPS)
        t += n
    return frames, starts, durs


def make_scene(job):
    timer = WordTimer(job["text"], job["dur"], LEAD, TAIL, job.get("word_times"))
    sc = build_scene(job["scene"], job["idx"], job["dur"], job["mood"], job["text"], timer=timer)
    return sc, timer


def render_still(job, out_path, t_frac=0.85, size=(640, 360), captions=False):
    sc, timer = make_scene(job)
    caps = make_captions(job["text"], job["dur"], timer=timer) if captions else ()
    im = sc.render_at(job["dur"] * t_frac, caps)
    if size and size != (W, H):
        from PIL import Image
        im = im.resize(size, Image.LANCZOS)
    im.convert("RGB").save(out_path, quality=88)
    return sc.warnings


def watermark_image(text, size=26):
    """A small semi-transparent label for the top-right corner (Free plan in hosted mode)."""
    from PIL import Image, ImageDraw
    from .fonts import font
    f = font("semi", size)
    x0, y0, x1, y1 = f.getbbox(text)
    pad = 10
    im = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=10, fill=(20, 20, 30, 110))
    d.text((pad - x0, pad - y0), text, font=f, fill=(255, 255, 255, 200))
    return im


def render_segment(job):
    """job: dict(idx, scene, dur, mood, text, word_times, frames, out, captions=True, watermark="").
    Returns dict(idx, sfx=[(t, kind)], warnings=[...], seconds=elapsed)."""
    t0 = time.time()
    sc, timer = make_scene(job)
    caps = make_captions(job["text"], job["dur"], timer=timer) if job.get("captions", True) else ()
    wm = watermark_image(job["watermark"]) if job.get("watermark") else None
    tmp = job["out"] + ".part.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", job.get("preset", "veryfast"),
           "-crf", str(job.get("crf", 20)), "-pix_fmt", "yuv420p", "-threads", str(job.get("threads", 1)),
           "-movflags", "+faststart", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fr in sc.render_frames(job["frames"], caps):
            if wm is not None:
                fr.paste(wm, (W - wm.width - 24, 22), wm)
            p.stdin.write(fr.convert("RGB").tobytes())
        p.stdin.close()
    except BrokenPipeError:
        pass
    err = p.stderr.read().decode(errors="ignore")
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for scene {job['idx']}: {err[-400:]}")
    os.replace(tmp, job["out"])
    return dict(idx=job["idx"], sfx=sc.sfx, warnings=sc.warnings, seconds=time.time() - t0)


def concat_segments(paths, out_path, audio_path=None):
    lst = out_path + ".txt"
    with open(lst, "w", encoding="utf-8") as f:
        for pth in paths:
            f.write("file '" + os.path.abspath(pth).replace("\\", "/").replace("'", "'\\''") + "'\n")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst]
    if audio_path:
        cmd += ["-i", audio_path, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-c", "copy"]
    cmd += ["-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)
    os.remove(lst)
    return out_path


def share_copy(src, out_path, max_mb=30.0, duration=None):
    """2-pass x264 copy under max_mb (flat doodle art looks fine around 230 kbps)."""
    if duration is None:
        duration = probe_duration(src)
    audio_kbps = 96
    total_kbps = max_mb * 8 * 1024 / max(duration, 1) * 0.94
    v_kbps = int(max(120, min(300, total_kbps - audio_kbps)))
    passlog = out_path + ".passlog"
    null = "NUL" if os.name == "nt" else "/dev/null"
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:v", "libx264", "-preset", "medium",
            "-b:v", f"{v_kbps}k", "-passlogfile", passlog]
    subprocess.run(base + ["-pass", "1", "-an", "-f", "mp4", null], check=True)
    subprocess.run(base + ["-pass", "2", "-c:a", "aac", "-b:a", f"{audio_kbps}k", "-movflags", "+faststart", out_path],
                   check=True)
    for ext in ("-0.log", "-0.log.mbtree"):
        try:
            os.remove(passlog + ext)
        except OSError:
            pass
    return out_path, v_kbps


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0
