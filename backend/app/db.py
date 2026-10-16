"""SQLite: officers and their sign-in sessions, the officer's findings and the stored narratives.

Case results themselves are recomputed from the cached data, so they are not stored. Findings and
narratives are keyed by area, so two areas never share or overwrite each other's cases.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS officers(
  id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
  pin_salt TEXT NOT NULL, pin_hash TEXT NOT NULL, area_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, officer_id INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_outcomes(
  area_id TEXT NOT NULL, case_id TEXT NOT NULL, check_id TEXT NOT NULL, outcome TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '', closed_at TEXT NOT NULL, closed_by INTEGER,
  PRIMARY KEY (area_id, case_id));
CREATE TABLE IF NOT EXISTS case_findings(
  id INTEGER PRIMARY KEY, area_id TEXT NOT NULL, case_id TEXT NOT NULL, check_id TEXT NOT NULL,
  outcome TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', recorded_at TEXT NOT NULL, recorded_by INTEGER);
CREATE INDEX IF NOT EXISTS case_findings_case ON case_findings(area_id, case_id, id);
CREATE TABLE IF NOT EXISTS narratives(
  key TEXT PRIMARY KEY, json TEXT NOT NULL, source TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL);
-- findings from before areas existed; they cannot be placed in an area
DROP TABLE IF EXISTS outcomes;
"""
PIN_ROUNDS = 120_000


@contextmanager
def conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        c.executescript(SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


def now() -> datetime:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0, tzinfo=None)


def _stamp() -> str:
    return now().isoformat(timespec="seconds")


# ---- officers and sessions

def _pin_hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), PIN_ROUNDS).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_officer(username: str, name: str, pin: str, area_id: str | None = None) -> dict:
    salt = secrets.token_hex(16)
    with conn() as c:
        cur = c.execute(
            "INSERT INTO officers(username, name, pin_salt, pin_hash, area_id, created_at) VALUES (?,?,?,?,?,?)",
            (username, name, salt, _pin_hash(pin, salt), area_id, _stamp()),
        )
        oid = cur.lastrowid
    return get_officer(oid)  # type: ignore[return-value]


def get_officer(officer_id: int) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT id, username, name, area_id FROM officers WHERE id=?", (officer_id,)).fetchone()
    return dict(row) if row else None


def find_officer(username: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT id, username, name, area_id FROM officers WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def check_pin(username: str, pin: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM officers WHERE username=?", (username,)).fetchone()
    if not row or not hmac.compare_digest(row["pin_hash"], _pin_hash(pin, row["pin_salt"])):
        return None
    return get_officer(row["id"])


def set_officer_area(officer_id: int, area_id: str | None) -> None:
    with conn() as c:
        c.execute("UPDATE officers SET area_id=? WHERE id=?", (area_id, officer_id))


def open_session(officer_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with conn() as c:
        c.execute("INSERT INTO sessions(token_hash, officer_id, created_at) VALUES (?,?,?)",
                  (_token_hash(token), officer_id, _stamp()))
    return token


def session_officer(token: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT officer_id FROM sessions WHERE token_hash=?", (_token_hash(token),)).fetchone()
    return get_officer(row["officer_id"]) if row else None


def close_session(token: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))


# ---- findings and narratives

# case_outcomes held one closing finding per case; findings are now a list that keeps the case open,
# so that table is no longer read or written.

def add_finding(area_id: str, case_id: str, check_id: str, outcome: str, note: str, recorded_at: datetime,
                recorded_by: int | None = None) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO case_findings(area_id, case_id, check_id, outcome, note, recorded_at, recorded_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (area_id, case_id, check_id, outcome, note, recorded_at.isoformat(timespec="seconds"), recorded_by),
        )


def list_findings(area_id: str, case_id: str) -> list[dict]:
    """The officer's findings on a case, in the order they were recorded."""
    with conn() as c:
        rows = c.execute("SELECT * FROM case_findings WHERE area_id=? AND case_id=? ORDER BY id",
                         (area_id, case_id)).fetchall()
    return [dict(r) for r in rows]


def get_narrative(key: str) -> tuple[str, str] | None:
    with conn() as c:
        row = c.execute("SELECT json, source FROM narratives WHERE key=?", (key,)).fetchone()
    return (row["json"], row["source"]) if row else None


def save_narrative(key: str, json_text: str, source: str, model: str | None) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO narratives(key, json, source, model, created_at) VALUES (?,?,?,?,?)",
            (key, json_text, source, model, _stamp()),
        )


def reset(area_id: str | None = None) -> None:
    """Clear findings and stored narratives: for one area, or everywhere when no area is given."""
    with conn() as c:
        if area_id is None:
            c.execute("DELETE FROM case_outcomes")
            c.execute("DELETE FROM case_findings")
            c.execute("DELETE FROM narratives")
        else:
            c.execute("DELETE FROM case_outcomes WHERE area_id=?", (area_id,))
            c.execute("DELETE FROM case_findings WHERE area_id=?", (area_id,))
            c.execute("DELETE FROM narratives WHERE key LIKE ?", (f"{area_id}:%",))
