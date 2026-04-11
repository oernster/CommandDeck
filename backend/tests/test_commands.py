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
