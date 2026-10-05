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
ENV_FILE = os.environ.get("STUDIO_ENV_FILE") or os.path.join(ROOT, ".env")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
WEB_DIST = os.path.join(ROOT, "web", "dist")

# "local" (default): the app runs on your PC for you alone.
# "hosted": a public website with accounts, plans and Stripe billing (see DEPLOY.md).
MODE = os.environ.get("STUDIO_MODE", "local").strip().lower()
PUBLIC_URL = os.environ.get("STUDIO_PUBLIC_URL", "http://localhost:8765").rstrip("/")


def hosted():
    return MODE == "hosted"


def private():
    """Your own studio online, for you alone: hosted mode on your PC behind a free Cloudflare link
    (python -m studio online / start.bat online). One owner account, no sign-ups, no plans."""
    return hosted() and os.environ.get("STUDIO_PRIVATE") == "1"


def ytdlp_opts(**kw):
    """yt-dlp options. YouTube often blocks server IPs; STUDIO_YTDLP_COOKIES can point at a cookies.txt export."""
    cookies = os.environ.get("STUDIO_YTDLP_COOKIES", "")
    if cookies and os.path.exists(cookies):
        kw["cookiefile"] = cookies
    return kw

SECRET_KEYS = {
    "ANTHROPIC_API_KEY": "Anthropic API key (paid script/storyboard writer)",
    "ELEVENLABS_API_KEY": "ElevenLabs API key (voice, music, transcripts, images)",
    "HF_API_KEY": "Higgsfield API key (images)",
    "HF_API_SECRET": "Higgsfield API secret (images)",
    "STRIPE_SECRET_KEY": "Stripe secret key (hosted mode: take payments)",
    "STRIPE_WEBHOOK_SECRET": "Stripe webhook signing secret (hosted mode)",
    "STRIPE_PRICE_PRO": "Stripe Price ID of the Pro monthly subscription (price_...)",
    "STRIPE_PRICE_PACK": "Stripe Price ID of the +10 Pro minutes pack (price_...)",
    "STUDIO_LINK_SECRET": "Netlify site: the secret that lets this PC post its online link (same value as on Netlify)",
}

DEFAULT_SETTINGS = {
    "port": 8765,
    # Your Netlify website (e.g. https://stickman-studio.netlify.app). While `start.bat online` runs, this PC tells
    # it the current link, so its "Open my studio" button always works. Empty = off.
    "netlify_site": "",
    "autopilot": True,
    "providers": {
        "transcript": "youtube_captions",
        "llm": "claude_cli",
        "voice": "kokoro",
        "music": "synth",
        "image": "local",
        "shorts": "stickman",
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
    "reuse_music_beds": True,          # pay for each ElevenLabs music mood once, reuse it in later videos
    "share_copy": True,
    "share_max_mb": 30,
    "render_workers": 0,
    # Local mode safety net: the run pauses and asks again before one video's spending goes over this.
    "max_usd_per_video": 15.0,
    "calliope": {
        "server": "calliope",          # MCP server name in Claude Code (tools are mcp__<server>__<tool>)
        "template_id": "",             # optional Calliope template for Shorts; empty = most popular short template
        "quality": "medium",           # medium | high | extra
        "usd_per_1k_credits": 0.0,     # set to your Calliope plan's rate to see dollar estimates
        "ai_short_minutes": 5,         # hosted mode: one AI Short uses this many Pro minutes
        "bridge_model": "",            # Claude model Claude Code uses to relay the tool calls (empty = its default)
        "connected": False,            # set by Settings > Calliope > Test connection
    },
    # Hosted mode only (STUDIO_MODE=hosted)
    "hosted": {
        # Start free-only: no Pro plan, no payments. Turn this on once people use the site (needs Stripe keys).
        "paid_plans": False,
        # Most the website may spend on AI tools (Anthropic, ElevenLabs) per calendar month for everyone's videos
        # but the admins'. When it's used up, new videos wait until the 1st. 0 = no limit.
        "monthly_budget_usd": 20.0,
        "allow_signup": True,
        "max_concurrent_runs": 2,
        "max_usd_per_video": 8.0,      # refuse jobs whose estimated tool cost is above this
        "ai_edits_per_video": 40,      # beat rewrites / scene redraws per video (stage re-runs count 10)
        "watermark_text": "Made with Stickman Studio",
        # Calliope AI Shorts on the website run through Claude Code on the server with an Anthropic API key and
        # your Calliope account. Off until you set that up and set calliope.usd_per_1k_credits.
        "ai_shorts": False,
        "plans": {
            "free": {
                "name": "Free", "price_usd": 0, "videos_per_month": 2, "max_minutes": 3, "pro_minutes": 0,
                "watermark": True, "shorts": ["stickman"],
                "providers": {"transcript": "youtube_captions", "llm": "anthropic", "voice": "kokoro",
                              "music": "synth", "image": "local", "shorts": "stickman"},
                "llm_model": "claude-opus-5-5",
            },
            "pro": {
                "name": "Pro", "price_usd": 19.99, "videos_per_month": 0, "max_minutes": 15, "pro_minutes": 30,
                "watermark": False, "shorts": ["stickman", "calliope"],
                "providers": {"transcript": "youtube_captions", "llm": "anthropic", "voice": "elevenlabs",
                              "music": "elevenlabs_music", "image": "elevenlabs_image", "shorts": "stickman"},
                "llm_model": "claude-opus-5-5",
            },
        },
        "pack": {"name": "+10 Pro minutes", "price_usd": 5.99, "minutes": 10},
    },
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
