"""Stripe billing for hosted mode (official `stripe` Python SDK).

You create two Prices in your Stripe dashboard: a monthly subscription for Pro and a one-time "+10 Pro
minutes" pack, and put their IDs in STRIPE_PRICE_PRO / STRIPE_PRICE_PACK. Payments go through Stripe Checkout
(Stripe hosts the card form, we never see card numbers); customers manage or cancel in the Stripe Billing Portal.
Our webhook endpoint listens for the results and updates the user's plan.
"""
from ..config import secret, PUBLIC_URL
from . import accounts, plans

PRO_STATUSES = ("active", "trialing", "past_due")   # past_due keeps Pro while Stripe retries the card


class BillingError(Exception):
    pass


def enabled():
    return bool(plans.paid_on() and secret("STRIPE_SECRET_KEY") and secret("STRIPE_PRICE_PRO"))


def status():
    return dict(enabled=enabled(), packs=bool(enabled() and secret("STRIPE_PRICE_PACK")),
                webhook=bool(secret("STRIPE_WEBHOOK_SECRET")))


def client():
    import stripe
    key = secret("STRIPE_SECRET_KEY")
    if not key:
        raise BillingError("payments aren't set up on this server yet")
    return stripe.StripeClient(key)


def _customer(c, user):
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]
    cust = c.v1.customers.create(params={"email": user["email"], "metadata": {"user_id": str(user["id"])}})
    accounts.update_user(user["id"], stripe_customer_id=cust.id)
    return cust.id


def checkout(user, kind):
    """Return the URL of a Stripe Checkout page for 'pro' (subscription) or 'pack' (one-time minutes)."""
    if not plans.paid_on():
        raise BillingError("paid plans aren't open yet; everything on this site is free for now")
    c = client()
    if kind == "pro":
        price = secret("STRIPE_PRICE_PRO")
        mode = "subscription"
        if plans.effective_plan(user) == "pro" and user.get("sub_status") in PRO_STATUSES:
            raise BillingError("you're already on Pro")
    elif kind == "pack":
        price = secret("STRIPE_PRICE_PACK")
        mode = "payment"
        if not price:
            raise BillingError("minute packs aren't set up on this server")
    else:
        raise BillingError("unknown purchase")
    params = {
        "mode": mode,
        "customer": _customer(c, user),
        "line_items": [{"price": price, "quantity": 1}],
        "client_reference_id": str(user["id"]),
        "metadata": {"user_id": str(user["id"]), "kind": kind},
        "success_url": f"{PUBLIC_URL}/#/account?paid={kind}",
        "cancel_url": f"{PUBLIC_URL}/#/pricing",
        "allow_promotion_codes": True,
    }
    if mode == "subscription":
        params["subscription_data"] = {"metadata": {"user_id": str(user["id"])}}
    s = c.v1.checkout.sessions.create(params=params)
    return s.url


def portal(user):
    c = client()
    if not user.get("stripe_customer_id"):
        raise BillingError("no billing account yet")
    s = c.v1.billing_portal.sessions.create(params={"customer": user["stripe_customer_id"],
                                                    "return_url": f"{PUBLIC_URL}/#/account"})
    return s.url


def _get(o, k, default=None):
    try:
        v = o[k]
    except (KeyError, TypeError, IndexError):
        v = getattr(o, k, default)
    return default if v is None else v


def handle_event(event):
    """Apply one verified Stripe event. Returns a short description (for logs/tests)."""
    etype = _get(event, "type")
    eid = _get(event, "id")
    if eid and accounts.event_seen(eid, etype):
        return "duplicate"
    obj = _get(_get(event, "data", {}), "object", {})
    if etype == "checkout.session.completed":
        meta = _get(obj, "metadata", {}) or {}
        uid = _get(meta, "user_id") or _get(obj, "client_reference_id")
        user = accounts.get_user(int(uid)) if uid else accounts.user_by_stripe(customer_id=_get(obj, "customer"))
        if not user:
            return "unknown user"
        if _get(obj, "customer") and not user.get("stripe_customer_id"):
            accounts.update_user(user["id"], stripe_customer_id=_get(obj, "customer"))
        if _get(obj, "mode") == "subscription":
            accounts.update_user(user["id"], plan="pro", stripe_subscription_id=_get(obj, "subscription"),
                                 sub_status="active")
            return "pro activated"
        if _get(obj, "mode") == "payment" and _get(meta, "kind") == "pack" and _get(obj, "payment_status") == "paid":
            plans.add_minutes(user["id"], plans.cfg()["pack"]["minutes"], note="pack purchase")
            return "pack added"
        return "ignored checkout"
    if etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        sub_id, cust = _get(obj, "id"), _get(obj, "customer")
        st = "canceled" if etype.endswith("deleted") else _get(obj, "status")
        meta = _get(obj, "metadata", {}) or {}
        user = accounts.user_by_stripe(customer_id=cust, subscription_id=sub_id)
        if not user and _get(meta, "user_id"):
            user = accounts.get_user(int(_get(meta, "user_id")))
        if not user:
            return "unknown user"
        plan = "pro" if st in PRO_STATUSES else "free"
        accounts.update_user(user["id"], plan=plan, sub_status=st, stripe_subscription_id=sub_id,
                             stripe_customer_id=cust or user.get("stripe_customer_id"))
        return f"subscription {st} -> {plan}"
    return "ignored"


def webhook(payload, sig_header):
    import stripe
    whsec = secret("STRIPE_WEBHOOK_SECRET")
    if not whsec:
        raise BillingError("STRIPE_WEBHOOK_SECRET isn't set")
    try:
        event = stripe.StripeClient(secret("STRIPE_SECRET_KEY") or "sk_unset").construct_event(payload, sig_header, whsec)
    except Exception as e:
        raise BillingError(f"bad signature: {e}")
    return handle_event(event)
