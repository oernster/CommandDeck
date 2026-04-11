from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure `backend/` is on sys.path so `import app.*` works.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="function")
def test_db_path() -> str:
    """Create a fresh temporary database file per test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        yield path
    finally:
        os.remove(path)


@pytest.fixture(scope="function")
def db_connection(test_db_path: str) -> sqlite3.Connection:
    """Provide a real SQLite connection."""
    # TestClient may execute app code in a different thread.
    conn = sqlite3.connect(test_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    init_db(conn)

    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="function")
def client(db_connection: sqlite3.Connection) -> TestClient:
    """FastAPI test client using real DB (no mocks)."""

    def _get_test_db():
        yield db_connection

    app.dependency_overrides[get_db] = _get_test_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
