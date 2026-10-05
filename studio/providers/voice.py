"""Voice providers: Kokoro (free, offline), ElevenLabs (paid, best + exact word timing), system voice (fallback)."""
import base64
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request

import numpy as np
import soundfile as sf

from .base import VoiceProvider, Cost, FREE, ProviderError, NeedsSetup
from ..config import MODELS_DIR, CACHE_DIR, load_settings, secret
from . import elevenlabs_common as el

KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")

KOKORO_VOICES = [
    "am_michael", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_onyx", "am_puck", "am_santa",
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky", "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "bf_alice", "bf_emma", "bf_isabella",
    "bf_lily",
]


def trim_silence(s, sr, thresh=0.01, pre=0.03, post=0.08):
    s = np.asarray(s, dtype=np.float32)
    if s.ndim > 1:
        s = s.mean(axis=1)
    a = np.abs(s)
    idx = np.where(a > thresh)[0]
    if len(idx):
        s = s[max(0, idx[0] - int(pre * sr)):idx[-1] + int(post * sr)]
    return s


def download(url, dst, progress=None):
    tmp = dst + ".part"
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    os.replace(tmp, dst)


class Kokoro(VoiceProvider):
    id = "kokoro"
    label = "Kokoro (free, offline)"
    description = "Good-sounding open voice model that runs on your PC. ~340 MB download on first use."
    paid = False
    quality = "good"
    needs_modules = ("kokoro_onnx",)
    install_hint = "pip install kokoro-onnx"
    _lock = threading.Lock()
    _model = None

    def model_paths(self):
        return [os.path.join(MODELS_DIR, f) for f in KOKORO_FILES]

    def ensure_model(self, progress=None):
        os.makedirs(MODELS_DIR, exist_ok=True)
        for i, (name, path) in enumerate(zip(KOKORO_FILES, self.model_paths())):
            if not os.path.exists(path):
                try:
                    download(KOKORO_BASE + name, path,
                             (lambda f, i=i: progress(f"downloading {name}", (i + f) / 2)) if progress else None)
                except Exception as e:
                    raise NeedsSetup(f"Could not download the Kokoro model ({name}): {e}. Download it by hand from "
                                     f"{KOKORO_BASE}{name} and put it in {MODELS_DIR}")

    def _load(self, progress=None):
        with self._lock:
            if Kokoro._model is None:
                self.ensure_model(progress)
                from kokoro_onnx import Kokoro as K
                Kokoro._model = K(*self.model_paths())
        return Kokoro._model

    def voices(self):
        return [dict(id=v, name=v, lang="en-gb" if v[0] == "b" else "en-us",
                     gender="female" if v[1] == "f" else "male") for v in KOKORO_VOICES]

    def synthesize(self, text, voice=None, speed=None, progress=None):
        st = load_settings()["voice"]
        voice = voice or st.get("kokoro_voice") or "am_michael"
        speed = float(speed or st.get("kokoro_speed") or 1.2)
        k = self._load(progress)
        lang = "en-gb" if voice.startswith("b") else "en-us"
        s, sr = k.create(text, voice=voice, speed=speed, lang=lang)
        return trim_silence(s, sr), sr, None


class SystemVoice(VoiceProvider):
    """espeak-ng (Linux) or Windows SAPI through pyttsx3. Robotic, but works with zero downloads."""
    id = "system"
    label = "System voice (robotic fallback)"
    description = "Uses espeak-ng on Linux or the built-in Windows voice. Only for testing."
    paid = False
    quality = "basic"

    def available(self):
        if shutil.which("espeak-ng") or shutil.which("espeak"):
            return True, ""
        if sys.platform == "win32":
            try:
                import pyttsx3  # noqa: F401
                return True, ""
            except ImportError:
                return False, "pip install pyttsx3"
        return False, "install espeak-ng (sudo apt install espeak-ng)"

    def voices(self):
        return [dict(id="default", name="default")]

    def synthesize(self, text, voice=None, speed=None, progress=None):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "v.wav")
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            if exe:
                wpm = int(175 * float(speed or 1.1))
                subprocess.run([exe, "-v", voice if voice and voice != "default" else "en-us", "-s", str(wpm),
                                "-w", out, text], check=True, capture_output=True)
            else:
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", int(180 * float(speed or 1.1)))
                eng.save_to_file(text, out)
                eng.runAndWait()
            s, sr = sf.read(out, dtype="float32")
        return trim_silence(s, sr), sr, None


