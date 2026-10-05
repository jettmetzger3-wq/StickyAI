"""Provider registry: one dropdown per stage. The free provider is always listed first and is the default."""
from .base import Cost, FREE, Provider, ProviderError, NeedsSetup
from .llm import ClaudeCLI, AnthropicAPI, Ollama, OfflineLLM, extract_json
from .voice import Kokoro, ElevenLabsVoice, SystemVoice
from .music import SynthMusic, UploadMusic, ElevenLabsMusic
from .transcript import YouTubeCaptions, WhisperLocal, ElevenLabsScribe, video_id
from .image import LocalImage, ElevenLabsImage, HiggsfieldImage

REGISTRY = {
    "llm": [ClaudeCLI(), AnthropicAPI(), Ollama(), OfflineLLM()],
    "voice": [Kokoro(), ElevenLabsVoice(), SystemVoice()],
    "music": [SynthMusic(), UploadMusic(), ElevenLabsMusic()],
    "transcript": [YouTubeCaptions(), WhisperLocal(), ElevenLabsScribe()],
    "image": [LocalImage(), ElevenLabsImage(), HiggsfieldImage()],
}

STAGE_LABELS = {
    "transcript": "Transcript (YouTube remake)",
    "llm": "Writer (script, storyboard, title)",
    "voice": "Voice",
    "music": "Music",
    "image": "Thumbnail art",
}

# Quality presets the New Video form offers. "free" never costs anything.
TIERS = {
    "free": {"transcript": "youtube_captions", "llm": "claude_cli", "voice": "kokoro", "music": "synth", "image": "local"},
    "pro": {"transcript": "youtube_captions", "llm": "anthropic", "voice": "elevenlabs", "music": "elevenlabs_music",
            "image": "elevenlabs_image"},
}


def get(stage, pid):
    for p in REGISTRY.get(stage, []):
        if p.id == pid:
            return p
    raise KeyError(f"unknown {stage} provider '{pid}'")


def catalog():
    return {stage: [p.info() for p in ps] for stage, ps in REGISTRY.items()}


__all__ = ["REGISTRY", "STAGE_LABELS", "TIERS", "get", "catalog", "Cost", "FREE", "Provider", "ProviderError",
           "NeedsSetup", "extract_json", "video_id"]
