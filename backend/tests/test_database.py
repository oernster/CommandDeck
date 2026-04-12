from __future__ import annotations

import sqlite3

from app.core.database import _connect, get_db, init_db


def test_init_db_creates_schema() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    init_db(conn)

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
    }
    assert {"commands", "outcomes", "sessions"}.issubset(tables)

    conn.close()


def test_connect_enables_row_factory_and_foreign_keys(tmp_path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = _connect(db_path)

    try:
        assert conn.row_factory is sqlite3.Row
        assert conn.execute("PRAGMA foreign_keys;").fetchone()[0] == 1
    finally:
        conn.close()


def test_repository_defensive_enum_corruption_raises(tmp_path) -> None:
    # This is a real DB test (no mocks): we insert corrupted enum values directly
    # and assert the repository fails fast.
    import sqlite3

    from app.core.database import init_db
    from app.repositories.command_repository import CommandRepository

    conn = sqlite3.connect(str(tmp_path / "corrupt.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn)

    conn.execute(
        "INSERT INTO commands (title, category, status, sort_index, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("Bad", "NotACategory", "NotAStatus", 1, 1),
    )
    conn.commit()

    repo = CommandRepository(conn)
    try:
        repo.list(category=None, status=None)
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "Invalid enum value" in str(exc)
    finally:
        conn.close()


def test_init_db_upgrades_existing_commands_table_without_sort_index(tmp_path) -> None:
    """Covers the small v1 in-app migration that adds commands.sort_index."""

    conn = sqlite3.connect(str(tmp_path / "legacy.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # Simulate an older schema (no sort_index).
    conn.execute("""
        CREATE TABLE commands (
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """.strip())
    # Insert 2 commands in Design in the legacy ordering (created_at DESC).
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, created_at) "
            "VALUES (?,?,?,?,?)"
        ),
        (1, "A", "Design", "Not Started", 10),
    )
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, created_at) "
            "VALUES (?,?,?,?,?)"
        ),
        (2, "B", "Design", "Not Started", 11),
    )
    conn.commit()

    # Running init_db should add the column and backfill sort_index, preserving
    # the *current* visual order (created_at DESC): id=2 should be first.
    init_db(conn)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(commands)").fetchall()]
    assert "sort_index" in cols

    rows = conn.execute(
        "SELECT id, sort_index FROM commands WHERE category = ? ORDER BY sort_index",
        ("Design",),
    ).fetchall()
    assert [(int(r["id"]), int(r["sort_index"])) for r in rows] == [(2, 1), (1, 2)]

    conn.close()


def test_init_db_backfill_appends_when_partially_initialized(tmp_path) -> None:
    conn = sqlite3.connect(str(tmp_path / "partial.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # Legacy commands table.
    conn.execute("""
        CREATE TABLE commands (
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """.strip())
    # Pretend an external tool already added sort_index and set one row.
    conn.execute(
        "ALTER TABLE commands ADD COLUMN sort_index INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, sort_index, "
            "created_at) VALUES (?,?,?,?,?,?)"
        ),
        (1, "Existing", "Build", "Not Started", 5, 100),
    )
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, sort_index, "
            "created_at) VALUES (?,?,?,?,?,?)"
        ),
        (2, "NeedsBackfill", "Build", "Not Started", 0, 101),
    )
    conn.commit()

    init_db(conn)

    rows = conn.execute(
        "SELECT id, sort_index FROM commands WHERE category = ? ORDER BY sort_index",
        ("Build",),
    ).fetchall()
    assert [(int(r["id"]), int(r["sort_index"])) for r in rows] == [(1, 5), (2, 6)]

    conn.close()


def test_init_db_no_backfill_when_all_sort_index_initialized(tmp_path) -> None:
    """Covers the early-continue branch when there are no zero sort_index rows."""

    conn = sqlite3.connect(str(tmp_path / "all_init.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # Legacy-ish table with sort_index already present.
    conn.execute("""
        CREATE TABLE commands (
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          sort_index INTEGER NOT NULL DEFAULT 0
        );
        """.strip())
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, sort_index, "
            "created_at) VALUES (?,?,?,?,?,?)"
        ),
        (1, "A", "Review", "Not Started", 1, 1),
    )
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, sort_index, "
            "created_at) VALUES (?,?,?,?,?,?)"
        ),
        (2, "B", "Review", "Not Started", 2, 2),
    )
    conn.commit()

    init_db(conn)

    rows = conn.execute(
        "SELECT id, sort_index FROM commands WHERE category = ? ORDER BY sort_index",
        ("Review",),
    ).fetchall()
    assert [(int(r["id"]), int(r["sort_index"])) for r in rows] == [(1, 1), (2, 2)]

    conn.close()


