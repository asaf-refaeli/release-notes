def test_create_writes_created_event(db_client):
    release = db_client.post("/api/releases", json={"version": "1.0.0"}).json()

    response = db_client.get(f"/api/releases/{release['id']}/events")

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "CREATED"
    assert events[0]["release_id"] == release["id"]


def test_events_for_unknown_release_return_404(db_client):
    response = db_client.get("/api/releases/999/events")

    assert response.status_code == 404


def test_events_with_non_integer_id_return_422(db_client):
    response = db_client.get("/api/releases/abc/events")

    assert response.status_code == 422
