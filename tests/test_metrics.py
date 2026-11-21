import time

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError

from app.db import get_engine

pytestmark = pytest.mark.medium


def test_pool_gauges_follow_the_real_pool(migrated_url, monkeypatch):
    # The real get_engine(), as in production, pointed at the test DB.
    monkeypatch.setenv("DATABASE_URL", migrated_url)
    get_engine.cache_clear()
    try:
        engine = get_engine()
        engine.dispose()  # a pool reset must not leave the gauge on the old pool
        with engine.connect():
            assert REGISTRY.get_sample_value("db_pool_checked_out") == 1
        assert REGISTRY.get_sample_value("db_pool_checked_out") == 0
        # Ask SQLAlchemy itself, not Settings (a private attribute is fine in a test).
        real_max = engine.pool.size() + engine.pool._max_overflow
        assert REGISTRY.get_sample_value("db_pool_max_connections") == real_max
    finally:
        get_engine().dispose()
        get_engine.cache_clear()  # the next caller gets an engine for its own env


def test_db_queries_are_timed(db_client):
    before = REGISTRY.get_sample_value("db_query_duration_seconds_count")

    db_client.get("/api/releases")  # runs at least one SQL query

    after = REGISTRY.get_sample_value("db_query_duration_seconds_count")
    assert after > before


def test_failed_queries_are_timed(test_engine):
    before = REGISTRY.get_sample_value("db_query_duration_seconds_count")

    with test_engine.connect() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(text("SELECT * FROM no_such_table"))
        assert connection.info["query_start"] == []  # no start time left behind

    after = REGISTRY.get_sample_value("db_query_duration_seconds_count")
    assert after == before + 1


def test_lock_wait_is_observed(db_client):
    before = REGISTRY.get_sample_value("release_lock_wait_seconds_count")
    release = db_client.post(
        "/api/releases", json={"version": "1.0.0", "description": "notes"}
    ).json()

    db_client.post(f"/api/releases/{release['id']}/publish")  # takes the lock once

    after = REGISTRY.get_sample_value("release_lock_wait_seconds_count")
    assert after == before + 1


def test_lock_wait_excludes_waiting_for_a_connection(db_client, test_engine):
    release = db_client.post(
        "/api/releases", json={"version": "1.0.0", "description": "notes"}
    ).json()

    def slow_checkout(*args):
        time.sleep(0.2)  # as if the pool were full

    event.listen(test_engine, "checkout", slow_checkout)
    try:
        before = REGISTRY.get_sample_value("release_lock_wait_seconds_sum")
        db_client.post(f"/api/releases/{release['id']}/publish")
        waited = REGISTRY.get_sample_value("release_lock_wait_seconds_sum") - before
    finally:
        event.remove(test_engine, "checkout", slow_checkout)

    assert waited < 0.2  # the pool wait is not counted as lock wait


def test_requests_in_progress_is_exposed(db_client):
    db_client.get("/api/releases")

    # One total per pod (no labels): compared against the 40 threads.
    assert "\nhttp_requests_inprogress " in db_client.get("/metrics").text
