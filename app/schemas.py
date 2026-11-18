from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models import EventType, ReleaseStatus

# Field rules shared by create and update, so both validate the same way.
# [0-9], not \d: \d also accepts non-ASCII digits.
Version = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=32)]
# Postgres TEXT cannot store NUL (0x00); reject it here as 422, not 500 on insert.
Description = Annotated[str, Field(max_length=5000, pattern=r"^[^\x00]*$")]


class ReleaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Version
    description: Description = ""


class ReleaseUpdate(BaseModel):
    # forbid: status and published_at change only through publish/archive.
    model_config = ConfigDict(extra="forbid")

    # None means "not sent": the service skips None fields (null never reaches the DB).
    version: Version | None = None
    description: Description | None = None


class ReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    description: str
    created_at: datetime
    updated_at: datetime
    status: ReleaseStatus
    published_at: datetime | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    release_id: int
    event_type: EventType
    occurred_at: datetime
