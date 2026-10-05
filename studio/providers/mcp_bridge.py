"""Call one tool of an MCP connector through Claude Code (`claude -p`).

Some services (Calliope, later Korpi) are only reachable as MCP connectors, not as a plain web API. Claude Code
can talk to MCP servers, so we ask it to make exactly one tool call with exactly our arguments and read the raw
tool result from its event stream (we never trust a retyped copy of the result).

One-time setup on your PC (once per service):
    claude mcp add --transport http calliope https://www.calliopelabs.co/api/mcp
then run `claude`, type /mcp and log in to Calliope. Tools are then named mcp__calliope__<tool>.
"""
import json
import os
import subprocess
import tempfile

from ..config import hosted, private, load_settings
from .base import ProviderError


def tool_name(server, tool):
    return f"mcp__{server}__{tool}"


def parse_stream(lines, name):
    """Find our tool call and its result in Claude Code's stream-json output. Returns (result, is_error, final)."""
    call_ids, result, is_error, final = set(), None, False, None
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        typ = ev.get("type")
        content = ((ev.get("message") or {}).get("content")) or []
        if typ == "assistant":
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_use" and c.get("name") == name:
                    call_ids.add(c.get("id"))
        elif typ == "user":
            for c in content if isinstance(content, list) else []:
                if c.get("type") == "tool_result" and c.get("tool_use_id") in call_ids and result is None:
                    raw = c.get("content")
                    if isinstance(raw, list):
                        raw = "".join(x.get("text", "") for x in raw if isinstance(x, dict) and x.get("type") == "text")
                    result, is_error = raw, bool(c.get("is_error"))
        elif typ == "result":
            final = ev
    return result, is_error, final, bool(call_ids)


def decode(result):
    if isinstance(result, (dict, list)):
        return result
    s = (result or "").strip()
    try:
        return json.loads(s)
    except ValueError:
        i = s.find("{")
        if i >= 0:
            try:
                return json.loads(s[i:s.rfind("}") + 1])
            except ValueError:
                pass
    return {"text": s}


def call_tool(server, tool, args, timeout=300):
    """Run exactly one MCP tool call through Claude Code and return its decoded result."""
    from .llm import ClaudeCLI
    cli = ClaudeCLI()
    if not cli.path():
        raise ProviderError("this needs Claude Code (the `claude` command) with the connector added")
    name = tool_name(server, tool)
    env = dict(os.environ)
    if not hosted() or private():
        # your own videos: use your Claude subscription, never an API key that happens to be in .env
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            env.pop(k, None)
    model = (load_settings().get("calliope") or {}).get("bridge_model") or ""
    prompt = (f"Call the tool {name} exactly once with exactly these JSON arguments, unchanged:\n"
              f"{json.dumps(args, ensure_ascii=False)}\n"
              f"Do not call any other tool. After the tool returns, reply with the single word DONE.")
    cmd = cli.command() + ["-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
                           "--tools", "", "--allowedTools", name, "--max-turns", "3"]
    if model:
        cmd += ["--model", model]
    with tempfile.TemporaryDirectory(prefix="studio_mcp_") as td:
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=td, env=env)
        except subprocess.TimeoutExpired:
            raise ProviderError(f"{name} timed out after {timeout} s")
    result, is_error, final, called = parse_stream(r.stdout.splitlines(), name)
    if not called:
        why = (r.stderr or "").strip()[:200]
        raise ProviderError(f"Claude Code couldn't use {name}. Add the connector with "
                            f"`claude mcp add --transport http {server} <url>` and log in via /mcp."
                            + (f" ({why})" if why else ""))
    if result is None:
        raise ProviderError(f"{name} returned nothing")
    if is_error:
        raise ProviderError(f"{tool}: {str(result)[:400]}")
    return decode(result)
