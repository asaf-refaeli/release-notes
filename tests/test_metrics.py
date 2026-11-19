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
