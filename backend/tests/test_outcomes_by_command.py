from __future__ import annotations


def test_outcomes_by_command_empty_payload(client) -> None:
    resp = client.post("/api/outcomes/by-command", json={"command_ids": []})
    assert resp.status_code == 200
    assert resp.json() == {"by_command_id": {}}


def test_outcomes_by_command_includes_all_requested_command_ids(client) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "c1", "stage_id": "DESIGN"},
    ).json()
    c2 = client.post(
        "/api/commands",
        json={"title": "c2", "stage_id": "DESIGN"},
    ).json()

    # Create multiple outcomes for c1, none for c2.
    r1 = client.post(f"/api/commands/{c1['id']}/outcomes", json={"note": "first"})
    assert r1.status_code == 201
    r2 = client.post(f"/api/commands/{c1['id']}/outcomes", json={"note": "second"})
    assert r2.status_code == 201

    resp = client.post(
        "/api/outcomes/by-command",
        json={"command_ids": [c1["id"], c2["id"]]},
    )
    assert resp.status_code == 200
    body = resp.json()

    # JSON object keys are strings.
    assert set(body["by_command_id"].keys()) == {str(c1["id"]), str(c2["id"])}
    assert [o["note"] for o in body["by_command_id"][str(c1["id"])]][:2] == [
        "second",
        "first",
    ]
    assert body["by_command_id"][str(c2["id"])] == []


def test_outcomes_by_command_ignores_missing_commands_but_includes_key(client) -> None:
    resp = client.post("/api/outcomes/by-command", json={"command_ids": [999]})
    assert resp.status_code == 200
    assert resp.json() == {"by_command_id": {"999": []}}

