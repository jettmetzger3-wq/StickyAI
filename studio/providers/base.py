"""Provider interfaces. Every pipeline stage has one interface and several registered implementations.

A provider says whether it is free, whether it is available on this machine (keys, binaries, packages), and
how much a job will cost *before* it runs. Paid providers never run without an approval (see pipeline/costs.py).
"""
import importlib.util
import shutil
from dataclasses import dataclass, field, asdict


@dataclass
class Cost:
    usd: float = 0.0                # best dollar estimate (0 for free)
    credits: float = 0.0            # provider credits, if the provider bills in credits
    credit_unit: str = ""           # e.g. "ElevenLabs credits"
    known: bool = True              # False when the provider doesn't publish a formula we can use
    note: str = ""

    @property
    def is_free(self):
        return self.known and not self.usd and not self.credits

    def __add__(self, other):
        return Cost(round(self.usd + other.usd, 4), round(self.credits + other.credits, 1),
                    self.credit_unit or other.credit_unit, self.known and other.known,
                    "; ".join(n for n in (self.note, other.note) if n))

    def to_dict(self):
        d = asdict(self)
        d["free"] = self.is_free
        return d


FREE = Cost()


class Provider:
    id = "base"
    stage = ""
    label = ""
    description = ""
    paid = False
    quality = "good"           # basic | good | best
    needs_keys = ()            # names of secrets in .env
    needs_bins = ()            # executables on PATH
    needs_modules = ()         # python modules
    install_hint = ""

    def available(self):
        from ..config import secret
        for k in self.needs_keys:
            if not secret(k):
                return False, f"add {k} in Settings"
        for b in self.needs_bins:
            if not shutil.which(b):
                return False, f"'{b}' not found on PATH" + (f" ({self.install_hint})" if self.install_hint else "")
        for m in self.needs_modules:
            if importlib.util.find_spec(m) is None:
                return False, f"python package '{m}' missing" + (f" ({self.install_hint})" if self.install_hint else "")
        return True, ""

    def estimate(self, **job):
        return FREE

    def balance(self):
        """Remaining balance if the provider's API exposes it, else None."""
        return None

    def info(self):
        ok, why = self.available()
        return dict(id=self.id, stage=self.stage, label=self.label, description=self.description, paid=self.paid,
                    quality=self.quality, available=ok, reason=why)


# ------------------------------------------------------------------ stage interfaces
class LLMBackend(Provider):
    """Text (and optionally image) completion used by ScriptProvider and StoryboardProvider."""
    stage = "llm"
    supports_images = False
    supports_schema = False
    supports_web = False

    def complete(self, system, prompt, schema=None, images=(), max_tokens=16000, model=None, label="", web=False):
        """Return (text, usage dict). `schema` is a JSON schema the backend may enforce. `web`: allow web search
        (only backends with supports_web; others ignore it)."""
        raise NotImplementedError

    def estimate_tokens(self, in_chars, out_tokens, model=None):
        return FREE


class TranscriptProvider(Provider):
    stage = "transcript"

    def transcript(self, url, meta, workdir, progress=None):
        """Return list of {start, end, text} segments."""
        raise NotImplementedError


class VoiceProvider(Provider):
    stage = "voice"

    def voices(self):
        return []

    def synthesize(self, text, voice=None, speed=1.0):
        """Return (samples float32 mono, sample_rate, alignment) where alignment is None or
        dict(chars=[...], starts=[...], ends=[...]) in seconds for the given text."""
        raise NotImplementedError


class MusicProvider(Provider):
    stage = "music"

    def beds(self, moods, total_seconds, workdir, progress=None):
        """Return {mood: path_to_audio} or {} to use the built-in synth."""
        return {}


class ImageProvider(Provider):
    stage = "image"
    watermark_warning = ""

    def generate(self, prompt, out_path, aspect="16:9"):
        raise NotImplementedError


class NeedsSetup(Exception):
    pass


class ProviderError(Exception):
    pass


__all__ = ["Cost", "FREE", "Provider", "LLMBackend", "TranscriptProvider", "VoiceProvider", "MusicProvider",
           "ImageProvider", "NeedsSetup", "ProviderError", "field"]
