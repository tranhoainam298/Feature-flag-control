from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SegmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    conditions: dict[str, Any] = Field(default_factory=dict)


class SegmentCreate(SegmentBase):
    key: str = Field(..., min_length=1, max_length=160, pattern=r"^[a-z0-9_-]+$")


class SegmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    conditions: dict[str, Any] | None = None


class SegmentResponse(SegmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    key: str
    created_at: datetime
    updated_at: datetime
