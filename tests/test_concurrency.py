from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm import Session

from app.schemas import ReleaseUpdate
from app.service import DomainError, publish_release, update_release
from tests.utils import create_draft, event_types

pytestmark = pytest.mark.medium


def run_concurrently(engine, *actions):
    """Run each action(session) in its own thread and session, all at the same moment.

    Returns "ok" or the DomainError name for each action, in the order given.
    """
    # The starting gate: each thread waits until all have arrived. The timeout makes
    # a stuck thread fail the test (BrokenBarrierError) instead of hanging it.
    barrier = Barrier(len(actions), timeout=5)

    def run(action):
        with Session(engine) as session:  # own connection and transaction, like a pod
            session.connection()  # connect before the gate, so it doesn't skew the race
            barrier.wait()
            try:
                action(session)
            except DomainError as error:
                return type(error).__name__
            return "ok"

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(run, action) for action in actions]
        # Keeps the input order, and re-raises any unexpected error from a thread.
        return [future.result() for future in futures]


def publish(release_id):
    return lambda session: publish_release(session, release_id)


def edit(release_id, description):
    data = ReleaseUpdate(description=description)
    return lambda session: update_release(session, release_id, data)


def test_concurrent_publish_same_release_one_wins(db_client, test_engine):
    release = create_draft(db_client)

    results = run_concurrently(
        test_engine, publish(release["id"]), publish(release["id"])
    )

    assert sorted(results) == ["InvalidTransition", "ok"]
    assert event_types(db_client, release["id"]).count("PUBLISHED") == 1


def test_concurrent_publish_same_version_different_drafts_one_wins(
    db_client, test_engine
):
    first = create_draft(db_client, version="2.0.0")
    second = create_draft(db_client, version="2.0.0")

    results = run_concurrently(test_engine, publish(first["id"]), publish(second["id"]))

    assert sorted(results) == ["DuplicateVersion", "ok"]
    statuses = {
        r["id"]: db_client.get(f"/api/releases/{r['id']}").json()["status"]
        for r in (first, second)
    }
    assert sorted(statuses.values()) == ["DRAFT", "PUBLISHED"]
    for release_id, status in statuses.items():
        expected = ["CREATED"] if status == "DRAFT" else ["CREATED", "PUBLISHED"]
        assert event_types(db_client, release_id) == expected


# Both start orders: whichever thread gets ahead decides the outcome, and without the
# lock a stale edit lands on a published release only when publish gets ahead.
@pytest.mark.parametrize("publish_first", [False, True])
def test_concurrent_edit_and_publish_keep_history_consistent(
    db_client, test_engine, publish_first
):
    release = create_draft(db_client)
    actions = [edit(release["id"], "changed"), publish(release["id"])]
    if publish_first:
        actions.reverse()

    results = run_concurrently(test_engine, *actions)

    if publish_first:
        results.reverse()
    edit_result, publish_result = results

    # Publish always wins its own race; the edit wins only if it ran first.
    assert publish_result == "ok"
    body = db_client.get(f"/api/releases/{release['id']}").json()
    history = event_types(db_client, release["id"])
    if edit_result == "ok":  # edit first, then publish
        assert body["description"] == "changed"
        assert history == ["CREATED", "UPDATED", "PUBLISHED"]
    else:  # publish first, so the edit was refused
        assert edit_result == "InvalidTransition"
        assert body["description"] == "first release"
        assert history == ["CREATED", "PUBLISHED"]
