"""Pydantic v2 schemas for project endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    default_stale_days: int = Field(30, ge=1, le=365)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    default_stale_days: int | None = Field(None, ge=1, le=365)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    default_stale_days: int
    created_at: datetime
    updated_at: datetime
