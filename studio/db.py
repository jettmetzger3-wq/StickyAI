"""SQLite index of projects, stages and costs (the library page and cost ledger read from here).

Each project's folder (meta.json) stays the source of truth; this database mirrors it after every change.
"""
import json
import os
import sqlite3
import threading

from .config import DATA_DIR, ensure_dirs

DB_PATH = os.path.join(DATA_DIR, "studio.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  slug TEXT PRIMARY KEY, title TEXT, mode TEXT, source_url TEXT, topic TEXT, status TEXT,
  created REAL, updated REAL, minutes REAL, providers TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS stages (
  slug TEXT, stage TEXT, status TEXT, progress REAL, message TEXT, started REAL, finished REAL,
  PRIMARY KEY (slug, stage)
);
CREATE TABLE IF NOT EXISTS costs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, stage TEXT, provider TEXT, usd REAL, credits REAL,
  note TEXT, at REAL
);
"""


def connect():
    ensure_dirs()
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def sync(meta):
    if not meta or not meta.get("slug"):
        return
    with _lock:
        con = connect()
        try:
            s = meta["slug"]
            con.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (s, meta.get("title"), meta.get("mode"), meta.get("source_url"), meta.get("topic"),
                         meta.get("status"), meta.get("created"), meta.get("updated"),
                         float((meta.get("options") or {}).get("minutes") or 0), json.dumps(meta.get("providers") or {}),
                         meta.get("error")))
            for st, v in (meta.get("stages") or {}).items():
                con.execute("INSERT OR REPLACE INTO stages VALUES (?,?,?,?,?,?,?)",
                            (s, st, v.get("status"), v.get("progress"), v.get("message"), v.get("started"), v.get("finished")))
            con.execute("DELETE FROM costs WHERE slug=?", (s,))
            for c in meta.get("costs") or []:
                con.execute("INSERT INTO costs (slug, stage, provider, usd, credits, note, at) VALUES (?,?,?,?,?,?,?)",
                            (s, c.get("stage"), c.get("provider"), c.get("usd"), c.get("credits"), c.get("note"), c.get("at")))
            con.commit()
        finally:
            con.close()


def remove(slug):
    with _lock:
        con = connect()
        try:
            for t in ("projects", "stages", "costs"):
                con.execute(f"DELETE FROM {t} WHERE slug=?", (slug,))
            con.commit()
        finally:
            con.close()


def spend_summary():
    con = connect()
    try:
        row = con.execute("SELECT COALESCE(SUM(usd),0) AS usd, COALESCE(SUM(credits),0) AS credits FROM costs").fetchone()
        per = [dict(r) for r in con.execute(
            "SELECT provider, COALESCE(SUM(usd),0) AS usd, COALESCE(SUM(credits),0) AS credits FROM costs GROUP BY provider")]
        return dict(usd=row["usd"], credits=row["credits"], by_provider=per)
    finally:
        con.close()
