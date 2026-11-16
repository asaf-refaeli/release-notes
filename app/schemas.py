from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # [0-9], not \d: \d also accepts non-ASCII digits.
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=32)
    description: str = Field(default="", max_length=5000)


class ReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    description: str
    created_at: datetime
    updated_at: datetime
