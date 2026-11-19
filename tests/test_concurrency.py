from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy.orm import Session

from app.service import DomainError, publish_release
from tests.utils import create_draft, event_types


def publish_concurrently(engine, *release_ids):
    """Publish each id from its own thread and session, all at the same moment."""
    # The starting gate: each thread waits until all have arrived. The timeout makes
    # a stuck thread fail the test (BrokenBarrierError) instead of hanging it.
    barrier = Barrier(len(release_ids), timeout=5)

    def publish(release_id):
        with Session(engine) as session:  # own connection and transaction, like a pod
            session.connection()  # connect before the gate, so it doesn't skew the race
            barrier.wait()
            try:
                publish_release(session, release_id)
            except DomainError as error:
                return type(error).__name__
            return "ok"

    with ThreadPoolExecutor(max_workers=len(release_ids)) as pool:
        futures = [pool.submit(publish, release_id) for release_id in release_ids]
        # Keeps the input order, and re-raises any unexpected error from a thread.
        return [future.result() for future in futures]


def test_concurrent_publish_same_release_one_wins(db_client, test_engine):
    release = create_draft(db_client)

    results = publish_concurrently(test_engine, release["id"], release["id"])

    assert sorted(results) == ["InvalidTransition", "ok"]
    assert event_types(db_client, release["id"]).count("PUBLISHED") == 1


def test_concurrent_publish_same_version_different_drafts_one_wins(
    db_client, test_engine
):
    first = create_draft(db_client, version="2.0.0")
    second = create_draft(db_client, version="2.0.0")

    results = publish_concurrently(test_engine, first["id"], second["id"])

    assert sorted(results) == ["DuplicateVersion", "ok"]
    statuses = {
        r["id"]: db_client.get(f"/api/releases/{r['id']}").json()["status"]
        for r in (first, second)
    }
    assert sorted(statuses.values()) == ["DRAFT", "PUBLISHED"]
    for release_id, status in statuses.items():
        expected = ["CREATED"] if status == "DRAFT" else ["CREATED", "PUBLISHED"]
        assert event_types(db_client, release_id) == expected
