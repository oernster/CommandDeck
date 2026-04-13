from __future__ import annotations

import json
import sqlite3

import pytest

from app.core.database import init_db
from app.repositories.board_repository import BoardRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.snapshot_service import SnapshotService
from app.domain.enums import StageId


def _service(conn: sqlite3.Connection) -> SnapshotService:
    return SnapshotService(
        conn=conn,
        board=BoardRepository(conn),
        sessions=SessionRepository(conn),
        snapshots=SnapshotRepository(conn),
    )


def test_ensure_sessions_v2_preserves_existing_sessions_legacy_suffix(tmp_path) -> None:
    """Exercise the upgrade path where sessions_legacy already exists.

    This hits the branch in [`_ensure_sessions_v2()`](backend/app/core/database.py:177)
    that chooses a suffixed legacy table name to avoid clobbering.
    """

    db_path = tmp_path / "suffix.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        # Minimal commands table so init_db can proceed far enough.
        conn.execute(
            """
            CREATE TABLE commands (
              id INTEGER PRIMARY KEY,
              title TEXT NOT NULL,
              stage_id TEXT NOT NULL,
              status TEXT NOT NULL,
              sort_index INTEGER NOT NULL,
              created_at INTEGER NOT NULL
            );
            """.strip()
        )
        # Legacy sessions table missing v2 columns.
        conn.execute(
            """
            CREATE TABLE sessions (
              id INTEGER PRIMARY KEY,
              category TEXT NOT NULL,
              started_at INTEGER NOT NULL,
              ended_at INTEGER
            );
            """.strip()
        )
        # Pre-existing sessions_legacy forces the suffixed rename path.
        conn.execute("CREATE TABLE sessions_legacy (id INTEGER PRIMARY KEY);")
        conn.commit()

        init_db(conn)

        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "sessions" in tables
        assert "sessions_legacy" in tables
        assert "sessions_legacy_2" in tables
    finally:
        conn.close()


def test_ensure_sessions_v2_preserve_loop_increments_past_existing_suffixes(tmp_path) -> None:
    """Exercise the `while _table_exists(..._i)` loop increment branch."""

    db_path = tmp_path / "suffix_loop.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        conn.execute(
            """
            CREATE TABLE commands (
              id INTEGER PRIMARY KEY,
              title TEXT NOT NULL,
              stage_id TEXT NOT NULL,
              status TEXT NOT NULL,
              sort_index INTEGER NOT NULL,
              created_at INTEGER NOT NULL
            );
            """.strip()
        )
        conn.execute(
            """
            CREATE TABLE sessions (
              id INTEGER PRIMARY KEY,
              category TEXT NOT NULL,
              started_at INTEGER NOT NULL,
              ended_at INTEGER
            );
            """.strip()
        )
        conn.execute("CREATE TABLE sessions_legacy (id INTEGER PRIMARY KEY);")
        conn.execute("CREATE TABLE sessions_legacy_2 (id INTEGER PRIMARY KEY);")
        conn.commit()

        init_db(conn)

        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "sessions_legacy_3" in tables
    finally:
        conn.close()


def test_board_service_parses_valid_stage_labels_json(db_connection) -> None:
    """Cover BoardService.get() happy-path JSON parsing."""

    conn = db_connection
    conn.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        (json.dumps({"DESIGN": "Plan"}),),
    )
    conn.commit()

    from app.services.board_service import BoardService

    out = BoardService(BoardRepository(conn)).get()
    assert out["stage_labels"] == {"DESIGN": "Plan"}


def test_board_service_ignores_stage_labels_json_when_values_not_strings(db_connection) -> None:
    """Cover the `isinstance(parsed, dict) and all(...)` false branch."""

    conn = db_connection
    conn.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        (json.dumps({"DESIGN": 123}),),
    )
    conn.commit()

    from app.services.board_service import BoardService

    out = BoardService(BoardRepository(conn)).get()
    assert out["stage_labels"] is None


def test_snapshot_service_get_stage_label_falls_back_when_stage_labels_json_not_dict(
    db_connection,
) -> None:
    """Cover `_get_stage_label()` branch where parsed JSON is not a dict."""

    conn = db_connection
    conn.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        (json.dumps(["DESIGN", "Plan"]),),
    )
    conn.commit()

    svc = _service(conn)
    assert svc._get_stage_label(StageId.DESIGN) == "Design"


