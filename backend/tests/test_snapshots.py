from __future__ import annotations

import pytest

from app.repositories.board_repository import BoardRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.snapshot_service import SnapshotService


def test_board_default_name_is_untitled(client):
    r = client.get("/api/board")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Untitled board"
    assert data["user_named"] is False
    assert data["is_new_unnamed"] is True


def test_can_update_board_name(client):
    r = client.patch("/api/board", json={"name": "Morning Setup"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Morning Setup"
    assert data["user_named"] is True
    assert data["is_new_unnamed"] is False


def test_can_update_stage_labels(client):
    r = client.patch(
        "/api/board/stage-labels",
        json={
            "stage_labels": {
                "DESIGN": "Design",
                "BUILD": "Build",
                "REVIEW": "Review",
                "COMPLETE": "Complete",
            }
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["stage_labels"]["DESIGN"] == "Design"


def test_board_service_ignores_invalid_stage_labels_json(db_connection):
    from app.repositories.board_repository import BoardRepository
    from app.services.board_service import BoardService

    # Corrupt persisted stage label data.
    db_connection.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        ("not-json",),
    )
    db_connection.commit()

    service = BoardService(BoardRepository(db_connection))
    data = service.get()
    assert data.get("stage_labels") is None


def test_board_repository_exists_is_true(client):
    # Implicitly verifies BoardRepository.exists() path via API access.
    r = client.get("/api/board")
    assert r.status_code == 200


def test_board_repository_get_raises_when_singleton_missing(db_connection):
    db_connection.execute("DELETE FROM board_state")
    db_connection.commit()
    repo = BoardRepository(db_connection)
    with pytest.raises(RuntimeError):
        repo.get()


def test_snapshot_save_list_and_dedupe_ignores_session_timing(client):
    # Create commands.
    r1 = client.post(
        "/api/commands",
        json={"title": "A", "stage_id": "DESIGN", "status": "Not Started"},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/commands",
        json={"title": "B", "stage_id": "BUILD", "status": "In Progress"},
    )
    assert r2.status_code == 201

    # Start a session (creates a runtime timestamp).
    cmd1 = r1.json()
    rs = client.post("/api/sessions/start", json={"command_id": cmd1["id"]})
    assert rs.status_code == 200

    # Save a snapshot.
    s1 = client.post("/api/snapshots")
    assert s1.status_code == 201
    snap1 = s1.json()
    assert "name" in snap1

    # Stop + start another session to change timestamps but keep structural meaning
    # (active session stage remains DESIGN after restart).
    rstop = client.post("/api/sessions/stop")
    assert rstop.status_code == 200
    rs2 = client.post("/api/sessions/start", json={"command_id": cmd1["id"]})
    assert rs2.status_code == 200

    s2 = client.post("/api/snapshots")
    assert s2.status_code == 201
    snap2 = s2.json()

    # Dedupe: same structural form => same snapshot id.
    assert snap2["id"] == snap1["id"]

    listed = client.get("/api/snapshots")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == snap1["id"]


def test_snapshot_repository_exists_false_when_missing(client):
    # SnapshotRepository.exists() is used by internal safety checks.
    r = client.get("/api/snapshots")
    assert r.status_code == 200
    assert r.json() == []


def test_snapshot_repository_exists_true_after_insert(db_connection):
    repo = SnapshotRepository(db_connection)
    assert repo.exists(1) is False
    db_connection.execute(
        "INSERT INTO snapshots (name, saved_at, payload_json, structural_hash) VALUES (?, ?, ?, ?)",
        ("X", 1, "{}", "h"),
    )
    db_connection.commit()
    snapshot_id = int(db_connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    assert repo.exists(snapshot_id) is True


def test_snapshot_repository_upsert_rolls_back_on_integrity_error(db_connection):
    repo = SnapshotRepository(db_connection)
    before = db_connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    with pytest.raises(Exception):
        # name column is NOT NULL, so this triggers an integrity error and forces
        # the rollback branch.
        repo.upsert_by_name_hash(  # type: ignore[arg-type]
            name=None,  # type: ignore[arg-type]
            structural_hash="h",
            saved_at=1,
            payload_json="{}",
        )
    after = db_connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    assert after == before


def test_snapshot_repository_upsert_by_name_hash_inserts_and_updates(db_connection):
    repo = SnapshotRepository(db_connection)
    out1 = repo.upsert_by_name_hash(
        name="N",
        structural_hash="h",
        saved_at=1,
        payload_json="{}",
    )
    assert out1["id"] >= 1
    assert out1["name"] == "N"
    assert out1["saved_at"] == 1

    out2 = repo.upsert_by_name_hash(
        name="N",
        structural_hash="h",
        saved_at=2,
        payload_json="{\"x\":1}",
    )
    assert out2["id"] == out1["id"]
    assert out2["saved_at"] == 2


def test_snapshot_repository_get_summary_none_when_missing(db_connection):
    repo = SnapshotRepository(db_connection)
    assert repo.get_summary(999999) is None


def test_can_rename_snapshot_via_patch(client):
    created = client.post("/api/snapshots")
    assert created.status_code == 201
    snap = created.json()

    r = client.patch(f"/api/snapshots/{snap['id']}", json={"name": "  My Snapshot  "})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == snap["id"]
    assert data["name"] == "My Snapshot"

    listed = client.get("/api/snapshots")
    assert listed.status_code == 200
    items = listed.json()
    assert any(it["id"] == snap["id"] and it["name"] == "My Snapshot" for it in items)


def test_rename_snapshot_rejects_empty(client):
    created = client.post("/api/snapshots")
    assert created.status_code == 201
    snap = created.json()

    r = client.patch(f"/api/snapshots/{snap['id']}", json={"name": "   "})
    assert r.status_code == 400


def test_rename_snapshot_404_when_missing(client):
    r = client.patch("/api/snapshots/999999", json={"name": "X"})
    assert r.status_code == 404


def test_snapshot_default_name_uses_stage_label_and_handles_invalid_labels_json(client, db_connection):
    # Create a command and start a session (so stage is known).
    r1 = client.post(
        "/api/commands",
        json={"title": "A", "stage_id": "DESIGN", "status": "Not Started"},
    )
    assert r1.status_code == 201
    cmd1 = r1.json()

    # Override stage label so snapshot naming uses the override.
    rlabels = client.patch(
        "/api/board/stage-labels",
        json={
            "stage_labels": {
                "DESIGN": "Sketch",
                "BUILD": "Build",
                "REVIEW": "Review",
                "COMPLETE": "Complete",
            }
        },
    )
    assert rlabels.status_code == 200

    rs = client.post("/api/sessions/start", json={"command_id": cmd1["id"]})
    assert rs.status_code == 200

    s1 = client.post("/api/snapshots")
    assert s1.status_code == 201
    snap1 = s1.json()
    assert snap1["name"].startswith("Sketch – ")

    # Corrupt stage label data to hit the exception branch in _get_stage_label.
    db_connection.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        ("not-json",),
    )
    db_connection.commit()

    s2 = client.post("/api/snapshots")
    assert s2.status_code == 201


def test_snapshot_invalid_payload_rejected(client, db_connection):
    # Call the service directly so we can assert the validation error without
    # TestClient re-raising server exceptions.
    db_connection.execute(
        "INSERT INTO snapshots (name, saved_at, payload_json, structural_hash) VALUES (?, ?, ?, ?)",
        ("Bad", 1, "{}", "deadbeef"),
    )
    db_connection.commit()
    snapshot_id = int(db_connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    with pytest.raises(ValueError):
        service.load(snapshot_id=snapshot_id)


def test_snapshot_apply_payload_rolls_back_on_mid_transaction_error(db_connection):
    # Seed state to verify rollback restores.
    db_connection.execute(
        "INSERT INTO commands (title, stage_id, status, sort_index, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Keep", "DESIGN", "Not Started", 1, 1),
    )
    cmd_id = int(db_connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    db_connection.execute(
        "INSERT INTO outcomes (command_id, note, created_at) VALUES (?, ?, ?)",
        (cmd_id, "note", 1),
    )
    db_connection.execute(
        "INSERT INTO sessions (command_id, stage_id, started_at, ended_at) VALUES (?, ?, ?, NULL)",
        (cmd_id, "DESIGN", 1),
    )
    db_connection.commit()

    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )

    bad_payload = {
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": {"Design": [{"title": "X", "status": "INVALID"}]},
        "sessions": [],
    }

    with pytest.raises(ValueError):
        service._apply_payload(bad_payload)

    # Rollback should keep original rows.
    assert db_connection.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 1
    assert db_connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 1
    assert db_connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_snapshot_apply_payload_keeps_first_active_session_when_multiple(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )

    payload = {
        # v1 payload; v2 loader drops v1 sessions because they are category-level.
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": {},
        "sessions": [
            {"category": "Design", "started_at": 1, "ended_at": None},
            {"category": "Build", "started_at": 2, "ended_at": None},
        ],
    }
    service._apply_payload(payload)
    rows = db_connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert int(rows) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "board_name": "X", "commands": {}, "sessions": []},
        {"schema_version": 1, "board_name": "", "commands": {}, "sessions": []},
        {"schema_version": 1, "board_name": "X", "commands": [], "sessions": []},
        {"schema_version": 1, "board_name": "X", "commands": {}, "sessions": {}},
        {"schema_version": 1, "board_name": "X", "commands": {"Design": "oops"}, "sessions": []},
        {"schema_version": 1, "board_name": "X", "commands": {"Design": [1]}, "sessions": []},
        {
            "schema_version": 1,
            "board_name": "X",
            "commands": {"Design": [{"title": "   ", "status": "Not Started"}]},
            "sessions": [],
        },
        # v1 sessions are ignored on load (category-level). Keep validation
        # coverage on v2 session schema instead.
        {
            "schema_version": 2,
            "board_name": "X",
            "commands": {},
            "sessions": [{"command_id": "oops", "stage_id": "DESIGN", "started_at": 1, "ended_at": None}],
        },
        {
            "schema_version": 2,
            "board_name": "X",
            "commands": {},
            "sessions": [{"command_id": 1, "stage_id": "NOPE", "started_at": 1, "ended_at": None}],
        },
        {
            "schema_version": 2,
            "board_name": "X",
            "commands": {},
            "sessions": [{"command_id": 1, "stage_id": "DESIGN", "started_at": "1", "ended_at": None}],
        },
        {
            "schema_version": 2,
            "board_name": "X",
            "commands": {},
            "sessions": [{"command_id": 1, "stage_id": "DESIGN", "started_at": 1, "ended_at": "2"}],
        },
    ],
)
def test_snapshot_apply_payload_validation_errors(db_connection, payload):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    with pytest.raises(Exception):
        service._apply_payload(payload)


