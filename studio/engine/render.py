"""Rendering: scene JSON -> frames -> MP4 segment (raw RGB piped into ffmpeg), stills, and concat."""
import os
import subprocess
import time

from .core import W, H, FPS
from .compiler import build_scene
from .captions import make_captions, paste_caption
from .timing import WordTimer, LEAD, TAIL

# bump when drawing or animation changes, so finished videos get re-rendered with the new look
ENGINE_VERSION = 10


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
    caps = make_captions(job["text"], job["dur"], timer=timer, style=job.get("caption_style", "highlight")) \
        if captions else ()
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


# ------------------------------------------------------------------ transitions between scenes
TRANSITIONS = ("auto", "cut", "slide", "wipe", "zoom", "iris", "paper", "fade")
TRANSITION_TIME = 0.45
TRANSITION_TIMES = {"mapzoom": 0.9}      # zooming from one map into a closer one takes a little longer
TRANSITION_SFX = {"slide": "swish", "wipe": "swish", "zoom": "whoosh", "paper": "swish", "iris": "swish",
                  "mapzoom": "whoosh"}


def bg_sig(scene):
    bg = (scene or {}).get("bg") or {}
    return (bg.get("type"), bg.get("skyline"), bg.get("style"), tuple(bg.get("center") or ()), bg.get("width"))


def pick_transition(prev, scene, idx, mood="fun", prev_mood="fun"):
    """How scene `idx` starts after `prev` (both scene dicts). Explicit "transition" wins; otherwise: maps and
    same-place scenes cut (it reads as one shot), sad moments fade, everything else rotates through the rest."""
    want = str((scene or {}).get("transition") or "auto").lower()
    if prev is None:
        return "cut"
    if want in TRANSITIONS and want not in ("auto", "zoom"):
        return want
    if want == "zoom" and not ((prev.get("bg") or {}).get("type") == (scene.get("bg") or {}).get("type") == "map"):
        return "zoom"
    if mood == "somber" or prev_mood == "somber":
        return "fade"
    a, b = ((prev.get("bg") or {}).get("type"), (scene.get("bg") or {}).get("type"))
    if a == b == "map":
        # a closer (or wider) view of a place on the previous map: zoom into it (or out of it)
        from .livemap import view_zoom
        if want in ("auto", "zoom") and view_zoom(prev.get("bg") or {}, scene.get("bg") or {}):
            return "mapzoom"
        return "cut"
    if bg_sig(prev) == bg_sig(scene):
        return "cut"
    return ("slide", "wipe", "zoom", "paper", "slide", "iris", "wipe")[idx % 7]


def compose_transition(a, b, kind, p):
    """Frame p (0..1) of a transition from image a (last frame before) to image b (the new scene)."""
    from PIL import Image, ImageDraw
    from .core import ease_io
    q = ease_io(p)
    a, b = a.convert("RGB"), b.convert("RGB")
    if kind == "slide":
        out = Image.new("RGB", (W, H))
        out.paste(a, (int(-q * W), 0))
        out.paste(b, (int(W - q * W), 0))
        return out
    if kind == "wipe":
        edge = q * (W + 500) - 250
        mask = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(mask)
        d.polygon([(0, 0), (edge + 160, 0), (edge - 160, H), (0, H)], fill=255)
        out = a.copy()
        out.paste(b, (0, 0), mask)
        ImageDraw.Draw(out).line([(edge + 160, 0), (edge - 160, H)], fill=(38, 38, 48), width=10)
        return out
    if kind == "zoom":
        za = 1 + 0.6 * q
        aa = a.resize((int(W * za), int(H * za)), Image.BILINEAR).crop(
            (int((W * za - W) / 2), int((H * za - H) / 2), int((W * za - W) / 2) + W, int((H * za - H) / 2) + H))
        zb = 1.18 - 0.18 * q
        bb = b.resize((int(W * zb), int(H * zb)), Image.BILINEAR).crop(
            (int((W * zb - W) / 2), int((H * zb - H) / 2), int((W * zb - W) / 2) + W, int((H * zb - H) / 2) + H))
        return Image.blend(aa, bb, min(1.0, q * 1.4))
    if kind == "iris":
        r = q * 1150
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=255)
        out = a.copy()
        out.paste(b, (0, 0), mask)
        if r > 4:
            ImageDraw.Draw(out).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], outline=(38, 38, 48), width=10)
        return out
    if kind == "paper":
        y = int(H * (1 - q))
        out = Image.blend(a, Image.new("RGB", (W, H), (20, 20, 26)), 0.25 * q)
        out.paste(b, (0, y))
        ImageDraw.Draw(out).rectangle([0, y - 12, W, y], fill=(60, 56, 52))
        return out
    if kind == "fade":
        dark = Image.new("RGB", (W, H), (16, 16, 22))
        return Image.blend(a, dark, min(1.0, p * 2)) if p < 0.5 else Image.blend(dark, b, min(1.0, (p - 0.5) * 2))
    return b


