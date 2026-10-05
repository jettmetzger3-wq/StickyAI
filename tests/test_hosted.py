"""Hosted mode: accounts, isolation, plan allowances, Stripe webhooks (signed locally, no network)."""
import json
import time
import uuid

import pytest

from studio import config
from studio.hosted import accounts, plans, billing

H = {"X-Studio": "1"}


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setattr(config, "MODE", "hosted")
    monkeypatch.setenv("STUDIO_ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("STUDIO_SIGNUPS_PER_IP", "1000")
    # the plan's writer must be usable in tests: point both plans at the no-AI writer
    s = config.load_settings()["hosted"]
    for p in s["plans"].values():
        p["providers"]["llm"] = "offline"
    config.save_settings({"hosted": s})
    yield
    config.save_settings({"hosted": config.DEFAULT_SETTINGS["hosted"]})


def client():
    from fastapi.testclient import TestClient
    from studio.server.app import app
    return TestClient(app, base_url="http://localhost")


def email(tag):
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


def signup(c, tag="u"):
    e = email(tag)
    r = c.post("/api/auth/signup", json=dict(email=e, password="correct horse"), headers=H)
    assert r.status_code == 200, r.text
    return e, r.json()["user"]


def test_csrf_header_required_local():
    c = client()
    assert c.put("/api/settings", json={}).status_code == 403
    assert c.put("/api/settings", json={}, headers=H).status_code == 200


def test_local_mode_only_answers_localhost():
    c = client()
    assert c.get("/api/health", headers={"host": "evil.example.com"}).status_code == 403
    assert c.get("/api/health", headers={"host": "localhost:8765"}).status_code == 200


def test_signup_login_and_isolation(hosted):
    a, b, anon = client(), client(), client()
    assert anon.get("/api/projects").status_code == 401
    assert anon.get("/api/config").json()["user"] is None
    ea, ua = signup(a, "alice")
    signup(b, "bob")
    assert not ua["is_admin"]
    r = a.post("/api/projects", json=dict(mode="topic", topic="Rome", minutes=2, start=False, tier="free"), headers=H)
    assert r.status_code == 200, r.text
    slug = r.json()["slug"]
    assert a.get(f"/api/projects/{slug}").status_code == 200
    assert b.get(f"/api/projects/{slug}").status_code == 404
    assert b.get(f"/api/projects/{slug}/file/script.json").status_code == 404
    assert slug not in [p["slug"] for p in b.get("/api/projects").json()["projects"]]
    # normal users can't touch settings, keys or admin pages
    assert a.put("/api/settings", json={}, headers=H).status_code == 403
    assert a.put("/api/secrets", json=dict(name="ANTHROPIC_API_KEY", value="x"), headers=H).status_code == 403
    assert a.get("/api/admin/users").status_code == 403
    assert "secrets" not in a.get("/api/settings").json() or not a.get("/api/settings").json()["secrets"]
    # logout ends the session
    a.post("/api/auth/logout", headers=H)
    assert a.get("/api/projects").status_code == 401
    assert a.post("/api/auth/login", json=dict(email=ea, password="wrong pass"), headers=H).status_code == 401
    assert a.post("/api/auth/login", json=dict(email=ea, password="correct horse"), headers=H).status_code == 200


def test_admin_from_env_and_plan_tools(hosted):
    boss = client()
    r = boss.post("/api/auth/signup", json=dict(email="boss@example.com", password="correct horse"), headers=H)
    if r.status_code == 400:  # already made by another test run in this session
        r = boss.post("/api/auth/login", json=dict(email="boss@example.com", password="correct horse"), headers=H)
    assert r.json()["user"]["is_admin"]
    assert boss.get("/api/admin/users").status_code == 200
    u = client()
    signup(u, "carol")
    r = u.post("/api/projects", json=dict(mode="topic", topic="Rome", minutes=2, start=False, tier="free",
                                          providers={"voice": "elevenlabs"}), headers=H)
    m = u.get(f"/api/projects/{r.json()['slug']}").json()["meta"]
    assert m["providers"]["voice"] == "kokoro"          # the plan decides, not the request
    assert m["options"]["watermark"]                    # free plan videos carry the mark
    assert m["billing"]["tier"] == "free" and "auto_approve" not in m
    # plan users can't change tools or the reserved length afterwards
    r2 = u.put(f"/api/projects/{m['slug']}/options", json=dict(providers={"voice": "elevenlabs"}, options=dict(minutes=30)),
               headers=H)
    assert r2.json()["meta"]["providers"]["voice"] == "kokoro"
    assert r2.json()["meta"]["options"]["minutes"] == 2


def test_free_allowance_and_refund(hosted):
    c = client()
    _, u = signup(c, "dave")
    slugs = []
    for i in range(2):
        r = c.post("/api/projects", json=dict(mode="topic", topic=f"T{i}", minutes=2, start=False, tier="free"), headers=H)
        assert r.status_code == 200
        slugs.append(r.json()["slug"])
    r = c.post("/api/projects", json=dict(mode="topic", topic="T3", minutes=2, start=False, tier="free"), headers=H)
    assert r.status_code == 402
    assert c.post("/api/projects", json=dict(mode="topic", topic="P", minutes=2, start=False, tier="pro"),
                  headers=H).status_code == 402
    assert c.post("/api/projects", json=dict(mode="topic", topic="Long", minutes=9, start=False, tier="free"),
                  headers=H).status_code in (402,)
    # deleting an unfinished video gives the free video back
    assert c.delete(f"/api/projects/{slugs[0]}", headers=H).status_code == 200
    assert c.get("/api/config").json()["user"]["usage"]["free_videos_used"] == 1


def test_pro_minutes_reserve_settle_and_packs():
    u = accounts.create_user(email("erin"), "correct horse")
    accounts.update_user(u["id"], plan="pro")
    u = accounts.get_user(u["id"])
    rec = plans.reserve(u, "pro", 12, "p1")
    assert rec["monthly"] == 12 and plans.usage(u)["pro_minutes_left"] == 18
    with pytest.raises(plans.LimitError):
        plans.reserve(u, "pro", 20, "p2")            # only 18 left
    plans.add_minutes(u["id"], 10)                    # a pack
    u = accounts.get_user(u["id"])
    rec2 = plans.reserve(u, "pro", 15, "p2")          # 18 monthly + 10 extra available
    assert rec2["monthly"] == 15 and rec2["extra"] == 0
    rec3 = plans.reserve(accounts.get_user(u["id"]), "pro", 8, "p3")
    assert rec3["monthly"] == 3 and rec3["extra"] == 5
    # the video came out 6.2 minutes: 1.8 go back, extra minutes first
    plans.settle(rec3, 6.2, "p3")
    u = accounts.get_user(u["id"])
    assert abs(u["extra_minutes"] - 6.8) < 1e-6
    assert rec3["settled"] and abs(rec3["refunded"] - 1.8) < 1e-6
    # a full refund returns both kinds
    plans.refund_all(rec, "p1")
    assert plans.usage(accounts.get_user(u["id"]))["pro_minutes_used"] == 18.0


def test_settle_after_month_rollover_returns_extra(monkeypatch):
    u = accounts.create_user(email("finn"), "correct horse")
    accounts.update_user(u["id"], plan="pro")
    rec = plans.reserve(accounts.get_user(u["id"]), "pro", 10, "x")
    monkeypatch.setattr(plans, "month", lambda: "2099-01")
    plans.settle(rec, 4, "x")
    assert abs(accounts.get_user(u["id"])["extra_minutes"] - 6) < 1e-6


def _signed(payload, secret):
    import stripe
    body = json.dumps(payload)
    return body, stripe.WebhookSignature.generate_signature_header(body, secret)


def test_stripe_webhook_signed(hosted, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_123")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    u = accounts.create_user(email("gina"), "correct horse")
    c = client()
    ev = {"id": "evt_" + uuid.uuid4().hex, "object": "event", "type": "checkout.session.completed",
          "data": {"object": {"object": "checkout.session", "mode": "subscription", "customer": "cus_1" + uuid.uuid4().hex[:6],
                              "subscription": "sub_" + uuid.uuid4().hex[:8], "client_reference_id": str(u["id"]),
                              "metadata": {"user_id": str(u["id"]), "kind": "pro"}, "payment_status": "paid"}}}
    body, sig = _signed(ev, "whsec_test_123")
    # no X-Studio header needed (Stripe calls it), but a bad signature is refused
    assert c.post("/api/billing/webhook", content=body, headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
    r = c.post("/api/billing/webhook", content=body, headers={"stripe-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200 and r.json()["result"] == "pro activated"
    assert accounts.get_user(u["id"])["plan"] == "pro"
    # the same event twice is ignored
    r = c.post("/api/billing/webhook", content=body, headers={"stripe-signature": sig})
    assert r.json()["result"] == "duplicate"
    # cancelling the subscription drops back to free
    sub = ev["data"]["object"]["subscription"]
    ev2 = {"id": "evt_" + uuid.uuid4().hex, "object": "event", "type": "customer.subscription.deleted",
           "data": {"object": {"object": "subscription", "id": sub, "customer": ev["data"]["object"]["customer"],
                               "status": "canceled", "metadata": {}}}}
    body2, sig2 = _signed(ev2, "whsec_test_123")
    assert c.post("/api/billing/webhook", content=body2, headers={"stripe-signature": sig2}).json()["result"].endswith("free")
    assert accounts.get_user(u["id"])["plan"] == "free"


def test_pack_purchase_adds_minutes():
    u = accounts.create_user(email("hank"), "correct horse")
    ev = {"id": "evt_" + uuid.uuid4().hex, "type": "checkout.session.completed",
          "data": {"object": {"mode": "payment", "payment_status": "paid", "client_reference_id": str(u["id"]),
                              "metadata": {"user_id": str(u["id"]), "kind": "pack"}}}}
    assert billing.handle_event(ev) == "pack added"
    assert accounts.get_user(u["id"])["extra_minutes"] == plans.cfg()["pack"]["minutes"]
    # unpaid (e.g. delayed payment method) doesn't add anything
    ev["id"] = "evt_" + uuid.uuid4().hex
    ev["data"]["object"]["payment_status"] = "unpaid"
    assert billing.handle_event(ev) == "ignored checkout"


def test_passwords_hashed_and_sessions_expire():
    e = email("ivy")
    u = accounts.create_user(e, "correct horse")
    con = accounts.conn()
    row = con.execute("SELECT pw_hash, salt FROM users WHERE id=?", (u["id"],)).fetchone()
    con.close()
    assert "correct horse" not in row["pw_hash"] and len(row["salt"]) == 32
    tok = accounts.new_session(u["id"])
    assert accounts.user_for_token(tok)["id"] == u["id"]
    con = accounts.conn()
    con.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
    con.commit()
    con.close()
    assert accounts.user_for_token(tok) is None
    with pytest.raises(accounts.AuthError):
        accounts.create_user(e, "correct horse")      # duplicate
    with pytest.raises(accounts.AuthError):
        accounts.create_user(email("jo"), "short")    # too short


def test_login_rate_limit():
    e = email("kim")
    accounts.create_user(e, "correct horse")
    for _ in range(10):
        with pytest.raises(accounts.AuthError):
            accounts.login(e, "nope", ip="9.9.9.9")
    with pytest.raises(accounts.AuthError, match="too many"):
        accounts.login(e, "correct horse", ip="9.9.9.9")
    assert accounts.login(e, "correct horse", ip="8.8.8.8")["email"] == e


def test_site_starts_free_only(hosted, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_dummy")
    c = client()
    signup(c, "lou")
    cfg = c.get("/api/config").json()
    assert cfg["pricing"]["paid_plans"] is False and cfg["billing"]["enabled"] is False
    r = c.post("/api/billing/checkout", json=dict(kind="pro"), headers=H)
    assert r.status_code == 400 and "free" in r.json()["detail"]


def test_monthly_budget_stops_new_videos(hosted, monkeypatch):
    c = client()
    _, u = signup(c, "max")
    r = c.post("/api/projects", json=dict(mode="topic", topic="Spendy", minutes=2, start=False, tier="free"), headers=H)
    slug = r.json()["slug"]
    from studio.pipeline import Project, costs as pcosts
    pcosts.record(Project(slug), "storyboard", "anthropic", usd=19.8, note="test")
    assert plans.budget_left() <= 0.5
    r = c.post("/api/projects", json=dict(mode="topic", topic="Next", minutes=2, start=False, tier="free"), headers=H)
    assert r.status_code == 503 and "1st" in r.json()["detail"]
    # the owner's own videos don't count against it, and the owner is never stopped by it
    s = config.load_settings()["hosted"]
    s["monthly_budget_usd"] = 0
    config.save_settings({"hosted": s})
    assert plans.budget_left() is None
    c.delete(f"/api/projects/{slug}", headers=H)
