"""Gemini and Groq writers, with the network faked: JSON replies, waiting on per-minute limits, stopping on daily
limits, sending less when a request is too big, and the storyboard splitting its batches for small free limits."""
import json

import pytest

from studio.providers import free_llm as F


class Resp:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.text = json.dumps(body) if not isinstance(body, str) else body

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


def ok(text, tokens=100):
    return Resp(200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                      "usage": {"prompt_tokens": tokens - 20, "completion_tokens": 20, "total_tokens": tokens}})


@pytest.fixture
def writer(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(F, "secret", lambda k: "test-key")
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    w = F.Groq()
    w.min_gap = 0
    return w


def fake_post(monkeypatch, replies, seen):
    import httpx

    def post(url, json=None, headers=None, timeout=None):
        seen.append(dict(url=url, body=json, headers=headers))
        return replies.pop(0)
    monkeypatch.setattr(httpx, "post", post)


def test_reply_parsed_and_counted(writer, monkeypatch):
    seen = []
    fake_post(monkeypatch, [ok('{"a": 1}')], seen)
    text, usage = writer.complete("sys", "Write it.", schema={"type": "object"})
    assert json.loads(text) == {"a": 1} and usage["billed_usd"] == 0.0
    body = seen[0]["body"]
    assert seen[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen[0]["headers"]["Authorization"] == "Bearer test-key"
    assert body["response_format"] == {"type": "json_object"} and "JSON schema" in body["messages"][-1]["content"]
    assert body["reasoning_effort"] == "low"                 # gpt-oss thinks briefly to fit the free limits
    assert writer.used_today()["requests"] == 1


def test_waits_on_per_minute_limit_then_succeeds(writer, monkeypatch):
    seen, slept = [], []
    monkeypatch.setattr(F.time, "sleep", lambda s: slept.append(s))
    fake_post(monkeypatch, [Resp(429, {"error": {"message": "Rate limit reached on tokens per minute (TPM): "
                                                            "Limit 8000. Please try again in 7.5s."}}),
                            ok('{"x": 2}')], seen)
    text, _ = writer.complete("", "go json")
    assert json.loads(text) == {"x": 2} and any(abs(s - 8.0) < 0.01 for s in slept)


def test_daily_limit_stops_with_clear_message(writer, monkeypatch):
    fake_post(monkeypatch, [Resp(429, {"error": {"message": "Rate limit reached on requests per day (RPD): "
                                                            "Limit 1000, Used 1000"}})], [])
    with pytest.raises(F.DailyLimit) as e:
        writer.complete("", "go json")
    assert "Resume" in str(e.value)


def test_gemini_daily_quota_in_list_shaped_error(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(F, "secret", lambda k: "k")
    g = F.Gemini()
    g.min_gap = 0
    body = [{"error": {"code": 429, "message": "You exceeded your current quota.", "status": "RESOURCE_EXHAUSTED",
                       "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}]
    fake_post(monkeypatch, [Resp(429, body)], [])
    with pytest.raises(F.DailyLimit):
        g.complete("", "go json")


def test_too_large_and_json_mode_fallback(writer, monkeypatch):
    fake_post(monkeypatch, [Resp(413, {"error": {"message": "Request too large for model on tokens per minute"}})], [])
    with pytest.raises(F.TooLarge):
        writer.complete("", "go json")
    seen = []
    fake_post(monkeypatch, [Resp(400, {"error": {"message": "response_format json_object is not supported"}}),
                            ok("```json\n{\"y\": 3}\n```")], seen)
    text, _ = writer.complete("", "go json")
    assert "response_format" not in seen[1]["body"] and '"y": 3' in text


def test_groq_learns_its_limits_from_headers(writer, monkeypatch):
    fake_post(monkeypatch, [Resp(200, ok("{}").json(), {"x-ratelimit-limit-requests": "1000",
                                                          "x-ratelimit-remaining-requests": "987",
                                                          "x-ratelimit-limit-tokens": "8000"})], [])
    writer.complete("", "json")
    b = writer.balance()
    assert b["remaining"] == 987 and b["limit"] == 1000 and "987" in b["text"]
    assert writer.batch_beats == 2


def test_gemini_sends_images_as_data_urls(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(F, "secret", lambda k: "k")
    img = tmp_path / "sheet.jpg"
    img.write_bytes(b"\xff\xd8\xff fake")
    g = F.Gemini()
    g.min_gap = 0
    seen = []
    fake_post(monkeypatch, [ok("{}")], seen)
    g.complete("look", "json please", images=[str(img)])
    content = seen[0]["body"]["messages"][-1]["content"]
    assert seen[0]["url"].startswith("https://generativelanguage.googleapis.com/v1beta/openai/")
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_storyboard_splits_batches_for_small_free_limits(monkeypatch):
    """A writer whose free limit only fits one scene per request still gets every scene drawn."""
    from studio.pipeline import new_project, stages
    from studio.pipeline.runner import Ctx
    from studio.providers import TooLarge

    sizes = []

    class SmallWriter:
        id, label, short, paid, supports_images = "groq", "Small", "Groq", False, False
        batch_beats, parallel, examples, compact = 4, 1, 3, True

        def available(self):
            return True, ""

        def complete(self, system, prompt, schema=None, images=(), label="", **kw):
            if label == "props":
                return '{"props": []}', {}
            idx = [int(x) for x in label.split()[1].split("-")]
            n = idx[1] - idx[0] + 1
            sizes.append((n, "EXAMPLES" in prompt))
            if n > 1:
                raise TooLarge("too big")
            return json.dumps({"scenes": [{"beat": idx[0], "scene": {"bg": {"type": "field"}, "elements": [
                {"type": "char", "kind": "bicorne", "x": 600, "y": 900}]}}]}), {}

    monkeypatch.setattr(stages, "provider", lambda meta, stage: SmallWriter())
    monkeypatch.setattr(stages, "render_previews", lambda *a, **k: None)
    pr = new_project("Small limits", "topic", topic="Napoleon", options={"minutes": 1})
    pr.save_script({"title": "Small limits", "topic": "Napoleon", "cast": [{"name": "Napoleon", "kind": "bicorne"}],
                    "beats": [{"mood": "fun", "text": f"Beat number {i} about Napoleon."} for i in range(4)]})
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    sb = json.load(open(pr.p("storyboard.json")))
    assert all(sb["scenes"][str(i)]["source"] == "groq" for i in range(4))
    assert sizes[0] == (4, True) and (1, True) in sizes
