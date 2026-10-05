"""Private online mode (python -m studio online): one owner, created on the PC itself; the Cloudflare link."""
import io

import pytest

from studio import config, db, online

H = {"X-Studio": "1"}
LINK = "https://lucky-words-here.trycloudflare.com"
REMOTE = {"X-Studio": "1", "cf-connecting-ip": "203.0.113.9"}


@pytest.fixture
def private(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MODE", "hosted")
    monkeypatch.setenv("STUDIO_PRIVATE", "1")
    monkeypatch.setenv("STUDIO_ADMIN_EMAIL", "someone-else@example.com")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "studio.db"))   # a fresh, empty account list
    yield


def client(base_url="http://localhost"):
    from fastapi.testclient import TestClient
    from studio.server.app import app
    return TestClient(app, base_url=base_url)


def test_owner_account_only_on_this_pc(private):
    remote, local = client(LINK), client()
    cfg = remote.get("/api/config", headers=REMOTE).json()
    assert cfg["private"] and cfg["needs_owner"] and cfg["signup"] is False
    r = remote.post("/api/auth/signup", json=dict(email="me@example.com", password="correct horse"), headers=REMOTE)
    assert r.status_code == 403 and "computer" in r.json()["detail"]
    assert local.get("/api/config").json()["signup"] is True
    r = local.post("/api/auth/signup", json=dict(email="me@example.com", password="correct horse"), headers=H)
    assert r.status_code == 200 and r.json()["user"]["is_admin"]       # the first account is the owner
    # nobody else can sign up afterwards, not even on the PC
    assert client().post("/api/auth/signup", json=dict(email="x@example.com", password="correct horse"),
                         headers=H).status_code == 403
    # the owner logs in through the link; the cookie is Secure there
    r = remote.post("/api/auth/login", json=dict(email="me@example.com", password="correct horse"), headers=REMOTE)
    assert r.status_code == 200 and "secure" in r.headers["set-cookie"].lower()
    cfg = remote.get("/api/config", headers=REMOTE).json()
    assert cfg["user"]["usage"]["unlimited"]
    # anonymous visitors through the link see nothing
    assert client(LINK).get("/api/projects", headers=REMOTE).status_code == 401


def test_owner_uses_free_tools_with_no_limits(private):
    c = client()
    c.post("/api/auth/signup", json=dict(email="me@example.com", password="correct horse"), headers=H)
    slugs = []
    for i in range(4):                                  # more than any plan's free videos, no reservation
        r = c.post("/api/projects", json=dict(mode="topic", topic=f"Topic {i}", minutes=12, start=False,
                                              providers={"llm": "claude_cli"}), headers=H)
        assert r.status_code == 200, r.text
        slugs.append(r.json()["slug"])
    m = c.get(f"/api/projects/{slugs[0]}").json()["meta"]
    assert m["providers"]["llm"] == "claude_cli" and not m["options"].get("watermark") and "billing" not in m
    for s in slugs:
        c.delete(f"/api/projects/{s}", headers=H)


def test_tunnel_url_is_read_from_cloudflared_log():
    log = io.StringIO("2026-10-05T16:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...\n"
                      "2026-10-05T16:00:02Z INF |  https://lucky-words-here.trycloudflare.com  |\n"
                      "2026-10-05T16:00:03Z INF Registered tunnel connection\n")

    class P:
        stdout = log
    got = []
    online.watch_tunnel(P, got.append)
    assert got == ["https://lucky-words-here.trycloudflare.com"]


def test_online_explains_how_to_get_cloudflared(monkeypatch, capsys):
    monkeypatch.setattr(online, "find_cloudflared", lambda: None)
    assert online.main(port=8799, open_browser=False) == 1
    out = capsys.readouterr().out
    assert "winget install --id Cloudflare.cloudflared" in out and "cloudflared-linux-amd64.deb" in out


def test_site_link_tells_netlify_where_the_studio_is():
    import http.server
    import json
    import threading
    got = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            got.append((self.path, self.headers["Authorization"], body))
            self.send_response(200 if self.headers["Authorization"] == "Bearer right-secret-123456" else 401)
            self.end_headers()

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        site = online.SiteLink(f"http://127.0.0.1:{srv.server_port}/", "right-secret-123456")
        site.start("https://lucky-words-here.trycloudflare.com")
        site.offline()
        assert got[0] == ("/api/studio-link", "Bearer right-secret-123456", {"url": "https://lucky-words-here.trycloudflare.com"})
        assert got[-1][2] == {"offline": True}
        wrong = online.SiteLink(f"http://127.0.0.1:{srv.server_port}", "wrong")
        assert wrong.post({"url": "x"}) is False and wrong.warned
        assert not online.SiteLink("", "x").on                # no site set: nothing is sent
    finally:
        srv.shutdown()
