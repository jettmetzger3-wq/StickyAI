"""Free API writers: Google Gemini and Groq, through their official OpenAI-compatible endpoints.

- Gemini: https://generativelanguage.googleapis.com/v1beta/openai/ with a free key from Google AI Studio.
- Groq:   https://api.groq.com/openai/v1 with a free key from console.groq.com.

Both have free tiers with request and token limits (no card needed). A key can only cost money if you turn on
billing for it yourself (a Google Cloud project with billing, or Groq's paid tier), so Settings says to keep the
key on a free project. The studio counts requests per day, waits when a per-minute limit is hit, and stops with
a clear message when the daily limit is used up (press Resume the next day or pick another writer).
"""
import base64
import json
import mimetypes
import os
import re
import threading
import time

from .base import LLMBackend, Cost, ProviderError
from ..config import load_settings, secret, DATA_DIR


class TooLarge(ProviderError):
    """The request is bigger than the provider's free per-minute token limit (send less at once)."""


class DailyLimit(ProviderError):
    """The free daily limit is used up."""


_usage_lock = threading.Lock()


def usage_file():
    return os.path.join(DATA_DIR, "writer_usage.json")


def _read_usage():
    try:
        with open(usage_file(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_usage(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = usage_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, usage_file())


def today():
    # free daily limits reset at midnight Pacific time for both providers; local date is close enough for a counter
    return time.strftime("%Y-%m-%d")


def wait_seconds(text, default=None):
    """'try again in 1m26.4s' / 'retry in 37.5s' / 'retryDelay': '12s' -> seconds."""
    s = str(text or "")
    m = re.search(r"(?:try again|retry) in\s+(?:(\d+)h)?\s*(?:(\d+)m(?!s))?\s*(?:([\d.]+)s)?", s, re.I)
    if m and any(m.groups()):
        h, mi, se = (float(g) if g else 0.0 for g in m.groups())
        return h * 3600 + mi * 60 + se
    m = re.search(r'"?retryDelay"?\s*[:=]\s*"?([\d.]+)s', s)
    if m:
        return float(m.group(1))
    return default


def is_daily(text):
    t = str(text or "").lower()
    return any(k in t for k in ("per day", "perday", "requests per day", "(rpd)", "tokens per day", "(tpd)",
                                "daily"))


def is_too_large(status, text):
    t = str(text or "").lower()
    return status == 413 or "request too large" in t or "context_length_exceeded" in t or \
        ("too large" in t and "token" in t) or "reduce your message size" in t


def _error_text(r):
    try:
        data = r.json()
    except ValueError:
        return r.text[:600]
    if isinstance(data, list) and data:
        data = data[0]
    e = data.get("error") if isinstance(data, dict) else None
    if isinstance(e, dict):
        msg = e.get("message") or ""
        det = e.get("details")
        return (msg + (" " + json.dumps(det)[:400] if det else "")).strip()
    return json.dumps(data)[:600]


class OpenAICompat(LLMBackend):
    """A chat-completions endpoint that follows OpenAI's format."""
    base_url = ""
    key_name = ""
    default_model = ""
    short = "The AI"
    paid = False
    quality = "good"
    supports_schema = False          # we ask for JSON mode and put the schema in the prompt
    supports_images = False
    min_gap = 2.0                    # seconds between requests (free per-minute request limits)
    max_out = 16000
    # how the pipeline should size its requests for this writer's free limits
    batch_beats = 8                  # scenes per storyboard request
    parallel = 1                     # storyboard requests at the same time
    examples = 20                    # example scenes shown in each storyboard request
    compact = False                  # shorter scene-language instructions
    signup = ""
    shows_usage = True               # Settings shows today's usage / what's left of the free limit

    def __init__(self):
        self._last = 0.0
        self._lock = threading.Lock()
        self.limits = {}             # rate-limit numbers the provider reported on its last answer

    # ---------------------------------------------------------------- settings
    def model(self, model=None):
        return model or load_settings().get("llm_models", {}).get(self.id) or self.default_model

    def key(self):
        return secret(self.key_name)

    def available(self):
        if not self.key():
            return False, f"add your free {self.key_name} in Settings > API keys ({self.signup})"
        return True, ""

    def estimate_tokens(self, in_chars, out_tokens, model=None):
        return Cost(0.0, note=f"free {self.short} key: uses requests from your free daily limit, no charges")

    # ---------------------------------------------------------------- usage counter
    def count_request(self, tokens=0):
        with _usage_lock:
            data = _read_usage()
            day = data.setdefault(self.id, {})
            for k in [k for k in day if k != today()]:
                day.pop(k, None)
            d = day.setdefault(today(), {"requests": 0, "tokens": 0})
            d["requests"] += 1
            d["tokens"] += int(tokens or 0)
            if self.limits:
                d["limits"] = self.limits
            _write_usage(data)

    def used_today(self):
        return (_read_usage().get(self.id) or {}).get(today()) or {"requests": 0, "tokens": 0}

    def remember_limits(self, headers):
        pass

    def balance(self):
        u = self.used_today()
        return dict(used=u.get("requests", 0), unit="requests today", tier="free",
                    text=f"{u.get('requests', 0)} requests used today")

    # ---------------------------------------------------------------- request
    def extra_body(self, model, label):
        return {}

    def messages(self, system, prompt, images):
        content = [{"type": "text", "text": prompt}]
        for img in images or ():
            mt = mimetypes.guess_type(img)[0] or "image/jpeg"
            with open(img, "rb") as f:
                url = f"data:{mt};base64," + base64.standard_b64encode(f.read()).decode()
            content.append({"type": "image_url", "image_url": {"url": url}})
        msgs = [{"role": "system", "content": system}] if system else []
        msgs.append({"role": "user", "content": content if images else prompt})
        return msgs

    def _pace(self):
        with self._lock:
            gap = self.min_gap - (time.time() - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.time()

    def complete(self, system, prompt, schema=None, images=(), max_tokens=16000, model=None, label="", web=False):
        import httpx
        key = self.key()
        if not key:
            raise ProviderError(f"{self.key_name} is not set (Settings > API keys)")
        m = self.model(model)
        if schema:
            prompt = (prompt + "\n\nReply with one JSON object that follows this JSON schema exactly:\n"
                      + json.dumps(schema, separators=(",", ":")))
        if "json" not in (system + prompt).lower():
            prompt += "\n\nReply with JSON only."
        body = {"model": m, "messages": self.messages(system, prompt, images),
                "max_tokens": int(min(max_tokens, self.max_out)), "response_format": {"type": "json_object"}}
        body.update(self.extra_body(m, label))
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        waited = 0.0
        for attempt in range(8):
            self._pace()
            try:
                r = httpx.post(self.base_url + "/chat/completions", json=body, headers=headers, timeout=600)
            except httpx.HTTPError as e:
                if attempt >= 3:
                    raise ProviderError(f"could not reach {self.short}: {e}")
                time.sleep(3 * (attempt + 1))
                continue
            self.remember_limits(r.headers)
            if r.status_code == 200:
                break
            err = _error_text(r)
            if r.status_code in (401, 403):
                raise ProviderError(f"{self.short} refused the key ({r.status_code}): {err[:200]}. "
                                    f"Check {self.key_name} in Settings.")
            if is_too_large(r.status_code, err):
                raise TooLarge(f"{self.short}: this request is bigger than the free per-minute limit ({err[:200]})")
            if r.status_code == 400 and "response_format" in body and \
                    any(k in err.lower() for k in ("response_format", "json mode", "json_object", "json_validate")):
                body.pop("response_format")          # some models don't do JSON mode; the prompt still asks for JSON
                continue
            if r.status_code == 429:
                if is_daily(err):
                    raise DailyLimit(f"{self.short}'s free daily limit is used up ({err[:160]}). Press Resume "
                                     f"tomorrow, or pick another writer in Settings.")
                ra = r.headers.get("retry-after")
                try:
                    wait = float(ra)
                except (TypeError, ValueError):
                    wait = wait_seconds(err, default=min(60, 5 * 2 ** attempt))
                if waited + wait > 600:
                    raise ProviderError(f"{self.short} kept saying 'too many requests' ({err[:160]})")
                time.sleep(wait + 0.5)
                waited += wait
                continue
            if r.status_code >= 500:
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            raise ProviderError(f"{self.short} error {r.status_code}: {err[:300]}")
        else:
            raise ProviderError(f"{self.short} didn't answer after several tries")
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        u = data.get("usage") or {}
        self.count_request(u.get("total_tokens") or 0)
        if choice.get("finish_reason") == "length":
            raise TooLarge(f"{self.short}'s reply was cut off (too long for one answer)")
        if not text.strip():
            raise ProviderError(f"{self.short} sent an empty reply")
        return text, dict(provider=self.id, model=m, input_tokens=u.get("prompt_tokens", 0),
                          output_tokens=u.get("completion_tokens", 0), billed_usd=0.0)

    # ---------------------------------------------------------------- models
    def list_models(self):
        import httpx
        key = self.key()
        if not key:
            return []
        r = httpx.get(self.base_url + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
        if r.status_code != 200:
            raise ProviderError(f"{self.short} error {r.status_code}: {_error_text(r)[:200]}")
        ids = [str(x.get("id", "")) for x in r.json().get("data") or []]
        return sorted({i.split("/", 1)[1] if i.startswith("models/") else i for i in ids if self.chat_model(i)})

    def chat_model(self, mid):
        return bool(mid)


class Gemini(OpenAICompat):
    id = "gemini"
    label = "Google Gemini (free API key)"
    description = ("Free key from Google AI Studio (aistudio.google.com/apikey), no card. Good scripts and titles; "
                   "scenes are a bit plainer than Claude's. Free requests per day are limited (AI Studio shows "
                   "yours); a 10-minute video needs about 12-20. Free-tier prompts may be used by Google to "
                   "improve its products.")
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    key_name = "GEMINI_API_KEY"
    default_model = "gemini-flash-latest"
    short = "Gemini"
    quality = "good"
    supports_images = True
    min_gap = 7.0                    # stays under ~10 requests per minute
    max_out = 60000
    batch_beats = 16                 # big context: fewer, larger requests save the daily request limit
    parallel = 1
    examples = 20
    signup = "free at aistudio.google.com/apikey"

    def chat_model(self, mid):
        m = mid.lower()
        return "gemini" in m and not any(k in m for k in ("embedding", "tts", "image", "audio", "live", "veo"))


class Groq(OpenAICompat):
    id = "groq"
    label = "Groq (free API key)"
    description = ("Free key from console.groq.com, no card. Very fast. Its free limits are small (about 8,000 "
                   "tokens a minute and 1,000 requests a day), so scenes are drawn two at a time with shorter "
                   "instructions; best for scripts, fact-checks and titles.")
    base_url = "https://api.groq.com/openai/v1"
    key_name = "GROQ_API_KEY"
    default_model = "openai/gpt-oss-120b"
    short = "Groq"
    quality = "basic"
    min_gap = 2.2                    # 30 requests per minute
    max_out = 6000
    batch_beats = 2
    parallel = 1
    examples = 3
    compact = True
    signup = "free at console.groq.com/keys"

    def extra_body(self, model, label):
        # gpt-oss models think before answering; keep that short so it fits the free token limits
        return {"reasoning_effort": "low"} if model.startswith("openai/gpt-oss") else {}

    def remember_limits(self, headers):
        lim = {}
        for k, name in (("x-ratelimit-limit-requests", "rpd"), ("x-ratelimit-remaining-requests", "rpd_left"),
                        ("x-ratelimit-limit-tokens", "tpm"), ("x-ratelimit-remaining-tokens", "tpm_left")):
            v = headers.get(k)
            if v and str(v).isdigit():
                lim[name] = int(v)
        if lim:
            self.limits = lim
            if lim.get("tpm") and lim["tpm"] < 12000:
                self.batch_beats, self.examples = 2, 3
            elif lim.get("tpm"):
                self.batch_beats, self.examples = 6, 10

    def balance(self):
        u = self.used_today()
        lim = self.limits or u.get("limits") or {}
        if lim.get("rpd"):
            left = lim.get("rpd_left", max(0, lim["rpd"] - u.get("requests", 0)))
            return dict(remaining=left, limit=lim["rpd"], unit="requests today", tier="free",
                        text=f"{left:,} of {lim['rpd']:,} free requests left today")
        return super().balance()

    def chat_model(self, mid):
        m = mid.lower()
        return not any(k in m for k in ("whisper", "tts", "guard", "playai", "orpheus", "distil"))
