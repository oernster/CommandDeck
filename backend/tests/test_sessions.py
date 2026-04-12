from __future__ import annotations


def test_active_session_none(client) -> None:
    resp = client.get("/api/sessions/active")
    assert resp.status_code == 200
    assert resp.json() == {"active": False}


def test_stop_session_when_none_active(client) -> None:
    resp = client.post("/api/sessions/stop")
    assert resp.status_code == 200
    assert resp.json() == {"active": False}


def test_start_session_invalid_category(client) -> None:
    resp = client.post("/api/sessions/start", json={"category": "Nope"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid category"}


def test_start_and_stop_session_flow(client) -> None:
    started = client.post("/api/sessions/start", json={"category": "Build"})
    assert started.status_code == 200
    body = started.json()
    assert body["id"] == 1
    assert body["category"] == "Build"
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
    s1 = client.post("/api/sessions/start", json={"category": "Design"}).json()
    assert s1["ended_at"] is None

    s2 = client.post("/api/sessions/start", json={"category": "Review"}).json()
    assert s2["id"] == 2
    assert s2["category"] == "Review"
    assert s2["ended_at"] is None

    # Previous session should now be ended.
    all_sessions = client.get("/api/sessions").json()
    by_id = {s["id"]: s for s in all_sessions}
    assert by_id[1]["ended_at"] is not None
    assert by_id[2]["ended_at"] is None


def test_list_sessions_filters(client) -> None:
    client.post("/api/sessions/start", json={"category": "Maintain"})
    client.post("/api/sessions/stop")
    client.post("/api/sessions/start", json={"category": "Maintain"})

    only_maintain = client.get("/api/sessions?category=Maintain")
    assert only_maintain.status_code == 200
    assert all(s["category"] == "Maintain" for s in only_maintain.json())

    active_only = client.get("/api/sessions?active=true")
    assert active_only.status_code == 200
    assert all(s["ended_at"] is None for s in active_only.json())

    inactive_only = client.get("/api/sessions?active=false")
    assert inactive_only.status_code == 200
    assert all(s["ended_at"] is not None for s in inactive_only.json())


def test_list_sessions_invalid_category_query(client) -> None:
    resp = client.get("/api/sessions?category=Nope")
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid category"}


def test_start_missing_body_is_400_invalid_request(client) -> None:
    resp = client.post("/api/sessions/start", json={})
    assert resp.status_code == 400
    assert resp.json() == {"error": "Invalid request"}


def test_latest_by_category_empty(client) -> None:
    resp = client.get("/api/sessions/latest-by-category")
    assert resp.status_code == 200
    body = resp.json()
    # All categories are present and null when no sessions exist.
    assert set(body.keys()) == {"Design", "Build", "Review", "Maintain", "Recover"}
    assert all(v is None for v in body.values())


def test_latest_by_category_after_start_and_switch(client) -> None:
    client.post("/api/sessions/start", json={"category": "Design"})
    client.post("/api/sessions/start", json={"category": "Build"})

    latest = client.get("/api/sessions/latest-by-category")
    assert latest.status_code == 200
    body = latest.json()

    # Design exists and is ended (because starting Build ends any active session).
    assert body["Design"] is not None
    assert body["Design"]["started_at"].endswith("Z")
    assert body["Design"]["ended_at"] is not None

    # Build exists and is active.
    assert body["Build"] is not None
    assert body["Build"]["ended_at"] is None


def test_latest_by_category_picks_most_recent_when_multiple_for_same_category(client) -> None:
    s1 = client.post("/api/sessions/start", json={"category": "Design"}).json()
    client.post("/api/sessions/stop")
    s2 = client.post("/api/sessions/start", json={"category": "Design"}).json()

    latest = client.get("/api/sessions/latest-by-category").json()
    assert latest["Design"]["id"] == s2["id"]
    assert latest["Design"]["id"] != s1["id"]
