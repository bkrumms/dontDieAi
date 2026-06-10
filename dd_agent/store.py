"""SQLite-backed persistence for the Discord bot.

Two tables:
  users — discord_id → encrypted JWT + character + DD api base
  runs  — run lifecycle (queued, running, finished, errored, stuck)

All JWT material is stored encrypted; secrets module owns the key.
The bot NEVER auto-forfeits — runs that go stuck stay stuck until the
user acts on them. See feedback_no_auto_forfeit.md.
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional

from . import secrets


DB_PATH = Path(os.getenv("DD_BOT_DB_PATH", "./bot_state.db"))

RUN_STATUSES = ("queued", "running", "finished", "errored", "stuck")
NON_TERMINAL = ("queued", "running")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    discord_id    TEXT PRIMARY KEY,
    character_id  TEXT NOT NULL,
    encrypted_jwt TEXT NOT NULL,
    dd_api_base   TEXT NOT NULL,
    registered_at INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    dd_session_id   TEXT,
    thread_id       TEXT,
    status          TEXT NOT NULL,
    started_at      INTEGER NOT NULL,
    last_event_at   INTEGER NOT NULL,
    end_reason      TEXT,
    summary_path    TEXT,
    notes           TEXT,
    interactivity   INTEGER DEFAULT 0,
    parent_run_id   INTEGER,
    FOREIGN KEY(discord_id) REFERENCES users(discord_id)
);

CREATE INDEX IF NOT EXISTS runs_by_user
    ON runs(discord_id, status);

CREATE INDEX IF NOT EXISTS runs_by_status
    ON runs(status);
"""


_initialized = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent schema additions for existing DBs."""
    for col, ddl in (
        ("interactivity", "ALTER TABLE runs ADD COLUMN interactivity INTEGER DEFAULT 0"),
        ("parent_run_id", "ALTER TABLE runs ADD COLUMN parent_run_id INTEGER"),
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column exists


@contextmanager
def _cursor() -> Iterator[sqlite3.Cursor]:
    global _initialized
    conn = _connect()
    try:
        if not _initialized:
            conn.executescript(SCHEMA)
            _migrate(conn)
            _initialized = True
        yield conn.cursor()
    finally:
        conn.close()


def now() -> int:
    return int(time.time())


# ---------------------------------------------------------------- users

def users_upsert(discord_id: str, character_id: str, jwt: str, dd_api_base: str) -> None:
    enc = secrets.encrypt(jwt)
    ts = now()
    with _cursor() as c:
        c.execute(
            """
            INSERT INTO users (discord_id, character_id, encrypted_jwt, dd_api_base,
                               registered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                character_id  = excluded.character_id,
                encrypted_jwt = excluded.encrypted_jwt,
                dd_api_base   = excluded.dd_api_base,
                updated_at    = excluded.updated_at
            """,
            (discord_id, character_id, enc, dd_api_base, ts, ts),
        )


def users_get(discord_id: str) -> Optional[dict]:
    with _cursor() as c:
        row = c.execute(
            "SELECT * FROM users WHERE discord_id=?", (discord_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["jwt"] = secrets.decrypt(d.pop("encrypted_jwt"))
    return d


def users_delete(discord_id: str) -> bool:
    with _cursor() as c:
        c.execute("DELETE FROM users WHERE discord_id=?", (discord_id,))
        return c.rowcount > 0


# ---------------------------------------------------------------- runs

def runs_create(discord_id: str, thread_id: Optional[str] = None,
                interactivity: int = 0) -> int:
    ts = now()
    with _cursor() as c:
        c.execute(
            """
            INSERT INTO runs (discord_id, thread_id, status, started_at, last_event_at, interactivity)
            VALUES (?, ?, 'queued', ?, ?, ?)
            """,
            (discord_id, thread_id, ts, ts, interactivity),
        )
        return c.lastrowid


def runs_create_resume(discord_id: str, thread_id: Optional[str], dd_session_id: str,
                       interactivity: int, parent_run_id: Optional[int] = None,
                       note: Optional[str] = None) -> int:
    """Create a new run row already attached to an existing DD session.
    Used by:
      - Restart button after a stuck run (parent_run_id = previous run)
      - /resume command (parent_run_id = previous stuck run)
      - /attach command (parent_run_id = None — fresh attach to a session
        the bot didn't create)
    """
    ts = now()
    if note is None:
        note = (
            f"resumed from run #{parent_run_id}" if parent_run_id is not None
            else "attached to externally-started session"
        )
    with _cursor() as c:
        c.execute(
            """
            INSERT INTO runs (discord_id, thread_id, dd_session_id, status,
                              started_at, last_event_at, interactivity, parent_run_id, notes)
            VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)
            """,
            (discord_id, thread_id, dd_session_id, ts, ts, interactivity,
             parent_run_id, note),
        )
        return c.lastrowid


def runs_set_session(run_id: int, dd_session_id: str) -> None:
    with _cursor() as c:
        c.execute(
            "UPDATE runs SET dd_session_id=?, status='running', last_event_at=? WHERE id=?",
            (dd_session_id, now(), run_id),
        )


def runs_set_status(
    run_id: int,
    status: str,
    end_reason: Optional[str] = None,
    summary_path: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    if status not in RUN_STATUSES:
        raise ValueError(f"unknown status: {status}")
    with _cursor() as c:
        c.execute(
            """
            UPDATE runs SET
                status        = ?,
                end_reason    = COALESCE(?, end_reason),
                summary_path  = COALESCE(?, summary_path),
                notes         = COALESCE(?, notes),
                last_event_at = ?
            WHERE id = ?
            """,
            (status, end_reason, summary_path, notes, now(), run_id),
        )


def runs_touch(run_id: int) -> None:
    with _cursor() as c:
        c.execute("UPDATE runs SET last_event_at=? WHERE id=?", (now(), run_id))


def runs_get(run_id: int) -> Optional[dict]:
    with _cursor() as c:
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None


def runs_active_for_user(discord_id: str) -> Optional[dict]:
    with _cursor() as c:
        row = c.execute(
            "SELECT * FROM runs WHERE discord_id=? AND status IN ('queued','running') "
            "ORDER BY id DESC LIMIT 1",
            (discord_id,),
        ).fetchone()
    return dict(row) if row else None


def runs_by_status(statuses: Iterable[str]) -> list[dict]:
    placeholders = ",".join("?" * len(list(statuses)))
    statuses = list(statuses)
    placeholders = ",".join("?" * len(statuses))
    with _cursor() as c:
        rows = c.execute(
            f"SELECT * FROM runs WHERE status IN ({placeholders})",
            statuses,
        ).fetchall()
    return [dict(r) for r in rows]


def runs_recent_for_user(discord_id: str, limit: int = 10) -> list[dict]:
    with _cursor() as c:
        rows = c.execute(
            "SELECT * FROM runs WHERE discord_id=? ORDER BY id DESC LIMIT ?",
            (discord_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def runs_resumable(discord_id: str, limit: int = 25) -> list[dict]:
    """Stuck runs that have a DD session id we can try to attach to.
    Filters: only the LATEST row per dd_session_id (so a chain of
    parent→resume→stuck shows only the most recent stuck attempt).
    """
    with _cursor() as c:
        rows = c.execute(
            """
            SELECT r.* FROM runs r
            WHERE r.discord_id = ?
              AND r.status = 'stuck'
              AND r.dd_session_id IS NOT NULL
              AND r.id = (
                  SELECT MAX(r2.id) FROM runs r2
                  WHERE r2.dd_session_id = r.dd_session_id
                    AND r2.discord_id = r.discord_id
              )
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (discord_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
