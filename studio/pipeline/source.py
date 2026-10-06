"""YouTube source: metadata (yt-dlp), transcript (provider), and "watching" via frame contact sheets."""
import glob
import math
import os
import subprocess

from PIL import Image, ImageDraw

from ..engine.fonts import font
from ..providers import video_id, ProviderError
from ..config import ytdlp_opts


def fetch_meta(url):
    import yt_dlp
    opts = ytdlp_opts(skip_download=True, quiet=True, no_warnings=True, noplaylist=True, ignore_no_formats_error=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    keep = ("id", "title", "channel", "uploader", "duration", "description", "chapters", "thumbnail", "webpage_url",
            "upload_date", "tags", "view_count", "categories")
    meta = {k: info.get(k) for k in keep}
    meta["description"] = (meta.get("description") or "")[:5000]
    meta["chapters"] = [dict(start_time=c.get("start_time"), end_time=c.get("end_time"), title=c.get("title"))
                        for c in (info.get("chapters") or [])]
    meta["channel"] = meta.get("channel") or meta.get("uploader") or ""
    meta["video_id"] = info.get("id") or video_id(url)
    return meta


def transcript_text(segments, every=20.0):
    """Compact transcript with a [123s] marker roughly every 20 seconds."""
    out, last = [], -1e9
    for s in segments:
        if s["start"] - last >= every:
            out.append(f"\n[{int(s['start'])}s]")
            last = s["start"]
        out.append(s["text"].strip())
    return " ".join(out).strip()


def download_lowres(url, workdir):
    import yt_dlp
    os.makedirs(workdir, exist_ok=True)
    for f in glob.glob(os.path.join(workdir, "lowres.*")):
        return f
    # we only need pictures: a small video-only stream is enough (YouTube often has no small "video+audio" file)
    opts = ytdlp_opts(format="wv*[height>=240][ext=mp4]/wv*[height>=240]/bv*[height<=480]/bv*/b/w",
                      quiet=True, no_warnings=True, outtmpl=os.path.join(workdir, "lowres.%(ext)s"), noplaylist=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def thumbnail_frames(vid, workdir):
    """Fallback when the video itself can't be downloaded: YouTube's own stills (the cover and three automatic
    frames from about 25%, 50% and 75% of the video). Returns [(t, path)]."""
    import urllib.request
    os.makedirs(workdir, exist_ok=True)
    out = []
    for k, name in enumerate(("maxresdefault", "hq1", "hq2", "hq3")):
        path = os.path.join(workdir, f"thumb_{k}.jpg")
        try:
            req = urllib.request.Request(f"https://i.ytimg.com/vi/{vid}/{name}.jpg", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r, open(path, "wb") as f:
                f.write(r.read())
            im = Image.open(path).convert("RGB")
            im.thumbnail((384, 384))
            im.save(path, quality=88)
            out.append((float(k), path))
        except Exception:
            continue
    return out


def extract_frames(video, duration, workdir, max_frames=48):
    """One frame every N seconds (N chosen so we get <= max_frames), 384 px wide. Returns [(t, path)]."""
    os.makedirs(workdir, exist_ok=True)
    step = max(5.0, math.ceil(max(duration, 1) / max_frames))
    out = []
    t = step / 2
    i = 0
    while t < duration and i < max_frames:
        path = os.path.join(workdir, f"f_{i:03d}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", "scale=384:-2", "-q:v", "4", path], check=False)
        if os.path.exists(path):
            out.append((t, path))
        t += step
        i += 1
    return out


def contact_sheets(frames, workdir, cols=4, rows=3):
    """Pack frames into labelled grids so a vision model can 'watch' the video in a few images."""
    os.makedirs(workdir, exist_ok=True)
    sheets = []
    per = cols * rows
    for k in range(0, len(frames), per):
        chunk = frames[k:k + per]
        tw, th = 384, 216
        im = Image.new("RGB", (cols * tw, rows * th), "white")
        d = ImageDraw.Draw(im)
        for j, (t, path) in enumerate(chunk):
            try:
                fr = Image.open(path).convert("RGB")
                fr.thumbnail((tw, th))
            except Exception:
                continue
            x, y = (j % cols) * tw, (j // cols) * th
            im.paste(fr, (x, y))
            d.rectangle([x, y, x + 74, y + 30], fill=(0, 0, 0))
            d.text((x + 6, y + 4), f"{int(t)}s", font=font("bold", 20), fill=(255, 255, 0))
        path = os.path.join(workdir, f"sheet_{len(sheets) + 1:02d}.jpg")
        im.save(path, quality=82)
        sheets.append(path)
    return sheets


def hints_for_beats(visual_notes, n_beats, duration):
    """Map 'moments' (time -> what was on screen) to beats by proportional position in the video."""
    moments = sorted((visual_notes or {}).get("moments") or [], key=lambda m: m.get("time", 0))
    if not moments or not n_beats or not duration:
        return {}
    out = {}
    for i in range(n_beats):
        t0, t1 = i / n_beats * duration, (i + 1) / n_beats * duration
        near = [m["visual"] for m in moments if t0 - 5 <= m.get("time", 0) <= t1 + 5]
        if near:
            out[i] = "; ".join(near[:2])[:300]
    return out
