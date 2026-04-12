from __future__ import annotations


def test_create_and_list_commands(client) -> None:
    create = client.post(
        "/api/commands",
        json={"title": "Draft architecture", "category": "Design"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["id"] == 1
    assert body["title"] == "Draft architecture"
    assert body["category"] == "Design"
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
        json={"title": "Cmd1", "category": "Design", "status": "Not Started"},
    ).json()
    c2 = client.post(
        "/api/commands",
        json={"title": "Cmd2", "category": "Build", "status": "Blocked"},
    ).json()

    upd = client.patch(
        f"/api/commands/{c1['id']}",
        json={"status": "In Progress"},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "In Progress"

    only_design = client.get("/api/commands?category=Design")
    assert only_design.status_code == 200
    assert [c["id"] for c in only_design.json()] == [c1["id"]]

    only_blocked = client.get("/api/commands?status=Blocked")
    assert only_blocked.status_code == 200
    assert [c["id"] for c in only_blocked.json()] == [c2["id"]]

    both = client.get("/api/commands?category=Build&status=Blocked")
    assert both.status_code == 200
    assert [c["id"] for c in both.json()] == [c2["id"]]


def test_update_category_valid_value_exercises_branch(client) -> None:
    created = client.post(
        "/api/commands",
        json={"title": "Move", "category": "Design"},
    ).json()

    upd = client.patch(
        f"/api/commands/{created['id']}",
        json={"category": "Build"},
    )
    assert upd.status_code == 200
    assert upd.json()["category"] == "Build"


def test_delete_command(client) -> None:
    created = client.post(
        "/api/commands",
        json={"title": "Delete me", "category": "Recover"},
    ).json()

    deleted = client.delete(f"/api/commands/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    missing = client.get(f"/api/commands/{created['id']}")
    assert missing.status_code == 404


def test_validation_errors_are_400_with_simple_shape(client) -> None:
    bad_category = client.post(
        "/api/commands",
        json={"title": "X", "category": "Nope"},
    )
    assert bad_category.status_code == 400
    assert bad_category.json() == {"error": "Invalid category"}

    bad_status = client.post(
        "/api/commands",
        json={"title": "X", "category": "Design", "status": "Nope"},
    )
    assert bad_status.status_code == 400
    assert bad_status.json() == {"error": "Invalid status"}

    empty_title = client.post(
        "/api/commands",
        json={"title": "   ", "category": "Design"},
    )
    assert empty_title.status_code == 400
    assert empty_title.json() == {"error": "Title must not be empty"}

    invalid_query = client.get("/api/commands?category=Nope")
    assert invalid_query.status_code == 400
    assert invalid_query.json() == {"error": "Invalid category"}

    invalid_status_query = client.get("/api/commands?status=Nope")
    assert invalid_status_query.status_code == 400
    assert invalid_status_query.json() == {"error": "Invalid status"}

    created = client.post(
        "/api/commands",
        json={"title": "Cmd", "category": "Design"},
    ).json()

    bad_update_category = client.patch(
        f"/api/commands/{created['id']}",
        json={"category": "Nope"},
    )
    assert bad_update_category.status_code == 400
    assert bad_update_category.json() == {"error": "Invalid category"}

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
        json={"title": "Get me", "category": "Maintain"},
    ).json()

    fetched = client.get(f"/api/commands/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_fastapi_request_validation_errors_are_mapped_to_400(client) -> None:
    # Missing required field `category` should trigger FastAPI validation.
    resp = client.post("/api/commands", json={"title": "X"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid request"}


def test_reorder_commands_persists_ordering_within_and_across_categories(
    client,
) -> None:
    d1 = client.post("/api/commands", json={"title": "D1", "category": "Design"}).json()
    d2 = client.post("/api/commands", json={"title": "D2", "category": "Design"}).json()
    b1 = client.post("/api/commands", json={"title": "B1", "category": "Build"}).json()

    # Initial order: append-to-bottom; list endpoint should return in that order.
    items = client.get("/api/commands?category=Design").json()
    assert [c["id"] for c in items] == [d1["id"], d2["id"]]

    # Move d2 above d1 (within category) and move b1 into Design at the end.
    reorder = client.post(
        "/api/commands/reorder",
        json={
            "by_category": {
                "Design": [d2["id"], d1["id"], b1["id"]],
                "Build": [],
            }
        },
    )
    assert reorder.status_code == 200
    assert reorder.json() == {"ok": True}

    # Persisted order should be reflected on list.
    items2 = client.get("/api/commands?category=Design").json()
    assert [c["id"] for c in items2] == [d2["id"], d1["id"], b1["id"]]
    items3 = client.get("/api/commands?category=Build").json()
    assert items3 == []


def test_reorder_commands_invalid_category_is_400(client) -> None:
    resp = client.post("/api/commands/reorder", json={"by_category": {"Nope": []}})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid category"}


def test_reorder_commands_requires_full_coverage(client) -> None:
    d1 = client.post("/api/commands", json={"title": "D1", "category": "Design"}).json()
    client.post("/api/commands", json={"title": "D2", "category": "Design"}).json()

    # Missing one id should fail.
    resp = client.post(
        "/api/commands/reorder",
        json={"by_category": {"Design": [d1["id"]]}},
    )
    assert resp.status_code == 400


def test_reorder_commands_duplicate_ids_is_400(client) -> None:
    d1 = client.post("/api/commands", json={"title": "D1", "category": "Design"}).json()
    resp = client.post(
        "/api/commands/reorder",
        json={"by_category": {"Design": [d1["id"], d1["id"]]}},
    )
    assert resp.status_code == 400


def test_reorder_commands_empty_payload_is_ok(client) -> None:
    resp = client.post("/api/commands/reorder", json={"by_category": {}})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_list_commands_is_ordered_within_category(client) -> None:
    # Build will come before Design due to category ordering in SQL, but we
    # mainly assert the within-category order is stable and respects sort_index.
    d1 = client.post("/api/commands", json={"title": "D1", "category": "Design"}).json()
    d2 = client.post("/api/commands", json={"title": "D2", "category": "Design"}).json()
    b1 = client.post("/api/commands", json={"title": "B1", "category": "Build"}).json()

    # Reorder within Design.
    ok = client.post(
        "/api/commands/reorder",
        json={"by_category": {"Design": [d2["id"], d1["id"]]}},
    )
    assert ok.status_code == 200

    items = client.get("/api/commands").json()
    design = [c for c in items if c["category"] == "Design"]
    assert [c["id"] for c in design] == [d2["id"], d1["id"]]

    build = [c for c in items if c["category"] == "Build"]
    assert [c["id"] for c in build] == [b1["id"]]
