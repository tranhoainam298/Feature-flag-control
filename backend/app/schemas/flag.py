"""Pydantic v2 schemas for Flag, Variation, and FlagEnvironmentSetting."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FlagType, ToggleKind


class VariationCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=80)
    value: Any
    name: str | None = Field(None, max_length=120)
    description: str | None = None


class VariationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flag_id: UUID
    key: str
    value: Any
    name: str | None = None
    description: str | None = None
    created_at: datetime


class FlagCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    type: FlagType
    toggle_kind: ToggleKind = ToggleKind.RELEASE
    is_temporary: bool = True
    is_client_visible: bool = False
    tags: list[str] = Field(default_factory=list)
    variations: list[VariationCreate] | None = None


class FlagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    toggle_kind: ToggleKind | None = None
    is_temporary: bool | None = None
    is_client_visible: bool | None = None
    tags: list[str] | None = None


class FlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    key: str
    name: str
    description: str | None = None
    type: FlagType
    toggle_kind: ToggleKind
    is_temporary: bool
    is_client_visible: bool
    tags: list[str] = Field(default_factory=list)
    archived_at: datetime | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    variations: list[VariationResponse] = Field(default_factory=list)


class FlagSettingUpdate(BaseModel):
    enabled: bool | None = None
    default_variation_id: UUID | None = None
    off_variation_id: UUID | None = None
    bucketing_key: str | None = Field(None, min_length=1, max_length=60)


class FlagSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flag_id: UUID
    environment_id: UUID
    enabled: bool
    default_variation_id: UUID | None = None
    off_variation_id: UUID | None = None
    bucketing_key: str
    last_evaluated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
