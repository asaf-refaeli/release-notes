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


def test_create_release_rejects_bad_version(db_client):
    response = db_client.post("/api/releases", json={"version": "1.2"})

    assert response.status_code == 422


def test_create_release_rejects_unknown_field(db_client):
    response = db_client.post("/api/releases", json={"version": "1.4.0", "id": 99})

    assert response.status_code == 422
