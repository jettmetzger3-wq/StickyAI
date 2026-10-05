"""Shorts teaser makers (a vertical Short cut from or made for the finished video).

- stickman: free. A 25-55 s run of your own scenes, re-framed to 1080x1920 with big captions (pipeline/shorts.py).
- calliope: paid (your Calliope credits). Calliope makes an AI Short from a 90-150 word script, through Claude
  Code and the Calliope MCP connector. The exact credit price comes from Calliope's own estimate tool and you
  approve that number first.
- none: no Short.
"""
import os
import time
import urllib.request

from ..config import hosted, private, load_settings, save_settings
from .base import Provider, Cost, FREE, ProviderError
from . import mcp_bridge


class StickmanShorts(Provider):
    id = "stickman"
    stage = "shorts"
    label = "Stickman Short (free)"
    description = "Cuts the best 25-55 seconds of your video into a vertical Short with big captions."
    paid = False

    def estimate(self, **kw):
        return FREE


class NoShorts(Provider):
    id = "none"
    stage = "shorts"
    label = "No Short"
    description = "Skip the Shorts teaser."
    paid = False

    def estimate(self, **kw):
        return FREE


def find(obj, keys, kind=None):
    """First value under any of `keys` anywhere in a nested dict/list (Calliope's replies are nested)."""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if v is not None and (kind is None or isinstance(v, kind)):
                return v
        for v in obj.values():
            r = find(v, keys, kind)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find(v, keys, kind)
            if r is not None:
                return r
    return None


CREDIT_KEYS = ("estimated_cost", "estimated_credits", "credit_cost", "total_credits", "credits", "cost")


class CalliopeShorts(Provider):
    id = "calliope"
    stage = "shorts"
    label = "Calliope AI Short (your Calliope credits)"
    description = "Calliope generates an AI-illustrated Short from a script. Uses Claude Code + the Calliope connector."
    paid = True
    quality = "best"

    def cfg(self):
        return load_settings().get("calliope") or {}

    @property
    def server(self):
        return self.cfg().get("server") or "calliope"

    def available(self):
        from .llm import ClaudeCLI
        if hosted() and not private() and not load_settings()["hosted"].get("ai_shorts"):
            return False, "AI Shorts are turned off on this website"
        if not ClaudeCLI().path():
            return False, "needs Claude Code (the `claude` command) with the Calliope connector"
        if not self.cfg().get("connected"):
            return False, "connect Calliope first: Settings > Calliope > Test connection"
        return True, ""

    def call(self, tool, args, timeout=300):
        return mcp_bridge.call_tool(self.server, tool, args, timeout=timeout)

    # ---------------- setup
    def test(self):
        """Free check: list the Short templates. Marks Calliope as connected when it works."""
        data = self.call("list_templates", {"content_type": "short"})
        items = find(data, ("templates", "items", "data"), list) or (data if isinstance(data, list) else [])
        temps = [dict(id=t.get("id") or t.get("template_id"), name=t.get("name"), visibility=t.get("visibility"))
                 for t in items if isinstance(t, dict) and (t.get("id") or t.get("template_id"))]
        save_settings({"calliope": {"connected": True, "templates": temps[:30], "tested_at": time.time()}})
        return temps

    def template_id(self):
        c = self.cfg()
        if c.get("template_id"):
            return c["template_id"]
        temps = c.get("templates") or self.test()
        if not temps:
            raise ProviderError("Calliope returned no Short templates for your account")
        return temps[0]["id"]

    def to_cost(self, raw, what):
        cr = find(raw, CREDIT_KEYS)
        try:
            cr = float(cr)
        except (TypeError, ValueError):
            return Cost(0.0, known=False, credit_unit="Calliope credits", note=f"{what}: Calliope didn't return a number")
        rate = float(self.cfg().get("usd_per_1k_credits") or 0)
        return Cost(round(cr / 1000 * rate, 2) if rate else 0.0, credits=cr, credit_unit="Calliope credits",
                    note=f"{what}: exact Calliope estimate" + ("" if rate else " (set your $ per 1,000 credits in Settings)"))

    # ---------------- Short
    def quote(self, seconds):
        args = {"content_type": "short", "target_duration_sec": int(seconds), "template_id": self.template_id()}
        if self.cfg().get("quality"):
            args["quality"] = self.cfg()["quality"]
        raw = self.call("estimate_generation_cost", args)
        return self.to_cost(raw, "AI Short"), raw

    def create(self, script):
        args = {"content_type": "short", "source": {"template_id": self.template_id()},
                "script_params": {"script": script}, "auto_accept": True, "auto_render": True, "captions": True}
        if self.cfg().get("quality"):
            args["quality"] = self.cfg()["quality"]
        raw = self.call("create_video", args, timeout=600)
        job = find(raw, ("job_id", "id"), str)
        if not job:
            raise ProviderError(f"Calliope didn't return a job id: {str(raw)[:300]}")
        return job, raw

    def job(self, job_id):
        return self.call("get_job", {"job_id": job_id})

    def wait(self, job_id, out_path, progress=None, check_cancel=None, max_minutes=40):
        t0 = time.time()
        while time.time() - t0 < max_minutes * 60:
            if check_cancel:
                check_cancel()
            raw = self.job(job_id)
            status = str(find(raw, ("status",), str) or "").lower()
            if status == "completed":
                url = find(raw, ("video_url",), str)
                if not url:
                    raise ProviderError("Calliope finished but gave no video link")
                download(url, out_path)
                return raw
            if status == "failed":
                raise ProviderError(f"Calliope job failed: {find(raw, ('error',), str) or 'no reason given'}")
            if progress:
                el = int(time.time() - t0)
                progress(min(0.95, 0.2 + el / (max_minutes * 60)),
                         f"Calliope is making the Short ({find(raw, ('phase',), str) or status or 'working'}, {el // 60} min)")
            wait = find(raw, ("estimated_time_remaining_sec",))
            try:
                wait = float(wait)
            except (TypeError, ValueError):
                wait = 45
            for _ in range(int(min(60, max(30, wait / 2)))):
                if check_cancel:
                    check_cancel()
                time.sleep(1)
        raise ProviderError(f"Calliope didn't finish within {max_minutes} minutes (job {job_id}); check it on calliopelabs.co")

    # ---------------- thumbnails (for a finished Calliope job)
    def quote_thumbnails(self, job_id, count):
        raw = self.call("create_thumbnails", {"job_id": job_id, "image_count": int(count), "estimate": True})
        return self.to_cost(raw, f"{count} Calliope thumbnails"), raw

    def make_thumbnails(self, job_id, count, prompt=""):
        args = {"job_id": job_id, "image_count": int(count)}
        if prompt:
            args["prompt"] = prompt
        return self.call("create_thumbnails", args, timeout=600)

    def thumbnails(self, job_id):
        raw = self.call("list_thumbnails", {"job_id": job_id})
        urls = []

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, str) and v.startswith("http") and ("url" in k.lower()):
                        urls.append(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(raw)
        return urls, raw


def download(url, out_path, timeout=300):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "StickmanStudio/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, out_path)
    return out_path