def test_snapshot_service_get_stage_label_falls_back_when_value_missing_or_blank(
    db_connection,
) -> None:
    """Cover `_get_stage_label()` branch where dict value is missing/blank."""

    conn = db_connection

    # Missing key -> v is None.
    conn.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        (json.dumps({"BUILD": "Build"}),),
    )
    conn.commit()
    svc = _service(conn)
    assert svc._get_stage_label(StageId.DESIGN) == "Design"

    # Blank value -> v is a string but `v.strip()` is empty.
    conn.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        (json.dumps({"DESIGN": "   "}),),
    )
    conn.commit()
    assert svc._get_stage_label(StageId.DESIGN) == "Design"


def test_snapshot_service_structural_form_active_session_and_invalid_commands_shape() -> None:
    """Hit SnapshotService._structural_form() branches around sessions/commands parsing."""

    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 123,
        # Bad shape: stage key maps to non-list -> should be ignored.
        "commands": {"DESIGN": "not-a-list"},
        "sessions": [
            {"stage_id": "DESIGN", "ended_at": None},
            # Not reached due to break; also checks isinstance(s, dict) guard.
            "not-a-dict",
        ],
    }

    structural = SnapshotService._structural_form(payload)
    assert structural["active_session_stage_id"] == "DESIGN"
    assert structural["commands"] == {}


def test_snapshot_service_structural_form_empty_sessions_and_empty_commands() -> None:
    """Cover the `if not sessions: pass` + `if not commands: pass` branches."""

    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 123,
        "commands": {},
        "sessions": [],
    }
    structural = SnapshotService._structural_form(payload)
    assert structural["active_session_stage_id"] is None
    assert structural["commands"] == {}


def test_snapshot_service_structural_form_skips_non_dict_session_then_finds_active() -> None:
    """Cover session loop path where first element is non-dict then active session is found."""

    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 123,
        "commands": {},
        "sessions": [
            "not-a-dict",
            {"stage_id": "BUILD", "ended_at": None},
        ],
    }
    structural = SnapshotService._structural_form(payload)
    assert structural["active_session_stage_id"] == "BUILD"


def test_snapshot_service_structural_form_commands_list_skips_non_dict_items() -> None:
    """Cover the `if not isinstance(it, dict): continue` branch."""

    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 123,
        "commands": {
            "DESIGN": [
                {"id": 1, "title": "T1", "status": "Not Started"},
                "not-a-dict",
            ]
        },
        "sessions": [],
    }

    structural = SnapshotService._structural_form(payload)
    assert structural["commands"] == {"DESIGN": [{"title": "T1", "status": "Not Started"}]}


def test_snapshot_service_structural_form_commands_not_dict_is_ignored() -> None:
    """Cover the `if isinstance(commands, dict)` false branch."""

    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 123,
        # Truthy but not a dict -> bypasses `or {}` fallback.
        "commands": ["not-a-dict"],
        "sessions": [],
    }

    structural = SnapshotService._structural_form(payload)
    assert structural["commands"] == {}


def test_snapshot_apply_payload_validation_error_board_name_blank(db_connection) -> None:
    """Cover snapshot payload validation branch for blank board_name."""

    service = _service(db_connection)
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(
            {
                "schema_version": 3,
                "board_name": "  ",
                "saved_at": 1,
                "commands": {},
                "sessions": [],
            }
        )


def test_snapshot_apply_payload_validation_error_sessions_wrong_type(db_connection) -> None:
    """Cover snapshot payload validation branch for sessions not list."""

    service = _service(db_connection)
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(
            {
                "schema_version": 3,
                "board_name": "Board",
                "saved_at": 1,
                "commands": {},
                "sessions": "nope",
            }
        )


def test_snapshots_rename_validation_error_empty_string(client):
    created = client.post("/api/snapshots")
    assert created.status_code == 201
    snap = created.json()

    # Covers the explicit empty-name validation branch in
    # [`rename_snapshot()`](backend/app/api/snapshots.py:65).
    r = client.patch(f"/api/snapshots/{snap['id']}", json={"name": ""})
    assert r.status_code == 400


