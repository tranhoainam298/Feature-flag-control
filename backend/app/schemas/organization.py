"""Pydantic v2 schemas for organization and membership."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MemberRole


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class MemberCreate(BaseModel):
    user_id: UUID
    role: MemberRole = MemberRole.DEVELOPER


class MemberUpdate(BaseModel):
    role: MemberRole


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    organization_id: UUID
    role: MemberRole
    created_at: datetime
