from __future__ import annotations

from pathlib import Path
import sqlite3

from app.core import config
from app.core.database import init_db


def init_database_file() -> None:
    """Ensure the configured SQLite database file has the required schema."""
    # Ensure parent directory exists (important for per-user appdata paths).
    try:
        Path(config.SETTINGS.sqlite_path).expanduser().resolve().parent.mkdir(
            parents=True, exist_ok=True
        )
    except Exception:
        # If we can't create dirs, let sqlite raise a clearer error.
        pass

    conn = sqlite3.connect(config.SETTINGS.sqlite_path, check_same_thread=False)
    try:
        init_db(conn)
    finally:
        conn.close()
