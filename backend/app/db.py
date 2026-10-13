"""SQLite: the officer's findings and the stored narratives.

Case results themselves are recomputed from the cached data, so they are not stored.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes(
  case_id TEXT PRIMARY KEY, check_id TEXT NOT NULL, outcome TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '', closed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS narratives(
  key TEXT PRIMARY KEY, json TEXT NOT NULL, source TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL);
"""


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


def get_outcome(case_id: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM outcomes WHERE case_id=?", (case_id,)).fetchone()
    return dict(row) if row else None


def save_outcome(case_id: str, check_id: str, outcome: str, note: str, closed_at: datetime) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO outcomes(case_id, check_id, outcome, note, closed_at) VALUES (?,?,?,?,?)",
            (case_id, check_id, outcome, note, closed_at.isoformat(timespec="seconds")),
        )


def get_narrative(key: str) -> tuple[str, str] | None:
    with conn() as c:
        row = c.execute("SELECT json, source FROM narratives WHERE key=?", (key,)).fetchone()
    return (row["json"], row["source"]) if row else None


def save_narrative(key: str, json_text: str, source: str, model: str | None) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO narratives(key, json, source, model, created_at) VALUES (?,?,?,?,?)",
            (key, json_text, source, model, now().isoformat(timespec="seconds")),
        )


def reset() -> None:
    with conn() as c:
        c.execute("DELETE FROM outcomes")
        c.execute("DELETE FROM narratives")
