"""Request guard (pure ASGI middleware, so it also covers the live-progress stream).

Both modes:
  - every POST/PUT/DELETE to /api needs the header `X-Studio: 1`. Browsers can't add custom headers to a
    cross-site form or a "simple" request, so other websites can't make your dashboard do things.
Local mode:
  - only answers to localhost (blocks DNS-rebinding tricks), unless you started it with --host 0.0.0.0.
Hosted mode:
  - reads the login cookie and puts the user in `studio.hosted.current_user` for the endpoints,
  - everything under /api needs a login except a few public paths; admin paths need an admin.
"""
import json
import os
from http.cookies import SimpleCookie

from starlette.concurrency import run_in_threadpool

from ..config import hosted
from ..hosted import accounts, current_user

COOKIE = "studio_session"
PUBLIC = ("/api/config", "/api/auth/login", "/api/auth/signup", "/api/auth/logout", "/api/billing/webhook",
          "/api/health", "/api/plans")
CSRF_EXEMPT = ("/api/billing/webhook",)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def admin_only(path, method):
    if path.startswith("/api/admin"):
        return True
    if path in ("/api/settings", "/api/secrets") and method != "GET":
        return True
    if path in ("/api/balances", "/api/llm/models"):
        return True
    return False


def cookie_value(header, name):
    if not header:
        return ""
    c = SimpleCookie()
    try:
        c.load(header)
    except Exception:
        return ""
    return c[name].value if name in c else ""


def client_ip(scope, headers):
    if os.environ.get("STUDIO_PRIVATE") == "1" and headers.get("cf-connecting-ip"):
        return headers["cf-connecting-ip"]          # the visitor's address, passed on by the Cloudflare link
    if os.environ.get("STUDIO_TRUST_PROXY") == "1" and headers.get("x-forwarded-for"):
        return headers["x-forwarded-for"].split(",")[0].strip()
    return (scope.get("client") or ("", 0))[0]


async def _reply(send, status, detail):
    body = json.dumps({"detail": detail}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class Guard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}
        scope.setdefault("state", {})["ip"] = client_ip(scope, headers)
        if not hosted() and os.environ.get("STUDIO_BIND_HOST", "127.0.0.1") in ("127.0.0.1", "localhost", "::1"):
            host = headers.get("host", "").rsplit(":", 1)[0] if not headers.get("host", "").startswith("[") \
                else headers.get("host", "").split("]")[0] + "]"
            extra = {h.strip() for h in os.environ.get("STUDIO_ALLOWED_HOSTS", "").split(",") if h.strip()}
            if host and host not in LOCAL_HOSTS | extra:
                return await _reply(send, 403, "this dashboard only answers on localhost")
        if not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        if method in ("POST", "PUT", "DELETE", "PATCH") and path not in CSRF_EXEMPT and headers.get("x-studio") != "1":
            return await _reply(send, 403, "missing X-Studio header")
        if not hosted():
            return await self.app(scope, receive, send)
        token = cookie_value(headers.get("cookie"), COOKIE)
        user = await run_in_threadpool(accounts.user_for_token, token) if token else None
        tok = current_user.set(user)
        try:
            if not user and path not in PUBLIC:
                return await _reply(send, 401, "please log in")
            if admin_only(path, method) and not (user and user.get("is_admin")):
                return await _reply(send, 403, "admins only")
            await self.app(scope, receive, send)
        finally:
            current_user.reset(tok)
