from datetime import datetime

import pytest

from tests.utils import create_draft, create_published, event_types


def test_patch_draft_updates_fields(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}",
        json={"version": "1.0.1", "description": "new"},
    )

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.1"
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


def test_patch_same_value_writes_no_event(db_client):
    release = create_draft(db_client)

    response = db_client.patch(
        f"/api/releases/{release['id']}", json={"description": "first release"}
    )

    assert response.status_code == 200
    assert response.json()["updated_at"] == release["updated_at"]
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
    release = create_published(db_client)

    response = db_client.post(f"/api/releases/{release['id']}/publish")

    assert response.status_code == 409


def test_edit_published_returns_409(db_client):
    release = create_published(db_client)

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
    assert "published or archived" in response.json()["detail"]
    assert db_client.get(f"/api/releases/{second['id']}").json()["status"] == "DRAFT"
    assert event_types(db_client, second["id"]) == ["CREATED"]


def test_publish_id_too_big_returns_422(db_client):
    response = db_client.post("/api/releases/99999999999999999999/publish")

    assert response.status_code == 422


def test_archive_published_ok(db_client):
    release = create_published(db_client)

    response = db_client.post(f"/api/releases/{release['id']}/archive")

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
    assert response.json()["published_at"] == release["published_at"]
    assert event_types(db_client, release["id"]) == ["CREATED", "PUBLISHED", "ARCHIVED"]


def test_archive_draft_returns_409(db_client):
    release = create_draft(db_client)

    response = db_client.post(f"/api/releases/{release['id']}/archive")

    assert response.status_code == 409


def test_archive_twice_returns_409(db_client):
    release = create_published(db_client)
    url = f"/api/releases/{release['id']}/archive"
    assert db_client.post(url).status_code == 200

    response = db_client.post(url)

    assert response.status_code == 409


def test_archived_release_is_final(db_client):
    release = create_published(db_client)
    url = f"/api/releases/{release['id']}"
    assert db_client.post(f"{url}/archive").status_code == 200

    assert db_client.patch(url, json={"description": "changed"}).status_code == 409
    assert db_client.post(f"{url}/publish").status_code == 409
    assert db_client.get(url).json()["description"] == "first release"
    assert event_types(db_client, release["id"]) == ["CREATED", "PUBLISHED", "ARCHIVED"]


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", "/api/releases/999/publish"),
        ("post", "/api/releases/999/archive"),
        ("patch", "/api/releases/999"),
        ("get", "/api/releases/999/events"),
    ],
)
def test_actions_on_unknown_id_return_404(db_client, method, url):
    # The body is needed only by PATCH (to pass validation); the others ignore it.
    response = db_client.request(method, url, json={"description": "x"})

    assert response.status_code == 404
    # The service's message, not FastAPI's "Not Found" for a route that does not exist.
    assert response.json()["detail"] == "Release 999 not found"