class ElevenLabsVoice(VoiceProvider):
    id = "elevenlabs"
    label = "ElevenLabs (paid, best)"
    description = "Studio-quality voice. Flash v2.5 costs about 0.5 credits per character; 1 take per line. " \
                  "Also returns exact word timing, so captions and pop-ins land exactly on the word."
    paid = True
    quality = "best"
    needs_keys = ("ELEVENLABS_API_KEY",)
    needs_modules = ("elevenlabs",)
    CREDITS_PER_CHAR = {"eleven_flash_v2_5": 0.5, "eleven_turbo_v2_5": 0.5, "eleven_multilingual_v2": 1.0,
                        "eleven_v3": 1.0}

    def model(self):
        return load_settings()["voice"].get("elevenlabs_model") or "eleven_flash_v2_5"

    def estimate(self, chars=0, **job):
        rate = self.CREDITS_PER_CHAR.get(self.model(), 1.0)
        credits = chars * rate
        return Cost(el.usd_for_credits(credits), credits=round(credits), credit_unit="ElevenLabs credits",
                    note=f"{chars:,} characters x {rate} credits ({self.model()}), 1 take per line")

    def balance(self):
        return el.subscription()

    def voices(self):
        try:
            res = el.client().voices.search(page_size=100)
            return [dict(id=v.voice_id, name=v.name, category=str(v.category or ""), preview_url=v.preview_url,
                         labels=v.labels or {}) for v in res.voices]
        except Exception as e:
            return [dict(id=load_settings()["voice"].get("elevenlabs_voice_id"), name="George (default)",
                         error=str(e)[:200])]

    def synthesize(self, text, voice=None, speed=None, progress=None):
        st = load_settings()["voice"]
        voice = voice or st.get("elevenlabs_voice_id") or "JBFqnCBsd6RMkjVDRZzb"
        try:
            r = el.client().text_to_speech.convert_with_timestamps(
                voice, text=text, model_id=self.model(), output_format="mp3_44100_128")
        except Exception as e:
            raise ProviderError(f"ElevenLabs TTS failed: {str(e)[:300]}")
        audio = base64.b64decode(r.audio_base_64)
        with tempfile.TemporaryDirectory() as td:
            mp3 = os.path.join(td, "a.mp3")
            wav = os.path.join(td, "a.wav")
            open(mp3, "wb").write(audio)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "44100", wav], check=True)
            s, sr = sf.read(wav, dtype="float32")
        al = r.alignment or r.normalized_alignment
        alignment = None
        if al is not None:
            alignment = dict(chars=list(al.characters), starts=list(al.character_start_times_seconds),
                             ends=list(al.character_end_times_seconds))
        # trim leading silence and shift timing accordingly
        a = np.abs(s)
        idx = np.where(a > 0.01)[0]
        if len(idx):
            cut0 = max(0, idx[0] - int(0.03 * sr))
            s = s[cut0:idx[-1] + int(0.08 * sr)]
            if alignment:
                off = cut0 / sr
                alignment["starts"] = [max(0.0, t - off) for t in alignment["starts"]]
                alignment["ends"] = [max(0.0, t - off) for t in alignment["ends"]]
        return s, sr, alignment


def preview_path(provider_id, voice):
    d = os.path.join(CACHE_DIR, "voice_previews")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{provider_id}_{voice}.wav")


PREVIEW_TEXT = "In 1941, Japan made a very bold decision. Let's find out why."