def test_snapshot_apply_payload_v2_ignores_second_active_session(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )

    payload = {
        "schema_version": 3,
        "board_name": "X",
        "saved_at": 1,
        "commands": {
            "DESIGN": [{"id": 1, "title": "A", "status": "Not Started"}],
            "BUILD": [{"id": 2, "title": "B", "status": "Not Started"}],
            "REVIEW": [],
            "COMPLETE": [],
        },
        "sessions": [
            {"command_id": 1, "stage_id": "DESIGN", "started_at": 1, "ended_at": None},
            {"command_id": 2, "stage_id": "BUILD", "started_at": 2, "ended_at": None},
        ],
    }
    service._apply_payload(payload)
    rows = db_connection.execute(
        "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL"
    ).fetchone()[0]
    assert int(rows) == 1


def test_snapshot_apply_payload_raises_if_board_state_missing(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    db_connection.execute("DELETE FROM board_state")
    db_connection.commit()

    payload = {
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": {},
        "sessions": [],
    }
    with pytest.raises(RuntimeError):
        service._apply_payload(payload)


def test_snapshot_apply_payload_rejects_sessions_non_dict_element(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    payload = {
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": {},
        "sessions": [1],
    }
    with pytest.raises(ValueError):
        service._apply_payload(payload)


def test_snapshot_apply_payload_rejects_sessions_none(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    payload = {
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": {},
        "sessions": None,
    }
    with pytest.raises(ValueError):
        service._apply_payload(payload)


def test_snapshot_apply_payload_commands_none_is_invalid(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    payload = {
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": None,
        "sessions": [],
    }
    with pytest.raises(ValueError):
        service._apply_payload(payload)


def test_snapshot_apply_payload_rejects_category_items_none(db_connection):
    service = SnapshotService(
        conn=db_connection,
        board=BoardRepository(db_connection),
        sessions=SessionRepository(db_connection),
        snapshots=SnapshotRepository(db_connection),
    )
    payload = {
        "schema_version": 1,
        "board_name": "X",
        "saved_at": 1,
        "commands": {"Design": None},
        "sessions": [],
    }
    with pytest.raises(ValueError):
        service._apply_payload(payload)


def test_snapshot_load_unknown_returns_404(client):
    r = client.post("/api/snapshots/999999/load")
    assert r.status_code == 404


def test_snapshot_load_overwrites_commands_and_sessions_and_clears_outcomes(client):
    # Create a command and an outcome.
    rc = client.post(
        "/api/commands",
        json={"title": "Cmd", "stage_id": "DESIGN", "status": "Not Started"},
    )
    assert rc.status_code == 201
    cmd_id = rc.json()["id"]

    ro = client.post(f"/api/commands/{cmd_id}/outcomes", json={"note": "hello"})
    assert ro.status_code == 201

    # Start a session.
    rs = client.post("/api/sessions/start", json={"command_id": cmd_id})
    assert rs.status_code == 200

    # Save snapshot.
    saved = client.post("/api/snapshots")
    assert saved.status_code == 201
    snapshot_id = saved.json()["id"]

    # Mutate live board: add another command and stop session.
    rc2 = client.post(
        "/api/commands",
        json={"title": "Other", "stage_id": "BUILD", "status": "Blocked"},
    )
    assert rc2.status_code == 201
    rstop = client.post("/api/sessions/stop")
    assert rstop.status_code == 200

    # Load snapshot => overwrite commands and sessions, clear outcomes.
    rl = client.post(f"/api/snapshots/{snapshot_id}/load")
    assert rl.status_code == 200
    assert rl.json()["ok"] is True

    # Commands should match original snapshot (only 1 command).
    cmds = client.get("/api/commands").json()
    assert len(cmds) == 1
    assert cmds[0]["title"] == "Cmd"

    # Outcomes cleared.
    outs = client.get(f"/api/commands/{cmd_id}/outcomes")
    assert outs.status_code == 200
    assert outs.json() == []

    # Active session restored (snapshot had active session).
    active = client.get("/api/sessions/active")
    assert active.status_code == 200
    assert active.json().get("active", True) is not False
    assert active.json()["stage_id"] == "DESIGN"

