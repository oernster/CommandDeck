from __future__ import annotations

import sqlite3


def test_create_and_list_commands(client) -> None:
    create = client.post(
        "/api/commands",
        json={"title": "Draft architecture", "stage_id": "DESIGN"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["id"] == 1
    assert body["title"] == "Draft architecture"
    assert body["stage_id"] == "DESIGN"
    assert body["status"] == "Not Started"
    assert body["created_at"].endswith("Z")

    listed = client.get("/api/commands")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == 1


def test_get_command_404(client) -> None:
    resp = client.get("/api/commands/999")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Command not found"}


def test_update_command_and_filtering(client) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "Cmd1", "stage_id": "DESIGN", "status": "Not Started"},
    ).json()
    c2 = client.post(
        "/api/commands",
        json={"title": "Cmd2", "stage_id": "BUILD", "status": "Blocked"},
    ).json()

    upd = client.patch(
        f"/api/commands/{c1['id']}",
        json={"status": "In Progress"},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "In Progress"

    only_design = client.get("/api/commands?stage_id=DESIGN")
    assert only_design.status_code == 200
    assert [c["id"] for c in only_design.json()] == [c1["id"]]

    only_blocked = client.get("/api/commands?status=Blocked")
    assert only_blocked.status_code == 200
    assert [c["id"] for c in only_blocked.json()] == [c2["id"]]

    both = client.get("/api/commands?stage_id=BUILD&status=Blocked")
    assert both.status_code == 200
    assert [c["id"] for c in both.json()] == [c2["id"]]


def test_update_stage_id_valid_value_exercises_branch(client) -> None:
    created = client.post(
        "/api/commands",
        json={"title": "Move", "stage_id": "DESIGN"},
    ).json()

    upd = client.patch(
        f"/api/commands/{created['id']}",
        json={"stage_id": "BUILD"},
    )
    assert upd.status_code == 200
    assert upd.json()["stage_id"] == "BUILD"


def test_delete_command(client, db_connection: sqlite3.Connection) -> None:
    created = client.post(
        "/api/commands",
        json={"title": "Delete me", "stage_id": "COMPLETE"},
    ).json()

    # Create related data that must be hard-deleted (no ghost rows).
    out = client.post(
        f"/api/commands/{created['id']}/outcomes",
        json={"note": "First note"},
    )
    assert out.status_code == 201

    sess = client.post(
        "/api/sessions/start",
        json={"command_id": created["id"]},
    )
    assert sess.status_code == 200

    deleted = client.delete(f"/api/commands/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    missing = client.get(f"/api/commands/{created['id']}")
    assert missing.status_code == 404

    # Hard delete (no ghost rows): outcomes + sessions must be removed.
    outcomes_count = int(
        db_connection.execute(
            "SELECT COUNT(*) FROM outcomes WHERE command_id = ?",
            (created["id"],),
        ).fetchone()[0]
    )
    assert outcomes_count == 0

    sessions_count = int(
        db_connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE command_id = ?",
            (created["id"],),
        ).fetchone()[0]
    )
    assert sessions_count == 0

    # API behavior: the outcomes list endpoint should return 404 (not an empty
    # list), because the command no longer exists.
    outcomes_after = client.get(f"/api/commands/{created['id']}/outcomes")
    assert outcomes_after.status_code == 404
    assert outcomes_after.json() == {"error": "Command not found"}

    # Cascading delete: any sessions that referenced the command should be gone.
    # The API should report no active session.
    active = client.get("/api/sessions/active")
    assert active.status_code == 200
    assert active.json() == {"active": False}


def test_validation_errors_are_400_with_simple_shape(client) -> None:
    bad_category = client.post(
        "/api/commands",
        json={"title": "X", "stage_id": "Nope"},
    )
    assert bad_category.status_code == 400
    assert bad_category.json() == {"error": "Invalid stage_id"}

    bad_status = client.post(
        "/api/commands",
        json={"title": "X", "stage_id": "DESIGN", "status": "Nope"},
    )
    assert bad_status.status_code == 400
    assert bad_status.json() == {"error": "Invalid status"}

    empty_title = client.post(
        "/api/commands",
        json={"title": "   ", "stage_id": "DESIGN"},
    )
    assert empty_title.status_code == 400
    assert empty_title.json() == {"error": "Title must not be empty"}

    invalid_query = client.get("/api/commands?stage_id=Nope")
    assert invalid_query.status_code == 400
    assert invalid_query.json() == {"error": "Invalid stage_id"}

    invalid_status_query = client.get("/api/commands?status=Nope")
    assert invalid_status_query.status_code == 400
    assert invalid_status_query.json() == {"error": "Invalid status"}

    created = client.post(
        "/api/commands",
        json={"title": "Cmd", "stage_id": "DESIGN"},
    ).json()

    bad_update_stage_id = client.patch(
        f"/api/commands/{created['id']}",
        json={"stage_id": "Nope"},
    )
    assert bad_update_stage_id.status_code == 400
    assert bad_update_stage_id.json() == {"error": "Invalid stage_id"}

    bad_update_status = client.patch(
        f"/api/commands/{created['id']}",
        json={"status": "Nope"},
    )
    assert bad_update_status.status_code == 400
    assert bad_update_status.json() == {"error": "Invalid status"}

    empty_title_update = client.patch(
        f"/api/commands/{created['id']}",
        json={"title": "   "},
    )
    assert empty_title_update.status_code == 400
    assert empty_title_update.json() == {"error": "Title must not be empty"}


def test_update_command_404(client) -> None:
    resp = client.patch("/api/commands/999", json={"status": "Complete"})
    assert resp.status_code == 404
    assert resp.json() == {"error": "Command not found"}


def test_delete_command_404(client) -> None:
    resp = client.delete("/api/commands/999")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Command not found"}


def test_get_command_success(client) -> None:
    created = client.post(
        "/api/commands",
        json={"title": "Get me", "stage_id": "COMPLETE"},
    ).json()

    fetched = client.get(f"/api/commands/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_fastapi_request_validation_errors_are_mapped_to_400(client) -> None:
    # Missing required field `stage_id` should trigger FastAPI validation.
    resp = client.post("/api/commands", json={"title": "X"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid request"}


def test_reorder_commands_persists_ordering_within_and_across_stages(
    client,
) -> None:
    d1 = client.post("/api/commands", json={"title": "D1", "stage_id": "DESIGN"}).json()
    d2 = client.post("/api/commands", json={"title": "D2", "stage_id": "DESIGN"}).json()
    b1 = client.post("/api/commands", json={"title": "B1", "stage_id": "BUILD"}).json()

    # Initial order: append-to-bottom; list endpoint should return in that order.
    items = client.get("/api/commands?stage_id=DESIGN").json()
    assert [c["id"] for c in items] == [d1["id"], d2["id"]]

    # Move d2 above d1 (within stage) and move b1 into DESIGN at the end.
    reorder = client.post(
        "/api/commands/reorder",
        json={
            "by_stage_id": {
                "DESIGN": [d2["id"], d1["id"], b1["id"]],
                "BUILD": [],
            }
        },
    )
    assert reorder.status_code == 200
    assert reorder.json() == {"ok": True}

    # Persisted order should be reflected on list.
    items2 = client.get("/api/commands?stage_id=DESIGN").json()
    assert [c["id"] for c in items2] == [d2["id"], d1["id"], b1["id"]]
    items3 = client.get("/api/commands?stage_id=BUILD").json()
    assert items3 == []


def test_reorder_commands_invalid_stage_id_is_400(client) -> None:
    resp = client.post("/api/commands/reorder", json={"by_stage_id": {"Nope": []}})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid stage_id"}


def test_reorder_commands_requires_full_coverage(client) -> None:
    d1 = client.post("/api/commands", json={"title": "D1", "stage_id": "DESIGN"}).json()
    client.post("/api/commands", json={"title": "D2", "stage_id": "DESIGN"}).json()

    # Missing one id should fail.
    resp = client.post(
        "/api/commands/reorder",
        json={"by_stage_id": {"DESIGN": [d1["id"]]}},
    )
    assert resp.status_code == 400


def test_reorder_commands_duplicate_ids_is_400(client) -> None:
    d1 = client.post("/api/commands", json={"title": "D1", "stage_id": "DESIGN"}).json()
    resp = client.post(
        "/api/commands/reorder",
        json={"by_stage_id": {"DESIGN": [d1["id"], d1["id"]]}},
    )
    assert resp.status_code == 400


def test_reorder_commands_empty_payload_is_ok(client) -> None:
    resp = client.post("/api/commands/reorder", json={"by_stage_id": {}})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_list_commands_is_ordered_within_stage(client) -> None:
    # BUILD will come before DESIGN due to stage_id ordering in SQL, but we mainly
    # assert the within-stage order is stable and respects sort_index.
    d1 = client.post("/api/commands", json={"title": "D1", "stage_id": "DESIGN"}).json()
    d2 = client.post("/api/commands", json={"title": "D2", "stage_id": "DESIGN"}).json()
    b1 = client.post("/api/commands", json={"title": "B1", "stage_id": "BUILD"}).json()

    # Reorder within Design.
    ok = client.post(
        "/api/commands/reorder",
        json={"by_stage_id": {"DESIGN": [d2["id"], d1["id"]]}},
    )
    assert ok.status_code == 200

    items = client.get("/api/commands").json()
    design = [c for c in items if c["stage_id"] == "DESIGN"]
    assert [c["id"] for c in design] == [d2["id"], d1["id"]]

    build = [c for c in items if c["stage_id"] == "BUILD"]
    assert [c["id"] for c in build] == [b1["id"]]
