from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live_returns_ok():
    response = client.get("/healthz/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_app_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.2.3")

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": "1.2.3"}
