from __future__ import annotations


def test_outcomes_list_requires_command(client) -> None:
    resp = client.get("/api/commands/999/outcomes")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Command not found"}


def test_create_and_list_outcomes(client) -> None:
    cmd = client.post(
        "/api/commands",
        json={"title": "With outcomes", "stage_id": "DESIGN"},
    ).json()

    created = client.post(
        f"/api/commands/{cmd['id']}/outcomes",
        json={"note": "Did the thing"},
    )
    assert created.status_code == 201
    outcome = created.json()
    assert outcome["id"] == 1
    assert outcome["command_id"] == cmd["id"]
    assert outcome["note"] == "Did the thing"
    assert outcome["created_at"].endswith("Z")

    listed = client.get(f"/api/commands/{cmd['id']}/outcomes")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == outcome["id"]


def test_create_outcome_validation(client) -> None:
    cmd = client.post(
        "/api/commands",
        json={"title": "X", "stage_id": "BUILD"},
    ).json()

    empty_note = client.post(
        f"/api/commands/{cmd['id']}/outcomes",
        json={"note": "   "},
    )
    assert empty_note.status_code == 400
    assert empty_note.json() == {"error": "Note must not be empty"}

    missing_field = client.post(
        f"/api/commands/{cmd['id']}/outcomes",
        json={},
    )
    assert missing_field.status_code == 400
    assert missing_field.json() == {"error": "Invalid request"}


def test_delete_outcome(client) -> None:
    cmd = client.post(
        "/api/commands",
        json={"title": "X", "stage_id": "REVIEW"},
    ).json()
    out = client.post(
        f"/api/commands/{cmd['id']}/outcomes",
        json={"note": "n"},
    ).json()

    deleted = client.delete(f"/api/outcomes/{out['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    missing = client.delete(f"/api/outcomes/{out['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"error": "Outcome not found"}


def test_command_delete_cascades_outcomes(client) -> None:
    cmd = client.post(
        "/api/commands",
        json={"title": "Cascade", "stage_id": "COMPLETE"},
    ).json()
    out = client.post(
        f"/api/commands/{cmd['id']}/outcomes",
        json={"note": "child"},
    ).json()

    deleted = client.delete(f"/api/commands/{cmd['id']}")
    assert deleted.status_code == 200

    # Outcome should be gone due to FK cascade.
    missing = client.delete(f"/api/outcomes/{out['id']}")
    assert missing.status_code == 404


def test_create_outcome_for_missing_command_returns_404(client) -> None:
    resp = client.post("/api/commands/999/outcomes", json={"note": "x"})
    assert resp.status_code == 404
    assert resp.json() == {"error": "Command not found"}
