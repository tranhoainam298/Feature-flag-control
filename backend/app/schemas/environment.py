"""Pydantic v2 schemas for environment endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    key: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    is_production: bool = False


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    key: str
    is_production: bool
    ruleset_version: int
    created_at: datetime
    updated_at: datetime
