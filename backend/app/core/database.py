from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from app.core.config import SETTINGS


def init_db(conn: sqlite3.Connection) -> None:
    """Create the v1 schema if it doesn't exist.

    No migrations framework in v1; schema is explicit and minimal.
    """
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """.strip())
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_commands_category ON commands(category);"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_commands_status ON commands(status);")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
          id INTEGER PRIMARY KEY,
          command_id INTEGER NOT NULL,
          note TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE
        );
        """.strip())
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outcomes_command_created "
        "ON outcomes(command_id, created_at);"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
          id INTEGER PRIMARY KEY,
          category TEXT NOT NULL,
          started_at INTEGER NOT NULL,
          ended_at INTEGER
        );
        """.strip())
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_category ON sessions(category);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at);"
    )

    conn.commit()


def _connect(sqlite_path: str) -> sqlite3.Connection:
    # Ensure parent directory exists (important for per-user appdata paths).
    try:
        Path(sqlite_path).expanduser().resolve().parent.mkdir(
            parents=True, exist_ok=True
        )
    except Exception:
        # If we can't create dirs, let sqlite raise a clearer error.
        pass

    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a SQLite connection."""
    conn = _connect(SETTINGS.sqlite_path)
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()
