"""Plans, monthly allowances and Pro-minute accounting for hosted mode.

Free: a few short videos a month with the free tools and a small watermark.
Pro:  a monthly allowance of "Pro minutes" (finished video minutes made with the paid tools) that resets on
      the 1st of each month (UTC), plus extra minutes from one-time packs that never expire.
A Pro video reserves its target length when it starts; when it's finished the unused part goes back.
"""
import math
import threading
import time

from ..config import load_settings
from .. import providers as P
from . import accounts

_lock = threading.Lock()


class LimitError(Exception):
    pass


def month():
    return time.strftime("%Y-%m", time.gmtime())


def cfg():
    return load_settings()["hosted"]


def plans():
    return cfg()["plans"]


def public_plans():
    c = cfg()
    out = {}
    for pid, p in c["plans"].items():
        out[pid] = dict(id=pid, name=p["name"], price_usd=p["price_usd"], videos_per_month=p["videos_per_month"],
                        max_minutes=p["max_minutes"], pro_minutes=p["pro_minutes"], watermark=p["watermark"],
                        shorts=p.get("shorts", []))
    return dict(plans=out, pack=c["pack"], ai_short_minutes=load_settings()["calliope"].get("ai_short_minutes", 5))


def effective_plan(user):
    if not user:
        return "free"
    if user.get("is_admin"):
        return "pro"
    return user.get("plan") if user.get("plan") in plans() else "free"


def usage(user):
    c = accounts.conn()
    try:
        r = c.execute("SELECT * FROM usage WHERE user_id=? AND month=?", (user["id"], month())).fetchone()
    finally:
        c.close()
    used = dict(free_videos=r["free_videos"], pro_minutes=r["pro_minutes"]) if r else dict(free_videos=0, pro_minutes=0.0)
    plan = plans()[effective_plan(user)]
    monthly_left = max(0.0, plan["pro_minutes"] - used["pro_minutes"])
    extra = float(user.get("extra_minutes") or 0)
    return dict(month=month(), plan=effective_plan(user), free_videos_used=used["free_videos"],
                free_videos_limit=plans()["free"]["videos_per_month"], pro_minutes_used=round(used["pro_minutes"], 1),
                pro_minutes_monthly=plan["pro_minutes"], pro_minutes_left=round(monthly_left + extra, 1),
                extra_minutes=round(extra, 1), unlimited=bool(user.get("is_admin")))


def _bump(c, user_id, free_videos=0, pro_minutes=0.0):
    c.execute("INSERT OR IGNORE INTO usage (user_id, month) VALUES (?,?)", (user_id, month()))
    c.execute("UPDATE usage SET free_videos = free_videos + ?, pro_minutes = pro_minutes + ? WHERE user_id=? AND month=?",
              (free_videos, pro_minutes, user_id, month()))


def ledger(c, user_id, project, kind, monthly, extra, note=""):
    c.execute("INSERT INTO ledger (user_id, project, kind, monthly, extra, note, at) VALUES (?,?,?,?,?,?,?)",
              (user_id, project, kind, monthly, extra, note, time.time()))


def reserve(user, tier, minutes, project):
    """Check the plan and take the allowance for a new video. Returns the billing record to store on the project."""
    plan_id = effective_plan(user)
    if tier == "pro" and plan_id != "pro" and float(user.get("extra_minutes") or 0) <= 0:
        raise LimitError("Pro quality needs the Pro plan or a minutes pack")
    plan = plans()["pro" if tier == "pro" else "free"]
    if minutes > plan["max_minutes"] and not user.get("is_admin"):
        raise LimitError(f"{plan['name']} videos can be up to {plan['max_minutes']} minutes")
    rec = dict(user_id=user["id"], tier=tier, minutes=float(minutes), monthly=0.0, extra=0.0, settled=False,
               month=month())
    if user.get("is_admin"):
        rec["admin"] = True
        return rec
    with _lock:
        u = usage(user)
        c = accounts.conn()
        try:
            if tier == "free":
                if u["free_videos_used"] >= plans()["free"]["videos_per_month"]:
                    raise LimitError(f"you've used your {plans()['free']['videos_per_month']} free videos this month. "
                                     f"Upgrade to Pro for more.")
                _bump(c, user["id"], free_videos=1)
                ledger(c, user["id"], project, "free_video", 0, 0)
            else:
                need = float(minutes)
                monthly_left = max(0.0, plans()["pro"]["pro_minutes"] - u["pro_minutes_used"]) if plan_id == "pro" else 0.0
                extra = float(user.get("extra_minutes") or 0)
                if need > monthly_left + extra + 1e-6:
                    raise LimitError(f"this video needs {need:g} Pro minutes and you have {monthly_left + extra:.1f} left. "
                                     f"Make it shorter or buy a minutes pack.")
                take_m = min(need, monthly_left)
                take_x = need - take_m
                _bump(c, user["id"], pro_minutes=take_m)
                c.execute("UPDATE users SET extra_minutes = extra_minutes - ? WHERE id=?", (take_x, user["id"]))
                ledger(c, user["id"], project, "reserve", -take_m, -take_x, f"{need:g} min")
                rec.update(monthly=take_m, extra=take_x)
            c.commit()
        finally:
            c.close()
    return rec


