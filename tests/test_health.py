import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from testcontainers.community.postgres import PostgresContainer

from app.db import get_engine
from app.main import app

client = TestClient(app)


@pytest.fixture
def dead_database():
    dead_engine = create_engine("postgresql+psycopg://user:pass@127.0.0.1:1/db")
    app.dependency_overrides[get_engine] = lambda: dead_engine
    yield
    app.dependency_overrides.clear()


def test_live_returns_ok():
    response = client.get("/healthz/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_app_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.2.3")

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": "1.2.3"}


def test_metrics_counts_requests():
    client.get("/api/version")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert 'handler="/api/version"' in response.text


def test_ready_returns_503_when_db_down(dead_database):
    response = client.get("/healthz/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert client.get("/healthz/live").status_code == 200


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:18", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def live_database(postgres_url):
    engine = create_engine(postgres_url)
    app.dependency_overrides[get_engine] = lambda: engine
    yield
    app.dependency_overrides.clear()
    engine.dispose()


def test_ready_returns_ok_when_db_up(live_database):
    response = client.get("/healthz/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
