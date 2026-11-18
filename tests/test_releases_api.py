from sqlalchemy import text


def test_create_release_saves_to_database(db_client, test_engine):
    response = db_client.post(
        "/api/releases", json={"version": "1.4.0", "description": "Dark mode"}
    )

    assert response.status_code == 201
    release_id = response.json()["id"]

    query = text("SELECT version, description, created_at FROM releases WHERE id = :id")
    with test_engine.connect() as connection:
        row = connection.execute(query, {"id": release_id}).one()

    assert row.version == "1.4.0"
    assert row.description == "Dark mode"
    assert row.created_at is not None


def test_new_release_is_draft(db_client):
    response = db_client.post("/api/releases", json={"version": "1.0.0"})

    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    assert response.json()["published_at"] is None


def test_create_release_rejects_bad_version(db_client):
    response = db_client.post("/api/releases", json={"version": "1.2"})

    assert response.status_code == 422


def test_create_release_rejects_unknown_field(db_client):
    response = db_client.post("/api/releases", json={"version": "1.4.0", "id": 99})

    assert response.status_code == 422


def test_create_release_rejects_nul_character(db_client):
    response = db_client.post(
        "/api/releases", json={"version": "1.0.0", "description": "a\u0000b"}
    )

    assert response.status_code == 422


def test_list_releases_newest_first(db_client):
    for version in ("1.0.0", "1.1.0", "1.2.0"):
        db_client.post("/api/releases", json={"version": version})

    response = db_client.get("/api/releases")

    assert response.status_code == 200
    assert [r["version"] for r in response.json()] == ["1.2.0", "1.1.0", "1.0.0"]


def test_list_releases_paginates(db_client):
    for version in ("1.0.0", "1.1.0", "1.2.0"):
        db_client.post("/api/releases", json={"version": version})

    response = db_client.get("/api/releases?limit=1&offset=1")

    assert [r["version"] for r in response.json()] == ["1.1.0"]


def test_list_releases_rejects_limit_over_100(db_client):
    response = db_client.get("/api/releases?limit=101")

    assert response.status_code == 422


def test_list_releases_rejects_offset_too_big_for_postgres(db_client):
    response = db_client.get("/api/releases?offset=99999999999999999999")

    assert response.status_code == 422


def test_get_release_returns_it(db_client):
    created = db_client.post("/api/releases", json={"version": "1.4.0"}).json()

    response = db_client.get(f"/api/releases/{created['id']}")

    assert response.status_code == 200
    assert response.json()["version"] == "1.4.0"


def test_get_unknown_release_returns_404(db_client):
    response = db_client.get("/api/releases/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Release 999 not found"}


def test_get_non_integer_id_returns_422(db_client):
    response = db_client.get("/api/releases/abc")

    assert response.status_code == 422


def test_get_id_too_big_for_postgres_returns_422(db_client):
    response = db_client.get("/api/releases/99999999999999999999")

    assert response.status_code == 422
