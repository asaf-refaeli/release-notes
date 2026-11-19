from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: SecretStr
    app_version: str = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # DB connections per pod: pool size + overflow. Defaults are SQLAlchemy's.
    # Keep pods x (size + overflow) below Postgres max_connections.
    db_pool_size: int = Field(default=5, ge=1)
    # ge=0: SQLAlchemy reads -1 as "no limit", which would break the max metric.
    db_max_overflow: int = Field(default=10, ge=0)


def get_settings() -> Settings:
    return Settings()
