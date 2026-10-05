"""Endpoints for hosted mode: config, sign up / log in, billing (Stripe) and admin."""
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .. import config, db
from ..hosted import accounts, plans, billing, user as current
from ..pipeline import list_projects
from .auth import COOKIE

router = APIRouter()
_signups = {}   # ip -> [timestamps]


LOOPBACK = ("localhost", "127.0.0.1", "::1", "[::1]")


def is_local(request):
    """Opened on this computer itself (not through the Cloudflare link or a proxy)."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    client = (request.client.host if request.client else "") or ""
    return host in LOOPBACK and client in ("127.0.0.1", "::1", "localhost", "testclient") \
        and not request.headers.get("cf-connecting-ip") and not request.headers.get("x-forwarded-for")


def _cookie(resp, token, max_age, request=None):
    secure = config.PUBLIC_URL.startswith("https://") or bool(request and not is_local(request))
    resp.set_cookie(COOKIE, token, max_age=max_age, httponly=True, samesite="lax", path="/", secure=secure)


def online_url():
    try:
        with open(os.path.join(config.DATA_DIR, "online_url.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def signup_open(request):
    if config.private():
        # one owner, created on the PC itself; nobody can sign up through the online link
        return accounts.count_users() == 0 and is_local(request)
    return bool(config.load_settings()["hosted"].get("allow_signup", True))


def me_payload(u):
    if not u:
        return None
    out = dict(id=u["id"], email=u["email"], is_admin=u["is_admin"], plan=plans.effective_plan(u),
               sub_status=u.get("sub_status"), has_billing=bool(u.get("stripe_customer_id")))
    if config.hosted():
        out["usage"] = plans.usage(u)
    return out


@router.get("/api/config")
def get_config(request: Request):
    u = current()
    out = dict(mode=config.MODE, user=me_payload(u), private=config.private())
    if config.hosted():
        h = config.load_settings()["hosted"]
        out.update(signup=signup_open(request), billing=billing.status(), pricing=plans.public_plans(),
                   ai_edits_per_video=h.get("ai_edits_per_video"))
        if config.private():
            out["needs_owner"] = accounts.count_users() == 0
            if u and u.get("is_admin"):
                out["online_url"] = online_url()
    return out


@router.get("/api/plans")
def get_plans():
    return dict(pricing=plans.public_plans(), billing=billing.status())


class Creds(BaseModel):
    email: str
    password: str


@router.post("/api/auth/signup")
def signup(b: Creds, request: Request, response: Response):
    if not config.hosted():
        raise HTTPException(400, "accounts are only used on the hosted website")
    if config.private() and not signup_open(request):
        raise HTTPException(403, "this is a private studio. The owner account can only be created on the computer "
                                 "it runs on (http://localhost)." if accounts.count_users() == 0 else
                                 "this is a private studio; sign-ups are off")
    if not signup_open(request):
        raise HTTPException(403, "sign-ups are closed right now")
    ip = request.scope.get("state", {}).get("ip", "")
    now = time.time()
    hits = [t for t in _signups.get(ip, []) if now - t < 86400]
    if not config.private() and len(hits) >= int(os.environ.get("STUDIO_SIGNUPS_PER_IP", "3")):
        raise HTTPException(429, "too many new accounts from this network today")
    try:
        u = accounts.create_user(b.email, b.password,
                                 admin_email="" if config.private() else os.environ.get("STUDIO_ADMIN_EMAIL", ""))
    except accounts.AuthError as e:
        raise HTTPException(400, str(e))
    _signups[ip] = hits + [now]
    _cookie(response, accounts.new_session(u["id"]), accounts.SESSION_DAYS * 86400, request)
    return dict(user=me_payload(u))


@router.post("/api/auth/login")
def login(b: Creds, request: Request, response: Response):
    if not config.hosted():
        raise HTTPException(400, "accounts are only used on the hosted website")
    try:
        u = accounts.login(b.email, b.password, request.scope.get("state", {}).get("ip", ""))
    except accounts.AuthError as e:
        raise HTTPException(401, str(e))
    _cookie(response, accounts.new_session(u["id"]), accounts.SESSION_DAYS * 86400, request)
    return dict(user=me_payload(u))


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    accounts.end_session(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return dict(ok=True)


class PasswordBody(BaseModel):
    old: str
    new: str


@router.post("/api/auth/password")
def change_password(b: PasswordBody, request: Request, response: Response):
    u = current()
    if not config.hosted() or not u:
        raise HTTPException(400, "not available")
    try:
        accounts.login(u["email"], b.old, request.scope.get("state", {}).get("ip", ""))
        accounts.set_password(u["id"], b.new)
    except accounts.AuthError as e:
        raise HTTPException(400, str(e))
    _cookie(response, accounts.new_session(u["id"]), accounts.SESSION_DAYS * 86400, request)
    return dict(ok=True)


# ------------------------------------------------------------------ billing
class CheckoutBody(BaseModel):
    kind: str = "pro"      # pro | pack


@router.post("/api/billing/checkout")
def checkout(b: CheckoutBody):
    u = current()
    if not config.hosted() or not u:
        raise HTTPException(400, "not available")
    try:
        return dict(url=billing.checkout(accounts.get_user(u["id"]), b.kind))
    except billing.BillingError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Stripe error: {str(e)[:200]}")


@router.post("/api/billing/portal")
def portal():
    u = current()
    if not config.hosted() or not u:
        raise HTTPException(400, "not available")
    try:
        return dict(url=billing.portal(accounts.get_user(u["id"])))
    except billing.BillingError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Stripe error: {str(e)[:200]}")


@router.post("/api/billing/webhook")
async def webhook(request: Request):
    payload = await request.body()
    try:
        result = billing.webhook(payload, request.headers.get("stripe-signature", ""))
    except billing.BillingError as e:
        raise HTTPException(400, str(e))
    return dict(received=True, result=result)


# ------------------------------------------------------------------ admin
@router.get("/api/admin/users")
def admin_users():
    users = accounts.list_users()
    counts = {}
    for m in list_projects():
        o = m.get("owner")
        if o is not None:
            counts[o] = counts.get(o, 0) + 1
    out = []
    for u in users:
        out.append(dict(u, usage=plans.usage(u), projects=counts.get(u["id"], 0)))
    return dict(users=out)


class AdminUserBody(BaseModel):
    plan: str | None = None
    add_minutes: float | None = None
    disabled: bool | None = None
    is_admin: bool | None = None
    password: str | None = None


@router.put("/api/admin/users/{uid}")
def admin_update_user(uid: int, b: AdminUserBody):
    u = accounts.get_user(uid)
    if not u:
        raise HTTPException(404, "no such user")
    me = current()
    fields = {}
    if b.plan is not None:
        if b.plan not in plans.plans():
            raise HTTPException(400, "unknown plan")
        fields["plan"] = b.plan
    if b.disabled is not None:
        if uid == me["id"]:
            raise HTTPException(400, "you can't disable yourself")
        fields["disabled"] = int(b.disabled)
    if b.is_admin is not None:
        if uid == me["id"] and not b.is_admin:
            raise HTTPException(400, "you can't remove your own admin rights")
        fields["is_admin"] = int(b.is_admin)
    if fields:
        accounts.update_user(uid, **fields)
    if b.add_minutes:
        plans.add_minutes(uid, b.add_minutes, note=f"granted by {me['email']}")
    if b.password:
        try:
            accounts.set_password(uid, b.password)
        except accounts.AuthError as e:
            raise HTTPException(400, str(e))
    u = accounts.get_user(uid)
    return dict(user=dict(u, usage=plans.usage(u)))


@router.get("/api/admin/stats")
def admin_stats():
    con = db.connect()
    try:
        month_start = time.mktime(time.strptime(plans.month() + "-01", "%Y-%m-%d"))
        row = con.execute("SELECT COALESCE(SUM(usd),0) AS usd, COUNT(DISTINCT slug) AS n FROM costs WHERE at >= ?",
                          (month_start,)).fetchone()
        per = [dict(r) for r in con.execute(
            "SELECT provider, COALESCE(SUM(usd),0) AS usd, COALESCE(SUM(credits),0) AS credits FROM costs "
            "WHERE at >= ? GROUP BY provider", (month_start,))]
    finally:
        con.close()
    users = accounts.list_users()
    pro = sum(1 for u in users if plans.effective_plan(u) == "pro" and not u["is_admin"])
    price = plans.plans()["pro"]["price_usd"]
    return dict(month=plans.month(), users=len(users), pro_users=pro, mrr_usd=round(pro * price, 2),
                tool_spend_usd=round(row["usd"], 2), videos_with_spend=row["n"], by_provider=per,
                billing=billing.status(), paid_plans=plans.paid_on(),
                monthly_budget_usd=float(plans.cfg().get("monthly_budget_usd") or 0), budget_left_usd=plans.budget_left())
