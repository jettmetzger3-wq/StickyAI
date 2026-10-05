"""Music providers: built-in synth (free), your own uploaded track (free), ElevenLabs Music (paid)."""
import os

from .base import MusicProvider, Cost, FREE, ProviderError
from . import elevenlabs_common as el

MOOD_PROMPTS = {
    "fun": "playful light ukulele and glockenspiel background music for a funny animated history explainer, "
           "bouncy, warm, instrumental, no vocals, loopable",
    "tense": "tense but light background music for an animated history explainer, plucked strings and soft low "
             "drums, minor key, instrumental, no vocals, loopable",
    "somber": "slow respectful sad piano and soft pad background music, quiet and gentle, instrumental, no vocals, "
              "loopable",
}


class SynthMusic(MusicProvider):
    id = "synth"
    label = "Built-in synth (free)"
    description = "Music generated in Python: ukulele strums for fun parts, plucks and drums for tense parts, " \
                  "soft piano for somber parts, crossfaded when the mood changes."
    paid = False
    quality = "good"


class UploadMusic(MusicProvider):
    id = "upload"
    label = "My own music file (free)"
    description = "Use a royalty-free track you upload (it loops under the whole video)."
    paid = False
    quality = "good"


class ElevenLabsMusic(MusicProvider):
    id = "elevenlabs_music"
    label = "ElevenLabs Music (paid)"
    description = "One AI-composed instrumental bed per mood (about 90 s each, looped under the video)."
    paid = True
    quality = "best"
    needs_keys = ("ELEVENLABS_API_KEY",)
    needs_modules = ("elevenlabs",)
    BED_SECONDS = 90

    def estimate(self, moods=(), **job):
        n = len(set(moods)) or 1
        return Cost(0.0, known=False, credit_unit="ElevenLabs credits",
                    note=f"{n} track(s) x {self.BED_SECONDS}s of music. ElevenLabs bills music from your credit "
                         f"balance; the exact rate depends on your plan, so the real usage is measured after.")

    def balance(self):
        return el.subscription()

    def beds(self, moods, total_seconds, workdir, progress=None):
        os.makedirs(workdir, exist_ok=True)
        out = {}
        ms = int(min(self.BED_SECONDS, max(30, total_seconds)) * 1000)
        moods = sorted(set(moods))
        for i, m in enumerate(moods):
            path = os.path.join(workdir, f"bed_{m}.mp3")
            if not os.path.exists(path):
                if progress:
                    progress(f"composing {m} music", i / max(1, len(moods)))
                try:
                    chunks = el.client().music.compose(prompt=MOOD_PROMPTS.get(m, MOOD_PROMPTS["fun"]),
                                                       music_length_ms=ms, force_instrumental=True)
                    with open(path + ".part", "wb") as f:
                        for c in chunks:
                            f.write(c)
                    os.replace(path + ".part", path)
                except Exception as e:
                    raise ProviderError(f"ElevenLabs music failed: {str(e)[:300]}")
            out[m] = path
        return out
