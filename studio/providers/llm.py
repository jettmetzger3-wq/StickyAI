"""LLM backends used to write scripts, storyboards and YouTube metadata.

- claude_cli: the `claude` command in headless mode, which runs on your Claude subscription (no API bill).
- anthropic:  the Anthropic API with your key (paid per token, estimate shown first).
- ollama:     a local model through Ollama (free, lower quality).
- gemini / groq: free API keys (see free_llm.py).
- offline:    no AI at all; the pipeline uses simple rules instead (for testing).
"""
import base64
import contextlib
import contextvars
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile

from .base import LLMBackend, Cost, FREE, ProviderError
from ..config import load_settings, secret


def extract_json(text):
    """Pull the first JSON object/array out of an LLM reply (handles ```json fences and chatter)."""
    if text is None:
        raise ValueError("empty reply")
    if isinstance(text, (dict, list)):
        return text
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m and m.group(1).strip()[:1] in "{[":
        s = m.group(1).strip()
    start = min([i for i in (s.find("{"), s.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON found in reply")
    s = s[start:]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # find the matching closing bracket
    depth, in_str, esc, end = 0, False, False, -1
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    cand = s[:end] if end > 0 else s
    try:
        return json.loads(cand)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", cand)          # trailing commas
        fixed = re.sub(r"(?<!\\)'", '"', fixed) if fixed.count('"') < 2 else fixed
        return json.loads(fixed)


# ------------------------------------------------------------------ Claude Code CLI
class ClaudeCLI(LLMBackend):
    id = "claude_cli"
    short = "Claude"
    label = "Claude Code (my subscription)"
    description = "Runs `claude -p` on this PC, so it uses your Claude plan instead of API credits."
    paid = False
    quality = "best"
    supports_images = True
    supports_schema = True
    supports_web = True          # Claude Code can search the web on your plan (used by the fact-check)
    install_hint = "install Claude Code and log in once with `claude`"

    def path(self):
        p = load_settings().get("claude_cli_path") or ""
        if p and os.path.exists(p):
            return p
        return shutil.which("claude") or shutil.which("claude.cmd") or shutil.which("claude.exe")

    def available(self):
        if not self.path():
            return False, "the `claude` command was not found (" + self.install_hint + ")"
        return True, ""

    def command(self):
        """The command prefix to run Claude Code. On Windows, npm installs a `claude.cmd` wrapper; going through
        cmd.exe would mangle quotes in our arguments (JSON schema, prompts), so we call its Node script directly."""
        exe = self.path()
        if exe and os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
            base = os.path.dirname(exe)
            js = os.path.join(base, "node_modules", "@anthropic-ai", "claude-code", "cli.js")
            node = os.path.join(base, "node.exe")
            if os.path.exists(js):
                return [node if os.path.exists(node) else (shutil.which("node") or "node"), js]
        return [exe]

    def estimate_tokens(self, in_chars, out_tokens, model=None):
        return Cost(0.0, note="uses your Claude subscription's usage limits, no API charges")

    def complete(self, system, prompt, schema=None, images=(), max_tokens=16000, model=None, label="", web=False):
        if not self.path():
            raise ProviderError("claude CLI not found")
        model = model or load_settings().get("llm_models", {}).get("claude_cli") or None
        env = dict(os.environ)
        # Make sure the CLI bills your subscription, never an API key that happens to be in .env
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            env.pop(k, None)
        with tempfile.TemporaryDirectory(prefix="studio_claude_") as td:
            cmd = self.command() + ["-p", "--output-format", "json", "--no-session-persistence"]
            if images:
                names = []
                for i, src in enumerate(images):
                    ext = os.path.splitext(src)[1] or ".jpg"
                    dst = os.path.join(td, f"image_{i + 1:02d}{ext}")
                    shutil.copy(src, dst)
                    names.append(os.path.basename(dst))
                cmd += ["--tools", "Read", "--allowedTools", "Read"]
                prompt = (f"First use the Read tool to look at these image files in the current folder: "
                          f"{', '.join(names)}.\n\n" + prompt)
            elif web:
                cmd += ["--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch"]
            else:
                cmd += ["--tools", ""]
            if system:
                cmd += ["--system-prompt", system[:4000]]
            if schema:
                cmd += ["--json-schema", json.dumps(schema, separators=(",", ":"))]
            if model:
                cmd += ["--model", model]
            try:
                r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=1800, cwd=td, env=env)
            except subprocess.TimeoutExpired:
                raise ProviderError("claude CLI timed out after 30 minutes")
        out = r.stdout.strip()
        try:
            data = json.loads(out[out.find("{"):]) if out else {}
        except json.JSONDecodeError:
            raise ProviderError(f"claude CLI returned something unexpected: {out[:300]} {r.stderr[:300]}")
        if data.get("is_error") or data.get("subtype") not in (None, "success"):
            msg = data.get("result") or r.stderr or "unknown error"
            raise ProviderError(f"claude CLI error: {str(msg)[:500]}")
        text = data.get("result", "")
        if schema and data.get("structured_output") is not None:
            text = json.dumps(data["structured_output"])
        usage = dict(provider=self.id, api_equivalent_usd=data.get("total_cost_usd"), billed_usd=0.0,
                     num_turns=data.get("num_turns"))
        return text, usage


# ------------------------------------------------------------------ Anthropic API
PRICES = {  # USD per million tokens (input, output)
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")

# Per-run model choice (hosted mode: each plan can pick its Anthropic model). Set by the runner for one run.
MODEL_OVERRIDE = contextvars.ContextVar("studio_llm_model", default=None)


@contextlib.contextmanager
def using_model(model):
    tok = MODEL_OVERRIDE.set(model or None)
    try:
        yield
    finally:
        MODEL_OVERRIDE.reset(tok)


class AnthropicAPI(LLMBackend):
    id = "anthropic"
    short = "Claude"
    label = "Anthropic API (pay per use)"
    description = "Uses your ANTHROPIC_API_KEY. Billed per token; you approve an estimate first."
    paid = True
    quality = "best"
    supports_images = True
    supports_schema = True
    needs_keys = ("ANTHROPIC_API_KEY",)
    needs_modules = ("anthropic",)

    def model(self, model=None):
        return model or MODEL_OVERRIDE.get() or load_settings().get("llm_models", {}).get("anthropic") or "claude-opus-5-5"

    def estimate_tokens(self, in_chars, out_tokens, model=None):
        m = self.model(model)
        pin, pout = PRICES.get(m, PRICES["claude-opus-5-5"])
        tin = in_chars / 3.5
        tout = out_tokens * 1.6  # thinking tokens are billed as output too; add headroom
        usd = tin / 1e6 * pin + tout / 1e6 * pout
        return Cost(round(usd, 3), note=f"{m}: ~{int(tin):,} input + ~{int(tout):,} output tokens")

    def complete(self, system, prompt, schema=None, images=(), max_tokens=16000, model=None, label="", web=False):
        import anthropic
        m = self.model(model)
        client = anthropic.Anthropic(api_key=secret("ANTHROPIC_API_KEY"))
        content = []
        for img in images or ():
            mt = mimetypes.guess_type(img)[0] or "image/jpeg"
            with open(img, "rb") as f:
                content.append({"type": "image", "source": {"type": "base64", "media_type": mt,
                                                            "data": base64.standard_b64encode(f.read()).decode()}})
        content.append({"type": "text", "text": prompt})
        kwargs = dict(model=m, max_tokens=max(max_tokens, 32000), messages=[{"role": "user", "content": content}])
        if system:
            kwargs["system"] = system
        output_config = {}
        if m.startswith("claude-opus-5") or m.startswith("claude-sonnet-5"):
            output_config["effort"] = "medium"
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if output_config:
            kwargs["output_config"] = output_config
        if m in FALLBACK_MODELS:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        try:
            if "betas" in kwargs:
                with client.beta.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
            else:
                with client.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
        except anthropic.AuthenticationError:
            raise ProviderError("Anthropic API key was rejected")
        except anthropic.RateLimitError:
            raise ProviderError("Anthropic API rate limit hit; try again in a minute")
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Anthropic API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            raise ProviderError("could not reach the Anthropic API")
        if msg.stop_reason == "refusal":
            raise ProviderError("the model declined this request")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        u = msg.usage
        pin, pout = PRICES.get(m, PRICES["claude-opus-5-5"])
        tin = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) * 1.25 \
            + (getattr(u, "cache_read_input_tokens", 0) or 0) * 0.1
        billed = tin / 1e6 * pin + (u.output_tokens or 0) / 1e6 * pout
        if msg.stop_reason == "max_tokens":
            raise ProviderError("reply was cut off (max_tokens); try a shorter video or fewer beats")
        return text, dict(provider=self.id, model=getattr(msg, "model", m), input_tokens=u.input_tokens,
                          output_tokens=u.output_tokens, billed_usd=round(billed, 4))


# ------------------------------------------------------------------ Ollama (local)
class Ollama(LLMBackend):
    id = "ollama"
    short = "The local AI"
    label = "Ollama (local model)"
    description = "A free model running on your own PC through Ollama. Lower quality than Claude."
    paid = False
    quality = "basic"
    supports_images = True
    supports_schema = True
    install_hint = "install Ollama from ollama.com and run `ollama pull llama3.1`"

    def url(self):
        return (load_settings().get("ollama_url") or "http://localhost:11434").rstrip("/")

    def available(self):
        import httpx
        try:
            r = httpx.get(self.url() + "/api/tags", timeout=1.5)
            if r.status_code == 200:
                return True, ""
        except Exception:
            pass
        return False, "Ollama is not running (" + self.install_hint + ")"

    def complete(self, system, prompt, schema=None, images=(), max_tokens=16000, model=None, label="", web=False):
        import httpx
        m = model or load_settings().get("llm_models", {}).get("ollama") or "llama3.1"
        msg = {"role": "user", "content": prompt}
        if images:
            msg["images"] = [base64.standard_b64encode(open(p, "rb").read()).decode() for p in images]
        body = {"model": m, "stream": False, "messages": ([{"role": "system", "content": system}] if system else []) + [msg],
                "options": {"num_ctx": 32768}, "format": schema or "json"}
        try:
            r = httpx.post(self.url() + "/api/chat", json=body, timeout=1800)
            r.raise_for_status()
        except Exception as e:
            raise ProviderError(f"Ollama error: {e}")
        return r.json().get("message", {}).get("content", ""), dict(provider=self.id, model=m, billed_usd=0.0)


class OfflineLLM(LLMBackend):
    id = "offline"
    short = "Basic mode"
    label = "Basic (no AI, for testing)"
    description = "No language model. Uses simple rules: scenes are generic and a YouTube remake just reuses " \
                  "the transcript text, so only use it to test the pipeline."
    paid = False
    quality = "basic"

    def complete(self, *a, **k):
        raise ProviderError("offline mode has no language model")
