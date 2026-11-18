def create_draft(client, version="1.0.0", description="first release"):
    response = client.post(
        "/api/releases", json={"version": version, "description": description}
    )
    return response.json()


def test_patch_draft_updates_fields(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"description": "new"}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "new"
    events = db_client.get(f"/api/releases/{release['id']}/events").json()
    assert [e["event_type"] for e in events] == ["CREATED", "UPDATED"]


def test_patch_rejects_status_field(db_client):
    release = create_draft(db_client)
    url = f"/api/releases/{release['id']}"

    assert db_client.patch(url, json={"status": "PUBLISHED"}).status_code == 422
    response = db_client.patch(url, json={"published_at": "2026-01-01T00:00:00Z"})
    assert response.status_code == 422


def test_patch_null_field_is_ignored(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"description": None}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "first release"
    events = db_client.get(f"/api/releases/{release['id']}/events").json()
    assert [e["event_type"] for e in events] == ["CREATED"]


def test_patch_rejects_bad_version(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"version": "1.2"}
    )

    assert response.status_code == 422
