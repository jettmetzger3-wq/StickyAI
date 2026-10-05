"""Transcript providers for "remake from a YouTube link".

- youtube_captions: the video's own captions (manual or auto-generated). Free, instant.
- whisper_local:    download the audio with yt-dlp and transcribe it on your PC (free, needs faster-whisper).
- elevenlabs_scribe: ElevenLabs speech-to-text reads the YouTube URL directly (paid, very accurate).
"""
import glob
import html
import json
import os
import re

from .base import TranscriptProvider, Cost, FREE, ProviderError
from ..config import ytdlp_opts
from . import elevenlabs_common as el


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url or "")
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", (url or "").strip()):
        return url.strip()
    return None


def canonical_url(url):
    """Rebuild a clean YouTube watch URL from the video id, so we never hand yt-dlp some other site's URL."""
    vid = video_id(url)
    return f"https://www.youtube.com/watch?v={vid}" if vid else ""


def parse_vtt(text):
    """WebVTT -> [{start, end, text}] (dedupes the rolling lines YouTube auto-captions repeat)."""
    segs = []
    ts = re.compile(r"(\d+):(\d\d):(\d\d)[.,](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[.,](\d{3})")
    lines = text.splitlines()
    i = 0
    last = ""
    while i < len(lines):
        m = ts.search(lines[i])
        if not m:
            i += 1
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        i += 1
        buf = []
        while i < len(lines) and lines[i].strip():
            buf.append(lines[i])
            i += 1
        t = " ".join(re.sub(r"<[^>]+>", "", b).strip() for b in buf)
        t = html.unescape(re.sub(r"\s+", " ", t)).strip()
        if not t:
            continue
        if last and t.startswith(last):
            t2 = t[len(last):].strip()
            if not t2:
                continue
            t = t2
        if t == last:
            continue
        segs.append(dict(start=start, end=end, text=t))
        last = segs[-1]["text"] if not buf or len(buf) == 1 else buf[-1].strip()
    return segs


def parse_json3(data):
    segs = []
    for ev in data.get("events", []):
        if "segs" not in ev:
            continue
        t = "".join(s.get("utf8", "") for s in ev["segs"]).replace("\n", " ").strip()
        if not t:
            continue
        st = ev.get("tStartMs", 0) / 1000
        segs.append(dict(start=st, end=st + ev.get("dDurationMs", 0) / 1000, text=html.unescape(t)))
    return segs


class YouTubeCaptions(TranscriptProvider):
    id = "youtube_captions"
    label = "YouTube captions (free)"
    description = "Uses the video's own captions (manual or auto-generated)."
    paid = False
    quality = "good"
    needs_modules = ("yt_dlp",)

    def transcript(self, url, meta, workdir, progress=None):
        vid = video_id(url)
        errors = []
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            try:
                tr = api.fetch(vid, languages=["en", "en-US", "en-GB"])
            except Exception:
                tl = api.list(vid)
                t = next(iter(tl))
                tr = t.translate("en").fetch() if getattr(t, "is_translatable", False) and t.language_code != "en" else t.fetch()
            segs = [dict(start=s.start, end=s.start + s.duration, text=s.text.replace("\n", " ")) for s in tr]
            if segs:
                return segs
        except Exception as e:
            errors.append(f"youtube-transcript-api: {str(e)[:200]}")
        # fallback: yt-dlp subtitle download
        try:
            import yt_dlp
            os.makedirs(workdir, exist_ok=True)
            opts = ytdlp_opts(skip_download=True, writesubtitles=True, writeautomaticsub=True, subtitleslangs=["en.*", "en"],
                        subtitlesformat="json3/vtt/best", outtmpl=os.path.join(workdir, "subs.%(ext)s"), quiet=True,
                        no_warnings=True)
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            for f in sorted(glob.glob(os.path.join(workdir, "subs*"))):
                if f.endswith(".json3"):
                    segs = parse_json3(json.load(open(f, encoding="utf-8")))
                elif f.endswith(".vtt"):
                    segs = parse_vtt(open(f, encoding="utf-8").read())
                else:
                    continue
                if segs:
                    return segs
            errors.append("yt-dlp found no English subtitles")
        except Exception as e:
            errors.append(f"yt-dlp: {str(e)[:200]}")
        raise ProviderError("No captions available for this video. Try 'Whisper (local)' or 'ElevenLabs Scribe'. "
                            + " | ".join(errors))


class WhisperLocal(TranscriptProvider):
    id = "whisper_local"
    label = "Whisper on my PC (free, slower)"
    description = "Downloads the audio and transcribes it locally with faster-whisper (first run downloads a model)."
    paid = False
    quality = "good"
    needs_modules = ("faster_whisper", "yt_dlp")
    install_hint = "pip install faster-whisper"

    def transcript(self, url, meta, workdir, progress=None):
        import yt_dlp
        from faster_whisper import WhisperModel
        os.makedirs(workdir, exist_ok=True)
        if progress:
            progress("downloading audio", 0.05)
        opts = ytdlp_opts(format="bestaudio/best", outtmpl=os.path.join(workdir, "audio.%(ext)s"), quiet=True, no_warnings=True)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        if progress:
            progress("transcribing (this can take a while)", 0.2)
        model = WhisperModel("small.en", device="auto", compute_type="int8")
        segments, _ = model.transcribe(path, vad_filter=True)
        dur = max(1.0, float(meta.get("duration") or 1))
        out = []
        for s in segments:
            out.append(dict(start=s.start, end=s.end, text=s.text.strip()))
            if progress:
                progress("transcribing", 0.2 + 0.8 * min(1.0, s.end / dur))
        return out


class ElevenLabsScribe(TranscriptProvider):
    id = "elevenlabs_scribe"
    label = "ElevenLabs Scribe (paid, most accurate)"
    description = "ElevenLabs speech-to-text transcribes the YouTube link directly."
    paid = True
    quality = "best"
    needs_keys = ("ELEVENLABS_API_KEY",)
    needs_modules = ("elevenlabs",)

    def estimate(self, duration=0, **job):
        mins = (duration or 0) / 60
        return Cost(0.0, known=False, credit_unit="ElevenLabs credits",
                    note=f"~{mins:.1f} min of audio. ElevenLabs bills speech-to-text by audio length from your credit "
                         f"balance; the exact rate depends on your plan, so real usage is measured after.")

    def balance(self):
        return el.subscription()

    def transcript(self, url, meta, workdir, progress=None):
        if progress:
            progress("ElevenLabs is transcribing the video", 0.1)
        try:
            r = el.client().speech_to_text.convert(model_id="scribe_v2", source_url=url, timestamps_granularity="word",
                                                   tag_audio_events=False)
        except Exception as e:
            raise ProviderError(f"ElevenLabs Scribe failed: {str(e)[:300]}")
        words = [w for w in (r.words or []) if getattr(w, "type", "word") == "word"]
        segs, cur, start = [], [], None
        for w in words:
            if start is None:
                start = w.start or 0.0
            cur.append(w.text)
            if len(cur) >= 14 or (w.text and w.text[-1] in ".?!"):
                segs.append(dict(start=start, end=w.end or start, text=" ".join(cur).strip()))
                cur, start = [], None
        if cur:
            segs.append(dict(start=start or 0.0, end=(words[-1].end or 0.0), text=" ".join(cur)))
        if not segs and getattr(r, "text", ""):
            segs = [dict(start=0.0, end=float(meta.get("duration") or 0), text=r.text)]
        return segs
