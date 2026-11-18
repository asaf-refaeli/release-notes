from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ReleaseStatus


class ReleaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # [0-9], not \d: \d also accepts non-ASCII digits.
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=32)
    # Postgres TEXT cannot store NUL (0x00); reject it here as 422, not 500 on insert.
    description: str = Field(default="", max_length=5000, pattern=r"^[^\x00]*$")


class ReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    description: str
    created_at: datetime
    updated_at: datetime
    status: ReleaseStatus
    published_at: datetime | None
