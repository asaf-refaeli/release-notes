"""Test helpers shared by several test files."""


def create_draft(client, version="1.0.0", description="first release"):
    response = client.post(
        "/api/releases", json={"version": version, "description": description}
    )
    return response.json()


def create_published(client, version="1.0.0"):
    release = create_draft(client, version=version)
    response = client.post(f"/api/releases/{release['id']}/publish")
    # Fail here, in setup, if publish broke; not later with a misleading 409.
    assert response.status_code == 200
    return response.json()


def event_types(client, release_id):
    events = client.get(f"/api/releases/{release_id}/events").json()
    return [e["event_type"] for e in events]
