"""User accounts and login sessions for hosted mode (SQLite in data/studio.db).

Passwords are hashed with scrypt and a random salt. Session tokens are random 32-byte values; only their
SHA-256 is stored, so a leaked database doesn't hand out logins.
"""
import hashlib
import hmac
import re
import secrets
import threading
import time

from .. import db

SESSION_DAYS = 30
_lock = threading.Lock()
_attempts = {}  # (ip, email) -> [timestamps] for login rate limiting

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  pw_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  created REAL,
  is_admin INTEGER DEFAULT 0,
  plan TEXT DEFAULT 'free',
  extra_minutes REAL DEFAULT 0,
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  sub_status TEXT,
  disabled INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER, created REAL, expires REAL
);
CREATE TABLE IF NOT EXISTS usage (
  user_id INTEGER, month TEXT, free_videos INTEGER DEFAULT 0, pro_minutes REAL DEFAULT 0,
  PRIMARY KEY (user_id, month)
);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, project TEXT, kind TEXT, monthly REAL, extra REAL,
  note TEXT, at REAL
);
CREATE TABLE IF NOT EXISTS stripe_events (id TEXT PRIMARY KEY, type TEXT, at REAL);
"""

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    pass


def conn():
    c = db.connect()
    c.executescript(SCHEMA)
    return c


def _hash(password, salt_hex):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2 ** 14, r=8, p=1, dklen=64).hex()


def _row(r):
    if r is None:
        return None
    d = dict(r)
    d.pop("pw_hash", None)
    d.pop("salt", None)
    d["is_admin"] = bool(d.get("is_admin"))
    d["disabled"] = bool(d.get("disabled"))
    return d


def get_user(user_id):
    c = conn()
    try:
        return _row(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    finally:
        c.close()


def find_user(email):
    c = conn()
    try:
        return _row(c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone())
    finally:
        c.close()


def list_users():
    c = conn()
    try:
        return [_row(r) for r in c.execute("SELECT * FROM users ORDER BY created DESC")]
    finally:
        c.close()


def count_users():
    c = conn()
    try:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        c.close()


def create_user(email, password, admin_email=""):
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 200:
        raise AuthError("please enter a valid email address")
    if len(password or "") < 8:
        raise AuthError("the password needs at least 8 characters")
    salt = secrets.token_hex(16)
    with _lock:
        c = conn()
        try:
            first = c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            # STUDIO_ADMIN_EMAIL decides who is admin; without it the very first account is
            is_admin = 1 if (email == admin_email.strip().lower() if admin_email else first) else 0
            try:
                cur = c.execute("INSERT INTO users (email, pw_hash, salt, created, is_admin) VALUES (?,?,?,?,?)",
                                (email, _hash(password, salt), salt, time.time(), is_admin))
            except Exception:
                raise AuthError("an account with this email already exists")
            c.commit()
            return get_user(cur.lastrowid)
        finally:
            c.close()


def set_password(user_id, password):
    if len(password or "") < 8:
        raise AuthError("the password needs at least 8 characters")
    salt = secrets.token_hex(16)
    c = conn()
    try:
        c.execute("UPDATE users SET pw_hash=?, salt=? WHERE id=?", (_hash(password, salt), salt, user_id))
        c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        c.commit()
    finally:
        c.close()


def update_user(user_id, **fields):
    allowed = {"plan", "extra_minutes", "stripe_customer_id", "stripe_subscription_id", "sub_status", "is_admin",
               "disabled"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_user(user_id)
    c = conn()
    try:
        sets = ", ".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE users SET {sets} WHERE id=?", (*fields.values(), user_id))
        if fields.get("disabled"):
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        c.commit()
    finally:
        c.close()
    return get_user(user_id)


def user_by_stripe(customer_id=None, subscription_id=None):
    c = conn()
    try:
        r = None
        if subscription_id:
            r = c.execute("SELECT * FROM users WHERE stripe_subscription_id=?", (subscription_id,)).fetchone()
        if r is None and customer_id:
            r = c.execute("SELECT * FROM users WHERE stripe_customer_id=?", (customer_id,)).fetchone()
        return _row(r)
    finally:
        c.close()


def rate_limited(ip, email, limit=10, window=600):
    now = time.time()
    key = (ip or "", (email or "").lower())
    hits = [t for t in _attempts.get(key, []) if now - t < window]
    _attempts[key] = hits
    return len(hits) >= limit


def note_failure(ip, email):
    _attempts.setdefault((ip or "", (email or "").lower()), []).append(time.time())


def login(email, password, ip=""):
    if rate_limited(ip, email):
        raise AuthError("too many attempts; wait a few minutes and try again")
    c = conn()
    try:
        r = c.execute("SELECT * FROM users WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    finally:
        c.close()
    if r is None:
        _hash(password or "", "00" * 16)   # same work either way, so timing doesn't reveal which emails exist
    if r is None or not hmac.compare_digest(_hash(password or "", r["salt"]), r["pw_hash"]):
        note_failure(ip, email)
        raise AuthError("wrong email or password")
    if r["disabled"]:
        raise AuthError("this account is disabled")
    return _row(r)


def new_session(user_id):
    token = secrets.token_urlsafe(32)
    c = conn()
    try:
        now = time.time()
        c.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                  (hashlib.sha256(token.encode()).hexdigest(), user_id, now, now + SESSION_DAYS * 86400))
        c.execute("DELETE FROM sessions WHERE expires < ?", (now,))
        c.commit()
    finally:
        c.close()
    return token


def user_for_token(token):
    if not token:
        return None
    c = conn()
    try:
        r = c.execute("SELECT user_id, expires FROM sessions WHERE token_hash=?",
                      (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    finally:
        c.close()
    if r is None or r["expires"] < time.time():
        return None
    u = get_user(r["user_id"])
    if not u or u["disabled"]:
        return None
    return u


def end_session(token):
    if not token:
        return
    c = conn()
    try:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        c.commit()
    finally:
        c.close()


def event_seen(event_id, event_type):
    """Record a Stripe event id; returns True if it was already processed (webhooks can be delivered twice)."""
    c = conn()
    try:
        try:
            c.execute("INSERT INTO stripe_events VALUES (?,?,?)", (event_id, event_type, time.time()))
            c.commit()
            return False
        except Exception:
            return True
    finally:
        c.close()
