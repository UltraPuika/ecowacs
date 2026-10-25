"""SQLite storage for settings, cleaning history, events and command log."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    kind TEXT NOT NULL,
    rooms TEXT,
    started_by TEXT NOT NULL,
    result TEXT,
    area_m2 REAL,
    minutes REAL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    name TEXT NOT NULL,
    params TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL
);
"""

MAX_EVENTS = 2000
MAX_COMMANDS = 2000


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Storage:
    """Small synchronous SQLite wrapper. Every query is short."""

    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.execute("PRAGMA journal_mode=WAL")

    def close(self) -> None:
        """Close the database."""
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, args: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    def _all(self, sql: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    # settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._all("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_setting(self, key: str, value: Any) -> None:
        self._exec(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )

    # sessions
    def open_session(self, kind: str, rooms: list[str] | None, started_by: str) -> int:
        cur = self._exec(
            "INSERT INTO sessions(started_at, kind, rooms, started_by) VALUES(?, ?, ?, ?)",
            (_now(), kind, json.dumps(rooms or []), started_by),
        )
        return int(cur.lastrowid or 0)

    def open_session_id(self) -> int | None:
        rows = self._all("SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1")
        return rows[0]["id"] if rows else None

    def current_session(self) -> dict[str, Any] | None:
        """The session in progress, if any."""
        rows = self._all("SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1")
        if not rows:
            return None
        rows[0]["rooms"] = json.loads(rows[0]["rooms"] or "[]")
        return rows[0]

    def close_session(
        self, session_id: int, result: str, area: float | None, minutes: float | None
    ) -> None:
        self._exec(
            "UPDATE sessions SET ended_at=?, result=?, area_m2=?, minutes=? WHERE id=?",
            (_now(), result, area, minutes, session_id),
        )

    def sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
        for row in rows:
            row["rooms"] = json.loads(row["rooms"] or "[]")
        return rows

    def clear_history(self) -> None:
        self._exec("DELETE FROM sessions")
        self._exec("DELETE FROM events")
        self._exec("DELETE FROM commands")

    # events and commands
    def add_event(self, level: str, kind: str, message: str) -> None:
        self._exec(
            "INSERT INTO events(ts, level, kind, message) VALUES(?, ?, ?, ?)",
            (_now(), level, kind, message),
        )
        self._exec(
            "DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?", (MAX_EVENTS,)
        )

    def events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))

    def add_command(self, name: str, params: dict[str, Any], status: str, message: str) -> None:
        self._exec(
            "INSERT INTO commands(ts, name, params, status, message) VALUES(?, ?, ?, ?, ?)",
            (_now(), name, json.dumps(params, ensure_ascii=False), status, message),
        )
        self._exec(
            "DELETE FROM commands WHERE id <= (SELECT MAX(id) FROM commands) - ?", (MAX_COMMANDS,)
        )

    def commands(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM commands ORDER BY id DESC LIMIT ?", (limit,))
        for row in rows:
            row["params"] = json.loads(row["params"])
        return rows
