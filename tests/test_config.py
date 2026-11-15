import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings()
