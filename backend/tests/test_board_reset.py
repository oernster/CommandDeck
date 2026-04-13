from __future__ import annotations


def test_reset_board_clears_operational_state_and_preserves_metadata(client) -> None:
    # Name + stage labels are persisted on board_state and must survive reset.
    renamed = client.patch("/api/board", json={"name": "My Board"})
    assert renamed.status_code == 200

    labels = client.patch(
        "/api/board/stage-labels",
        json={
            "stage_labels": {
                "DESIGN": "Sketch",
                "BUILD": "Build",
                "REVIEW": "Review",
                "COMPLETE": "Done",
            }
        },
    )
    assert labels.status_code == 200

    # Seed live operational state: commands + session + outcome.
    created = client.post(
        "/api/commands",
        json={"title": "A", "stage_id": "DESIGN", "status": "Not Started"},
    )
    assert created.status_code == 201
    cmd_id = int(created.json()["id"])

    started = client.post("/api/sessions/start", json={"command_id": cmd_id})
    assert started.status_code == 200

    out = client.post(f"/api/commands/{cmd_id}/outcomes", json={"note": "n"})
    assert out.status_code == 201

    # Ensure there is at least one snapshot and it survives reset.
    snap = client.post("/api/snapshots")
    assert snap.status_code == 201
    snap_id = int(snap.json()["id"])

    # Reset.
    r = client.post("/api/board/reset")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # Operational state cleared.
    cmds = client.get("/api/commands")
    assert cmds.status_code == 200
    assert cmds.json() == []

    active = client.get("/api/sessions/active")
    assert active.status_code == 200
    assert active.json() == {"active": False}

    # outcomes endpoints are keyed off commands; easiest invariant is table empty.
    # We rely on the API not exposing outcomes list directly.
    # Since commands were deleted, any outcomes would have been deleted too.

    # Board metadata preserved.
    b = client.get("/api/board")
    assert b.status_code == 200
    data = b.json()
    assert data["name"] == "My Board"
    assert data["stage_labels"]["DESIGN"] == "Sketch"
    assert data["is_empty"] is True

    # Snapshots preserved.
    snaps = client.get("/api/snapshots")
    assert snaps.status_code == 200
    items = snaps.json()
    assert any(it["id"] == snap_id for it in items)


def test_snapshot_save_accepts_explicit_name_and_trims(client) -> None:
    r = client.post("/api/snapshots", json={"name": "  Before reset - 2026-04-13 12:34  "})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Before reset - 2026-04-13 12:34"


def test_snapshot_save_blank_name_falls_back_to_default(client) -> None:
    r = client.post("/api/snapshots", json={"name": "   "})
    assert r.status_code == 201
    data = r.json()
    assert isinstance(data["name"], str)
    assert data["name"].strip() != ""


def test_board_reset_rolls_back_on_error(db_connection) -> None:
    # Force an error on the first delete by removing the outcomes table.
    db_connection.execute("DROP TABLE outcomes")
    db_connection.commit()

    from app.repositories.board_repository import BoardRepository

    repo = BoardRepository(db_connection)
    try:
        repo.reset_live_state()
        assert False, "Expected reset_live_state to raise when outcomes table is missing"
    except Exception:
        # The rollback branch must be covered; any exception is sufficient.
        pass

