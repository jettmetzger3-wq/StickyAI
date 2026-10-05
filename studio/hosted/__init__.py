"""Hosted mode: run Stickman Studio as a public website with accounts, plans and Stripe billing.

Turn it on with STUDIO_MODE=hosted (see DEPLOY.md). In the default local mode none of this is used.
"""
import contextvars

from ..config import hosted

LOCAL_USER = dict(id=0, email="local", is_admin=True, plan="pro", extra_minutes=0, disabled=False)
current_user = contextvars.ContextVar("studio_user", default=None)


def user():
    """The user making this request (local mode: the single local owner)."""
    if not hosted():
        return LOCAL_USER
    return current_user.get()


def is_admin():
    u = user()
    return bool(u and u.get("is_admin"))
