import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@127.0.0.1:1/db")

from app.db import get_engine  # noqa: E402  (needs DATABASE_URL set first)
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:18", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated_url(postgres_url):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", postgres_url)
        command.upgrade(Config("alembic.ini"), "head")
    return postgres_url


@pytest.fixture(scope="session")
def test_engine(migrated_url):
    engine = create_engine(migrated_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_client(test_engine):
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with test_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    app.dependency_overrides[get_engine] = lambda: test_engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_engine, None)
