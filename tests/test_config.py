import pytest
from pydantic import ValidationError

from app.config import Settings

pytestmark = pytest.mark.small


def test_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings()


def test_pool_settings_default_to_sqlalchemy_values():
    settings = Settings()

    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 10


@pytest.mark.parametrize(
    ("name", "value"), [("DB_POOL_SIZE", "0"), ("DB_MAX_OVERFLOW", "-1")]
)
def test_pool_settings_reject_invalid_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()
