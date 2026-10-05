"""Image providers (thumbnail backgrounds).

- local:      our own engine draws the thumbnail (free, always works).
- elevenlabs_image: ElevenLabs image generation through the official SDK (`client.flows.image`).
- higgsfield: Higgsfield's official Python client (`higgsfield-client`, model bytedance/seedream/v4/text-to-image).

OpenArt is not included: it has no public developer API (only an MCP connector inside the Claude app), so a
standalone website can't call it. Its free-tier images also carry a watermark.
"""
import os
import time
import urllib.request

from .base import ImageProvider, Cost, FREE, ProviderError
from . import elevenlabs_common as el
from ..config import secret

STYLE = ("simple flat 2D doodle cartoon, thick dark outlines, stick figure characters with round white heads, "
         "pastel colors, clean background, YouTube thumbnail composition, no text")


class LocalImage(ImageProvider):
    id = "local"
    label = "Built-in doodle thumbnail (free)"
    description = "Big two-line title, a small angry character vs a giant smug one, sunburst background."
    paid = False
    quality = "good"

    def generate(self, prompt, out_path, aspect="16:9"):
        return None  # the package stage draws it with the engine


def _download(url, path, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


class ElevenLabsImage(ImageProvider):
    id = "elevenlabs_image"
    label = "ElevenLabs image (paid)"
    description = "AI background art for the thumbnail (Seedream 5 Lite via ElevenLabs). Our title text and " \
                  "characters are drawn on top."
    paid = True
    quality = "best"
    needs_keys = ("ELEVENLABS_API_KEY",)
    needs_modules = ("elevenlabs",)

    def estimate(self, **job):
        return Cost(0.0, known=False, credit_unit="ElevenLabs credits",
                    note="1 image. Billed from your ElevenLabs credit balance; real usage is measured after.")

    def balance(self):
        return el.subscription()

    def generate(self, prompt, out_path, aspect="16:9"):
        from elevenlabs import ImageGenerationRequest_BytedanceSeedream5Lite
        c = el.client()
        try:
            job = c.flows.image.create(request=ImageGenerationRequest_BytedanceSeedream5Lite(
                prompt=f"{prompt}. {STYLE}", aspect_ratio=aspect))
            gid = job.id
            for _ in range(120):
                r = c.flows.image.get(gid)
                st = getattr(r, "status", "")
                if st == "completed":
                    return _download(r.content_url, out_path, {"xi-api-key": secret("ELEVENLABS_API_KEY")})
                if st == "failed":
                    raise ProviderError(f"image failed: {getattr(r, 'error_message', '')}")
                time.sleep(3)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"ElevenLabs image failed: {str(e)[:300]}")
        raise ProviderError("ElevenLabs image timed out")


class HiggsfieldImage(ImageProvider):
    id = "higgsfield"
    label = "Higgsfield image (paid)"
    description = "AI background art via Higgsfield's official API client (Seedream v4). Needs HF_API_KEY and " \
                  "HF_API_SECRET from cloud.higgsfield.ai."
    paid = True
    quality = "best"
    needs_keys = ("HF_API_KEY", "HF_API_SECRET")
    needs_modules = ("higgsfield_client",)
    APP = "bytedance/seedream/v4/text-to-image"

    def estimate(self, **job):
        return Cost(0.0, known=False, credit_unit="Higgsfield credits",
                    note="1 image. Billed from your Higgsfield credits; check the price on cloud.higgsfield.ai.")

    def generate(self, prompt, out_path, aspect="16:9"):
        os.environ["HF_API_KEY"] = secret("HF_API_KEY")
        os.environ["HF_API_SECRET"] = secret("HF_API_SECRET")
        try:
            import higgsfield_client
            result = higgsfield_client.subscribe(self.APP, arguments={
                "prompt": f"{prompt}. {STYLE}", "resolution": "2K", "aspect_ratio": aspect, "camera_fixed": False})
            url = result["images"][0]["url"]
        except Exception as e:
            raise ProviderError(f"Higgsfield failed: {str(e)[:300]}")
        return _download(url, out_path)
