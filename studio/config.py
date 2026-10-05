"""Paths, settings and secrets.

Secrets (API keys) live in .env at the repo root (gitignored). Everything else lives in data/settings.json.
Secrets are never logged or sent to the browser; the API only reports whether a key is set.
"""
import json
import os
import re
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("STUDIO_DATA_DIR", os.path.join(ROOT, "data"))
PROJECTS_DIR = os.environ.get("STUDIO_PROJECTS_DIR", os.path.join(ROOT, "projects"))
MODELS_DIR = os.path.join(DATA_DIR, "models")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
ENV_FILE = os.path.join(ROOT, ".env")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
WEB_DIST = os.path.join(ROOT, "web", "dist")

SECRET_KEYS = {
    "ANTHROPIC_API_KEY": "Anthropic API key (paid script/storyboard writer)",
    "ELEVENLABS_API_KEY": "ElevenLabs API key (voice, music, transcripts, images)",
    "HF_API_KEY": "Higgsfield API key (images)",
    "HF_API_SECRET": "Higgsfield API secret (images)",
}

DEFAULT_SETTINGS = {
    "port": 8765,
    "autopilot": True,
    "providers": {
        "transcript": "youtube_captions",
        "watch": "auto",
        "llm": "claude_cli",
        "voice": "kokoro",
        "music": "synth",
        "image": "local",
    },
    "llm_models": {"claude_cli": "", "anthropic": "claude-opus-5-5", "ollama": "llama3.1"},
    "ollama_url": "http://localhost:11434",
    "claude_cli_path": "",
    "voice": {
        "kokoro_voice": "am_michael",
        "kokoro_speed": 1.2,
        "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb",
        "elevenlabs_voice_name": "George",
        "elevenlabs_model": "eleven_flash_v2_5",
        "system_voice": "",
    },
    # Only used to turn ElevenLabs credits into an approximate dollar figure. Default = Creator plan
    # ($22 for 100k credits). Change it to match your plan.
    "elevenlabs_usd_per_1k_credits": 0.22,
    "pronunciations": {},
    "music_db": -13.0,
    "share_copy": True,
    "share_max_mb": 30,
    "render_workers": 0,
}

_lock = threading.Lock()


def ensure_dirs():
    for d in (DATA_DIR, PROJECTS_DIR, MODELS_DIR, CACHE_DIR):
        os.makedirs(d, exist_ok=True)


# ------------------------------------------------------------------ .env
def read_env_file(path=ENV_FILE):
    vals = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                vals[k.strip()] = v
    except OSError:
        pass
    return vals


def load_env():
    """Put .env values into os.environ (without overriding variables that are already set)."""
    for k, v in read_env_file().items():
        if k not in os.environ or not os.environ[k]:
            os.environ[k] = v


def secret(name):
    v = os.environ.get(name)
    if v:
        return v
    return read_env_file().get(name, "")


def set_secret(name, value):
    """Write/replace one key in .env (creates the file). An empty value removes the key."""
    if not re.match(r"^[A-Z0-9_]+$", name):
        raise ValueError("bad key name")
    with _lock:
        lines = []
        try:
            with open(ENV_FILE, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            pass
        lines = [l for l in lines if not l.strip().startswith(name + "=")]
        if value:
            lines.append(f"{name}={value}")
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def secrets_status():
    return {k: {"label": v, "set": bool(secret(k))} for k, v in SECRET_KEYS.items()}


def mask(s):
    if not s:
        return ""
    return s[:3] + "…" + s[-2:] if len(s) > 8 else "set"


# ------------------------------------------------------------------ settings.json
def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings():
    ensure_dirs()
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            user = json.load(f)
    except (OSError, ValueError):
        user = {}
    return _merge(DEFAULT_SETTINGS, user)


def save_settings(new):
    ensure_dirs()
    with _lock:
        cur = load_settings()
        merged = _merge(cur, new)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)
    return merged


load_env()
