from __future__ import annotations


def test_active_session_none(client) -> None:
    resp = client.get("/api/sessions/active")
    assert resp.status_code == 200
    assert resp.json() == {"active": False}


def test_stop_session_when_none_active(client) -> None:
    resp = client.post("/api/sessions/stop")
    assert resp.status_code == 200
    assert resp.json() == {"active": False}


def test_start_session_invalid_command_id(client) -> None:
    resp = client.post("/api/sessions/start", json={"command_id": 999})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid command_id"}


def test_start_and_stop_session_flow(client) -> None:
    # Create a task.
    created = client.post(
        "/api/commands",
        json={"title": "T1", "stage_id": "BUILD", "status": "Not Started"},
    )
    assert created.status_code == 201
    cmd = created.json()

    started = client.post("/api/sessions/start", json={"command_id": cmd["id"]})
    assert started.status_code == 200
    body = started.json()
    assert body["id"] == 1
    assert body["command_id"] == cmd["id"]
    assert body["stage_id"] == "BUILD"
    assert body["ended_at"] is None
    assert body["started_at"].endswith("Z")

    active = client.get("/api/sessions/active")
    assert active.status_code == 200
    assert active.json()["id"] == 1

    stopped = client.post("/api/sessions/stop")
    assert stopped.status_code == 200
    stopped_body = stopped.json()
    assert stopped_body["id"] == 1
    assert stopped_body["ended_at"].endswith("Z")


def test_start_new_session_ends_previous(client) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "A", "stage_id": "DESIGN", "status": "Not Started"},
    ).json()
    c2 = client.post(
        "/api/commands",
        json={"title": "B", "stage_id": "REVIEW", "status": "Not Started"},
    ).json()

    s1 = client.post("/api/sessions/start", json={"command_id": c1["id"]}).json()
    assert s1["ended_at"] is None

    s2 = client.post("/api/sessions/start", json={"command_id": c2["id"]}).json()
    assert s2["id"] == 2
    assert s2["command_id"] == c2["id"]
    assert s2["stage_id"] == "REVIEW"
    assert s2["ended_at"] is None

    # Previous session should now be ended.
    all_sessions = client.get("/api/sessions").json()
    by_id = {s["id"]: s for s in all_sessions}
    assert by_id[1]["ended_at"] is not None
    assert by_id[2]["ended_at"] is None


def test_list_sessions_filters(client) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "M", "stage_id": "COMPLETE", "status": "Not Started"},
    ).json()
    client.post("/api/sessions/start", json={"command_id": c1["id"]})
    client.post("/api/sessions/stop")
    client.post("/api/sessions/start", json={"command_id": c1["id"]})

    only_complete = client.get("/api/sessions?stage_id=COMPLETE")
    assert only_complete.status_code == 200
    assert all(s["stage_id"] == "COMPLETE" for s in only_complete.json())

    active_only = client.get("/api/sessions?active=true")
    assert active_only.status_code == 200
    assert all(s["ended_at"] is None for s in active_only.json())

    inactive_only = client.get("/api/sessions?active=false")
    assert inactive_only.status_code == 200
    assert all(s["ended_at"] is not None for s in inactive_only.json())


def test_list_sessions_invalid_stage_id_query(client) -> None:
    resp = client.get("/api/sessions?stage_id=Nope")
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid stage_id"}


def test_start_missing_body_is_400_invalid_request(client) -> None:
    resp = client.post("/api/sessions/start", json={})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid request"}


def test_latest_by_stage_id_empty(client) -> None:
    resp = client.get("/api/sessions/latest-by-stage-id")
    assert resp.status_code == 200
    body = resp.json()
    # All categories are present and null when no sessions exist.
    assert set(body.keys()) == {"DESIGN", "BUILD", "REVIEW", "COMPLETE"}
    assert all(v is None for v in body.values())


def test_latest_by_stage_id_after_start_and_switch(client) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "A", "stage_id": "DESIGN", "status": "Not Started"},
    ).json()
    c2 = client.post(
        "/api/commands",
        json={"title": "B", "stage_id": "BUILD", "status": "Not Started"},
    ).json()

    client.post("/api/sessions/start", json={"command_id": c1["id"]})
    client.post("/api/sessions/start", json={"command_id": c2["id"]})

    latest = client.get("/api/sessions/latest-by-stage-id")
    assert latest.status_code == 200
    body = latest.json()

    # Design exists and is ended (because starting Build ends any active session).
    assert body["DESIGN"] is not None
    assert body["DESIGN"]["started_at"].endswith("Z")
    assert body["DESIGN"]["ended_at"] is not None

    # Build exists and is active.
    assert body["BUILD"] is not None
    assert body["BUILD"]["ended_at"] is None


def test_latest_by_stage_id_picks_most_recent_when_multiple_for_same_stage(
    client,
) -> None:
    c1 = client.post(
        "/api/commands",
        json={"title": "A", "stage_id": "DESIGN", "status": "Not Started"},
    ).json()
    s1 = client.post("/api/sessions/start", json={"command_id": c1["id"]}).json()
    client.post("/api/sessions/stop")
    s2 = client.post("/api/sessions/start", json={"command_id": c1["id"]}).json()

    latest = client.get("/api/sessions/latest-by-stage-id").json()
    assert latest["DESIGN"]["id"] == s2["id"]
    assert latest["DESIGN"]["id"] != s1["id"]