def test_snapshot_apply_payload_validation_error_command_entry_not_dict(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": ["not-a-dict"]},
        "sessions": [],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_title_blank(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": " ", "status": "Not Started"}]},
        "sessions": [],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_status_invalid(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": "Ok", "status": "NO"}]},
        "sessions": [],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_v2_success_inserts_commands_and_ignores_sessions(db_connection) -> None:
    """Cover schema_version!=3 command insert path (v1/v2 compatibility)."""

    service = _service(db_connection)
    payload = {
        "schema_version": 2,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {
            "Design": [
                {"title": "Task A", "status": "Not Started"},
            ]
        },
        "sessions": [],
    }
    service._apply_payload(payload)
    row = db_connection.execute("SELECT title, stage_id FROM commands ORDER BY id ASC").fetchone()
    assert row is not None
    assert row["title"] == "Task A"
    assert row["stage_id"] == "DESIGN"


def test_snapshot_apply_payload_v2_unknown_stage_key_is_ignored(db_connection) -> None:
    """Cover StageId.from_str() returning None in v1/v2 upgrade loop."""

    service = _service(db_connection)
    payload = {
        "schema_version": 2,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"Nope": [{"title": "X", "status": "Not Started"}]},
        "sessions": [],
    }
    service._apply_payload(payload)
    count = db_connection.execute("SELECT COUNT(*) AS c FROM commands").fetchone()["c"]
    assert int(count) == 0


def test_snapshot_apply_payload_validation_error_stage_items_none(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": None},
        "sessions": [],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_stage_items_not_list(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": "nope"},
        "sessions": [],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_entry_id_not_int(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": "1", "title": "Ok", "status": "Not Started"}]},
        "sessions": [],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_session_command_id_not_int(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": "Ok", "status": "Not Started"}]},
        "sessions": [
            {
                "command_id": "1",
                "stage_id": "DESIGN",
                "started_at": 1,
                "ended_at": None,
            }
        ],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_session_stage_id_invalid(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": "Ok", "status": "Not Started"}]},
        "sessions": [
            {
                "command_id": 1,
                "stage_id": "NOPE",
                "started_at": 1,
                "ended_at": None,
            }
        ],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_session_started_at_not_int(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": "Ok", "status": "Not Started"}]},
        "sessions": [
            {
                "command_id": 1,
                "stage_id": "DESIGN",
                "started_at": "1",
                "ended_at": None,
            }
        ],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_session_ended_at_wrong_type(db_connection) -> None:
    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": "Ok", "status": "Not Started"}]},
        "sessions": [
            {
                "command_id": 1,
                "stage_id": "DESIGN",
                "started_at": 1,
                "ended_at": "2",
            }
        ],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_validation_error_session_command_missing(db_connection) -> None:
    """Cover the FK-safety check for session->command existence."""

    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {"DESIGN": [{"id": 1, "title": "Ok", "status": "Not Started"}]},
        "sessions": [
            {
                "command_id": 999,
                "stage_id": "DESIGN",
                "started_at": 1,
                "ended_at": None,
            }
        ],
    }
    with pytest.raises(ValueError, match="Invalid snapshot payload"):
        service._apply_payload(payload)


def test_snapshot_apply_payload_inserts_ended_session_happy_path(db_connection) -> None:
    """Cover the session path where `ended_at` is not None (ended session)."""

    service = _service(db_connection)
    payload = {
        "schema_version": 3,
        "board_name": "Board",
        "saved_at": 1,
        "commands": {
            "DESIGN": [
                {"id": 1, "title": "Ok", "status": "Not Started"},
            ]
        },
        "sessions": [
            {
                "command_id": 1,
                "stage_id": "DESIGN",
                "started_at": 10,
                "ended_at": 20,
            }
        ],
    }
    service._apply_payload(payload)

    row = db_connection.execute(
        "SELECT command_id, stage_id, started_at, ended_at FROM sessions"
    ).fetchone()
    assert row is not None
    assert row["command_id"] == 1
    assert row["stage_id"] == "DESIGN"
    assert row["started_at"] == 10
    assert row["ended_at"] == 20

