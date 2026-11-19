from prometheus_client import REGISTRY

from app.db import get_engine


def test_db_pool_gauges_are_exposed(db_client):
    text = db_client.get("/metrics").text

    assert "db_pool_checked_out " in text
    assert "db_pool_max_connections " in text


def test_pool_max_matches_real_pool(db_client):
    pool = get_engine().pool
    # Ask SQLAlchemy itself, not Settings (a private attribute is fine in a test).
    real_max = pool.size() + pool._max_overflow

    text = db_client.get("/metrics").text

    assert f"db_pool_max_connections {float(real_max)}" in text


def test_db_queries_are_timed(db_client):
    before = REGISTRY.get_sample_value("db_query_duration_seconds_count")

    db_client.get("/api/releases")  # runs at least one SQL query

    after = REGISTRY.get_sample_value("db_query_duration_seconds_count")
    assert after > before


def test_lock_wait_is_observed(db_client):
    before = REGISTRY.get_sample_value("release_lock_wait_seconds_count")
    release = db_client.post(
        "/api/releases", json={"version": "1.0.0", "description": "notes"}
    ).json()

    db_client.post(f"/api/releases/{release['id']}/publish")  # takes the lock once

    after = REGISTRY.get_sample_value("release_lock_wait_seconds_count")
    assert after == before + 1
