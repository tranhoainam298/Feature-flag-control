"""Pydantic v2 schemas for API key endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApiKeyScope


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scope: ApiKeyScope = ApiKeyScope.SERVER
    expires_at: datetime | None = None


class ApiKeyCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    environment_id: UUID
    name: str
    key_prefix: str
    key: str  # Raw API key — only returned once upon creation!
    scope: ApiKeyScope
    expires_at: datetime | None
    created_at: datetime


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    environment_id: UUID
    name: str
    key_prefix: str
    scope: ApiKeyScope
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