def charge_extra(user, minutes, project, note):
    """Take extra Pro minutes for an add-on (e.g. an AI Short). Raises LimitError if not enough."""
    if user.get("is_admin"):
        return dict(monthly=0, extra=0)
    with _lock:
        u = usage(user)
        plan_id = effective_plan(user)
        monthly_left = max(0.0, plans()["pro"]["pro_minutes"] - u["pro_minutes_used"]) if plan_id == "pro" else 0.0
        extra = float(user.get("extra_minutes") or 0)
        if minutes > monthly_left + extra + 1e-6:
            raise LimitError(f"{note} needs {minutes:g} Pro minutes and you have {monthly_left + extra:.1f} left")
        take_m = min(minutes, monthly_left)
        take_x = minutes - take_m
        c = accounts.conn()
        try:
            _bump(c, user["id"], pro_minutes=take_m)
            c.execute("UPDATE users SET extra_minutes = extra_minutes - ? WHERE id=?", (take_x, user["id"]))
            ledger(c, user["id"], project, "addon", -take_m, -take_x, note)
            c.commit()
        finally:
            c.close()
        return dict(monthly=take_m, extra=take_x)


def settle(rec, actual_minutes, project):
    """Give back the unused part of a Pro reservation once the real length is known. Returns the updated record."""
    if not rec or rec.get("settled") or rec.get("tier") != "pro" or rec.get("admin"):
        if rec:
            rec["settled"] = True
        return rec
    charged = rec["monthly"] + rec["extra"]
    actual = math.ceil(max(0.0, actual_minutes) * 10) / 10
    back = max(0.0, charged - actual)
    back_x = min(back, rec["extra"])
    back_m = back - back_x
    with _lock:
        c = accounts.conn()
        try:
            if back_m and rec.get("month") == month():
                _bump(c, rec["user_id"], pro_minutes=-back_m)
            elif back_m:
                back_x += back_m  # last month's allowance is gone; return it as extra minutes instead
                back_m = 0
            c.execute("UPDATE users SET extra_minutes = extra_minutes + ? WHERE id=?", (back_x, rec["user_id"]))
            ledger(c, rec["user_id"], project, "settle", back_m, back_x, f"used {actual:g} of {charged:g} min")
            c.commit()
        finally:
            c.close()
    rec.update(settled=True, used=actual, refunded=round(back_m + back_x, 2))
    return rec


def refund_all(rec, project, note="refund"):
    """Give back everything (e.g. the video was deleted before it was finished)."""
    if not rec or rec.get("settled") or rec.get("admin"):
        return rec
    with _lock:
        c = accounts.conn()
        try:
            if rec["tier"] == "free":
                if rec.get("month") == month():
                    _bump(c, rec["user_id"], free_videos=-1)
            else:
                m, x = rec["monthly"], rec["extra"]
                add = rec.get("addon") or {}
                m, x = m + float(add.get("monthly") or 0), x + float(add.get("extra") or 0)
                if rec.get("month") != month():
                    x, m = x + m, 0
                if m:
                    _bump(c, rec["user_id"], pro_minutes=-m)
                c.execute("UPDATE users SET extra_minutes = extra_minutes + ? WHERE id=?", (x, rec["user_id"]))
            ledger(c, rec["user_id"], project, note, rec.get("monthly", 0), rec.get("extra", 0))
            c.commit()
        finally:
            c.close()
    rec["settled"] = True
    rec["refunded"] = rec.get("minutes")
    return rec


def add_minutes(user_id, minutes, note="pack"):
    c = accounts.conn()
    try:
        c.execute("UPDATE users SET extra_minutes = extra_minutes + ? WHERE id=?", (float(minutes), user_id))
        ledger(c, user_id, "", note, 0, float(minutes))
        c.commit()
    finally:
        c.close()


def providers_for(tier):
    """Provider choice for a plan, falling back to the Free plan's tool (then the always-available one) when a
    paid tool isn't set up on this server yet."""
    want = dict(plans()["pro" if tier == "pro" else "free"]["providers"])
    free = plans()["free"]["providers"]
    safe = {"transcript": "youtube_captions", "llm": "anthropic", "voice": "kokoro", "music": "synth", "image": "local",
            "shorts": "stickman"}
    out, notes = {}, []
    want.setdefault("shorts", "stickman")
    for st, pid in want.items():
        chosen = None
        for cand in (pid, free.get(st), safe[st]):
            try:
                p = P.get(st, cand)
            except KeyError:
                continue
            if p.id == "claude_cli":
                continue  # a personal Claude subscription can't serve other people's videos
            if p.available()[0]:
                chosen = cand
                break
        if chosen is None:
            chosen = safe[st]
            notes.append(f"{st}: no working tool on this server")
        elif chosen != pid:
            notes.append(f"{st}: {pid} isn't set up, using {chosen}")
        out[st] = chosen
    return out, notes
