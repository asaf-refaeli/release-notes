from datetime import datetime


def create_draft(client, version="1.0.0", description="first release"):
    response = client.post(
        "/api/releases", json={"version": version, "description": description}
    )
    return response.json()


def event_types(client, release_id):
    events = client.get(f"/api/releases/{release_id}/events").json()
    return [e["event_type"] for e in events]


def test_patch_draft_updates_fields(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"description": "new"}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "new"
    assert event_types(db_client, release["id"]) == ["CREATED", "UPDATED"]


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
    assert event_types(db_client, release["id"]) == ["CREATED"]


def test_patch_rejects_bad_version(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"version": "1.2"}
    )

    assert response.status_code == 422


def test_publish_sets_status_and_server_timestamp(db_client):
    release = create_draft(db_client)

    response = db_client.post(
        f"/api/releases/{release['id']}/publish",
        json={"published_at": "2000-01-01T00:00:00Z"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PUBLISHED"
    published_at = datetime.fromisoformat(body["published_at"])
    assert published_at >= datetime.fromisoformat(body["created_at"])
    assert published_at.year != 2000
    assert event_types(db_client, release["id"]) == ["CREATED", "PUBLISHED"]


def test_publish_twice_returns_409(db_client):
    release = create_draft(db_client)
    url = f"/api/releases/{release['id']}/publish"
    db_client.post(url)

    response = db_client.post(url)

    assert response.status_code == 409


def test_edit_published_returns_409(db_client):
    release = create_draft(db_client)
    db_client.post(f"/api/releases/{release['id']}/publish")

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"description": "changed"}
    )

    assert response.status_code == 409


def test_publish_empty_description_returns_400(db_client):
    release = create_draft(db_client, description="")

    response = db_client.post(f"/api/releases/{release['id']}/publish")

    assert response.status_code == 400


def test_publish_whitespace_description_returns_400(db_client):
    release = create_draft(db_client, description="   ")

    response = db_client.post(f"/api/releases/{release['id']}/publish")

    assert response.status_code == 400


def test_publish_duplicate_version_returns_409(db_client):
    first = create_draft(db_client, version="1.0.0")
    second = create_draft(db_client, version="1.0.0")
    assert db_client.post(f"/api/releases/{first['id']}/publish").status_code == 200

    response = db_client.post(f"/api/releases/{second['id']}/publish")

    assert response.status_code == 409
    assert db_client.get(f"/api/releases/{second['id']}").json()["status"] == "DRAFT"
    assert event_types(db_client, second["id"]) == ["CREATED"]


def test_publish_id_too_big_returns_422(db_client):
    response = db_client.post("/api/releases/99999999999999999999/publish")

    assert response.status_code == 422
