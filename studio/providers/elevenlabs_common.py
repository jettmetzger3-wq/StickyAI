"""Shared ElevenLabs helpers (official `elevenlabs` Python SDK, so no hand-written endpoints)."""
from ..config import secret, load_settings


def client():
    from elevenlabs import ElevenLabs
    return ElevenLabs(api_key=secret("ELEVENLABS_API_KEY"), timeout=600)


def usd_for_credits(credits):
    rate = float(load_settings().get("elevenlabs_usd_per_1k_credits") or 0.22)
    return round(credits / 1000.0 * rate, 3)


def subscription():
    """dict(used, limit, remaining, reset_unix, tier) or None."""
    try:
        s = client().user.subscription.get()
    except Exception:
        return None
    used, limit = int(s.character_count or 0), int(s.character_limit or 0)
    return dict(used=used, limit=limit, remaining=max(0, limit - used), reset_unix=s.next_character_count_reset_unix,
                tier=s.tier, unit="ElevenLabs credits")
