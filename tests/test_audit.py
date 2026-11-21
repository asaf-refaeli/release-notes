from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import service
from app.models import ReleaseEvent
from tests.utils import create_draft, event_types

pytestmark = pytest.mark.medium


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


def test_events_recorded_in_order(db_client):
    release = create_draft(db_client)
    url = f"/api/releases/{release['id']}"

    db_client.patch(url, json={"description": "changed"})
    db_client.post(f"{url}/publish")
    db_client.post(f"{url}/archive")

    assert event_types(db_client, release["id"]) == [
        "CREATED",
        "UPDATED",
        "PUBLISHED",
        "ARCHIVED",
    ]


# Every refused action, from every state: the history must not change.
@pytest.mark.parametrize(
    ("state", "description", "method", "action", "status"),
    [
        ("DRAFT", "first release", "post", "/archive", 409),  # archive a draft
        ("DRAFT", "   ", "post", "/publish", 400),  # publish a blank description
        ("PUBLISHED", "first release", "post", "/publish", 409),  # publish twice
        ("PUBLISHED", "first release", "patch", "", 409),  # edit a published release
        ("ARCHIVED", "first release", "post", "/archive", 409),  # archive twice
        ("ARCHIVED", "first release", "post", "/publish", 409),  # publish archived
        ("ARCHIVED", "first release", "patch", "", 409),  # edit archived
    ],
)
def test_failed_transition_writes_no_event(
    db_client, state, description, method, action, status
):
    release = create_draft(db_client, description=description)
    url = f"/api/releases/{release['id']}"
    if state in ("PUBLISHED", "ARCHIVED"):
        assert db_client.post(f"{url}/publish").status_code == 200
    if state == "ARCHIVED":
        assert db_client.post(f"{url}/archive").status_code == 200
    history_before = event_types(db_client, release["id"])

    response = db_client.request(method, url + action, json={"description": "x"})

    assert response.status_code == status
    assert event_types(db_client, release["id"]) == history_before


def test_event_insert_failure_rolls_back_state_change(
    db_client, test_engine, monkeypatch
):
    release = create_draft(db_client)

    # For this test only: write an event type the DB's CHECK rule refuses.
    def bogus_event(session, release_id, event_type):
        session.add(ReleaseEvent(release_id=release_id, event_type="BOGUS"))

    monkeypatch.setattr(service, "_record_event", bogus_event)

    with Session(test_engine) as session:
        with pytest.raises(IntegrityError, match="ck_release_events_event_type_valid"):
            service.publish_release(session, release["id"])

    # The event failed, so the status change in the same transaction was undone too.
    body = db_client.get(f"/api/releases/{release['id']}").json()
    assert body["status"] == "DRAFT"
    assert body["published_at"] is None
    assert event_types(db_client, release["id"]) == ["CREATED"]


def test_updated_at_changes_on_edit_and_publish(db_client):
    created = create_draft(db_client)
    url = f"/api/releases/{created['id']}"

    edited = db_client.patch(url, json={"description": "changed"}).json()
    published = db_client.post(f"{url}/publish").json()

    times = [
        datetime.fromisoformat(r["updated_at"]) for r in (created, edited, published)
    ]
    assert times[0] < times[1] < times[2]
