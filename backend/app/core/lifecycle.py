from __future__ import annotations

import sqlite3

from app.core.config import SETTINGS
from app.core.database import init_db


def init_database_file() -> None:
    """Ensure the configured SQLite database file has the required schema."""
    conn = sqlite3.connect(SETTINGS.sqlite_path, check_same_thread=False)
    try:
        init_db(conn)
    finally:
        conn.close()
