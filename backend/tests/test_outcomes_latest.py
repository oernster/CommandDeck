from __future__ import annotations


def test_outcomes_latest_empty_payload(client) -> None:
    resp = client.post("/api/outcomes/latest", json={"command_ids": []})
    assert resp.status_code == 200
    assert resp.json() == {"by_command_id": {}, "counts_by_command_id": {}}


def test_outcomes_latest_returns_latest_per_command(client) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "c1", "stage_id": "DESIGN"},
    ).json()
    c2 = client.post(
        "/api/commands",
        json={"title": "c2", "stage_id": "DESIGN"},
    ).json()

    # For c1, create 2 outcomes; latest should win.
    r1 = client.post(f"/api/commands/{c1['id']}/outcomes", json={"note": "first"})
    assert r1.status_code == 201
    r2 = client.post(f"/api/commands/{c1['id']}/outcomes", json={"note": "second"})
    assert r2.status_code == 201

    # For c2, create 1 outcome.
    r3 = client.post(f"/api/commands/{c2['id']}/outcomes", json={"note": "only"})
    assert r3.status_code == 201

    latest = client.post(
        "/api/outcomes/latest",
        json={"command_ids": [c1["id"], c2["id"]]},
    )
    assert latest.status_code == 200
    body = latest.json()

    # JSON object keys are strings.
    assert set(body["by_command_id"].keys()) == {str(c1["id"]), str(c2["id"])}
    assert body["by_command_id"][str(c1["id"])]["note"] == "second"
    assert body["by_command_id"][str(c2["id"])]["note"] == "only"

    assert body["counts_by_command_id"][str(c1["id"])] == 2
    assert body["counts_by_command_id"][str(c2["id"])] == 1


def test_outcomes_latest_ignores_missing_commands(client) -> None:
    resp = client.post("/api/outcomes/latest", json={"command_ids": [999]})
    assert resp.status_code == 200
    assert resp.json() == {"by_command_id": {}, "counts_by_command_id": {}}