def test_command_repository_reorder_duplicate_ids_raises_value_error(tmp_path) -> None:
    import sqlite3

    from app.core.database import init_db
    from app.domain.enums import Category
    from app.repositories.command_repository import CommandRepository

    conn = sqlite3.connect(str(tmp_path / "dup.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn)

    # Create two valid commands.
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, sort_index, "
            "created_at) VALUES (?,?,?,?,?,?)"
        ),
        (1, "A", "Design", "Not Started", 1, 1),
    )
    conn.execute(
        (
            "INSERT INTO commands (id, title, category, status, sort_index, "
            "created_at) VALUES (?,?,?,?,?,?)"
        ),
        (2, "B", "Design", "Not Started", 2, 2),
    )
    conn.commit()

    repo = CommandRepository(conn)
    try:
        repo.reorder({Category.DESIGN: [1, 1]})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "duplicate" in str(exc).lower()
    finally:
        conn.close()


def test_session_repository_defensive_category_corruption_raises(tmp_path) -> None:
    # Real DB, no mocks: insert corrupted category directly.
    import sqlite3

    from app.core.database import init_db
    from app.repositories.session_repository import SessionRepository

    conn = sqlite3.connect(str(tmp_path / "bad_session.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn)

    conn.execute(
        "INSERT INTO sessions (category, started_at, ended_at) VALUES (?, ?, NULL)",
        ("NotACategory", 1),
    )
    conn.commit()

    repo = SessionRepository(conn)
    try:
        repo.list(category=None, active=None)
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "Invalid enum value" in str(exc)
    finally:
        conn.close()


def test_session_repository_start_rolls_back_on_insert_failure(tmp_path) -> None:
    # Real DB, no mocks: use a trigger to force an INSERT failure inside the
    # repository transaction and assert rollback.
    import sqlite3

    from app.core.database import init_db
    from app.domain.enums import Category
    from app.repositories.session_repository import SessionRepository

    conn = sqlite3.connect(str(tmp_path / "tx.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn)

    # Seed an active session.
    conn.execute(
        "INSERT INTO sessions (category, started_at, ended_at) VALUES (?, ?, NULL)",
        ("Design", 1),
    )
    conn.commit()

    # Force session inserts to fail.
    conn.execute("""
        CREATE TRIGGER fail_session_insert
        BEFORE INSERT ON sessions
        BEGIN
          SELECT RAISE(ABORT, 'forced');
        END;
        """.strip())
    conn.commit()

    repo = SessionRepository(conn)
    try:
        repo.start(category=Category.BUILD, now_epoch_seconds=2)
        raise AssertionError("Expected sqlite error")
    except sqlite3.DatabaseError:
        pass

    # Rollback should have kept the original session active.
    row = conn.execute(
        "SELECT category, started_at, ended_at FROM sessions WHERE id = 1"
    ).fetchone()
    assert row["category"] == "Design"
    assert row["started_at"] == 1
    assert row["ended_at"] is None

    conn.close()


def test_get_db_yields_initialized_connection(tmp_path) -> None:
    # We call the dependency generator directly and ensure it initializes schema.
    from app.core import config

    original = config.SETTINGS
    config.SETTINGS = config.Settings(sqlite_path=str(tmp_path / "dep.db"))
    try:
        gen = get_db()
        conn = next(gen)

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
        }
        assert {"commands", "outcomes", "sessions"}.issubset(tables)

        try:
            next(gen)
            raise AssertionError("generator should be exhausted")
        except StopIteration:
            pass
    finally:
        config.SETTINGS = original


def test_connect_creates_parent_dir_when_missing(tmp_path) -> None:
    from app.core.database import _connect

    sqlite_path = str(tmp_path / "nested" / "dir" / "x.db")
    conn = _connect(sqlite_path)
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()


def test_init_database_file_creates_parent_dir_when_missing(
    tmp_path, monkeypatch
) -> None:
    from app.core import config
    from app.core.lifecycle import init_database_file

    db_path = str(tmp_path / "nested" / "db" / "test.db")
    original = config.SETTINGS
    config.SETTINGS = config.Settings(sqlite_path=db_path)
    try:
        init_database_file()
        assert (tmp_path / "nested" / "db").is_dir()
    finally:
        config.SETTINGS = original


def test_init_database_file_dir_creation_except_path_is_defensive(
    monkeypatch, tmp_path
) -> None:
    from app.core import config
    from app.core.lifecycle import init_database_file

    db_path = str(tmp_path / "nested" / "db" / "test.db")
    original = config.SETTINGS
    config.SETTINGS = config.Settings(sqlite_path=db_path)
    try:

        def _boom(*_args, **_kwargs):  # noqa: ANN001
            raise RuntimeError("boom")

        # Force the directory creation attempt to raise.
        monkeypatch.setattr("pathlib.Path.mkdir", _boom, raising=True)

        # When directory creation fails, sqlite connect may still fail too.
        # We only assert that the mkdir exception is swallowed.
        import pytest

        with pytest.raises(sqlite3.OperationalError):
            init_database_file()
    finally:
        config.SETTINGS = original


def test_connect_dir_creation_except_path_is_defensive(monkeypatch, tmp_path) -> None:
    from app.core.database import _connect

    sqlite_path = str(tmp_path / "x.db")

    def _boom(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr("pathlib.Path.mkdir", _boom, raising=True)

    conn = _connect(sqlite_path)
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()