def render_segment(job):
    """job: dict(idx, scene, dur, mood, text, word_times, frames, out, captions=True, watermark="",
    prev=None (the previous scene's job, for a transition), transition="cut").
    Returns dict(idx, sfx=[(t, kind)], warnings=[...], seconds=elapsed)."""
    t0 = time.time()
    sc, timer = make_scene(job)
    caps = make_captions(job["text"], job["dur"], timer=timer, style=job.get("caption_style", "highlight")) \
        if job.get("captions", True) else ()
    wm = watermark_image(job["watermark"]) if job.get("watermark") else None
    kind = job.get("transition") or "cut"
    before = None
    if kind != "cut" and job.get("prev"):
        try:
            psc, _ = make_scene(job["prev"])
            before = psc.render_at(max(0.0, job["prev"]["dur"] - 1 / FPS))
        except Exception as e:  # a transition is a nicety; never fail the scene over it
            sc.warn(f"transition skipped: {e}")
            before = None
    zoom_info = None
    if kind == "mapzoom" and before is not None:
        from .livemap import view_zoom
        zoom_info = view_zoom((job["prev"].get("scene") or {}).get("bg") or {}, (job.get("scene") or {}).get("bg") or {})
        if zoom_info is None:
            kind = "fade"
    n_tr = int(TRANSITION_TIMES.get(kind, TRANSITION_TIME) * FPS) if before is not None else 0
    if n_tr and TRANSITION_SFX.get(kind):
        sc.sfx.append((0.02, TRANSITION_SFX[kind]))
    tmp = job["out"] + ".part.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", job.get("preset", "veryfast"),
           "-crf", str(job.get("crf", 20)), "-pix_fmt", "yuv420p", "-threads", str(job.get("threads", 1)),
           "-movflags", "+faststart", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fi in range(job["frames"]):
            tt = fi / FPS
            fr = sc.render_at(tt)
            if fi < n_tr:
                if zoom_info is not None:
                    from .livemap import compose_mapzoom
                    fr = compose_mapzoom(before, fr, zoom_info, (fi + 1) / (n_tr + 1))
                else:
                    fr = compose_transition(before, fr, kind, (fi + 1) / (n_tr + 1))
            paste_caption(fr, caps, tt)
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


def share_copy(src, out_path, max_mb=30.0, duration=None, height=720):
    """A small copy of the video under max_mb for chats and phones. One capped x264 pass at `height` pixels tall
    (flat doodle art stays cleaner at 720p than at 1080p for the same few hundred kbps, and the encode takes about
    half as long as the old two-pass 1080p one). The video bitrate is capped (maxrate), so the size never goes over."""
    if duration is None:
        duration = probe_duration(src)
    audio_kbps = 96
    total_kbps = max_mb * 8 * 1024 / max(duration, 1) * 0.94
    v_kbps = int(max(120, min(300, total_kbps - audio_kbps)))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src]
    if height and int(height) > 0:
        cmd += ["-vf", f"scale=-2:min({int(height)}\\,ih)"]          # never upscale a smaller source
    cmd += ["-c:v", "libx264", "-preset", "medium", "-tune", "animation", "-b:v", f"{v_kbps}k",
            "-maxrate", f"{v_kbps}k", "-bufsize", f"{v_kbps * 2}k", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", f"{audio_kbps}k", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)
    return out_path, v_kbps


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0
