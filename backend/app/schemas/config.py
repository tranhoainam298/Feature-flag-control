from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConfigFormat, ConfigValueType


class ConfigNamespaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    format: ConfigFormat = Field(default=ConfigFormat.JSON)


class ConfigNamespaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    environment_id: UUID
    name: str
    format: ConfigFormat
    current_release_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConfigItemInput(BaseModel):
    key: str = Field(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9._-]+$")
    value: str
    value_type: ConfigValueType = Field(default=ConfigValueType.STRING)
    is_secret: bool = Field(default=False)
    json_schema: dict[str, Any] | None = Field(default=None)
    comment: str | None = Field(default=None, max_length=500)


class ConfigItemsUpdateRequest(BaseModel):
    items: list[ConfigItemInput] = Field(default_factory=list)


class ConfigItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    namespace_id: UUID
    key: str
    value: str
    value_type: ConfigValueType
    is_secret: bool
    json_schema: dict[str, Any] | None = None
    comment: str | None = None
    created_at: datetime
    updated_at: datetime


class ConfigReleaseCreate(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class ConfigReleaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    namespace_id: UUID
    version: int
    snapshot: dict[str, Any]
    comment: str | None = None
    released_by: UUID | None = None
    released_at: datetime
    is_rollback_of: UUID | None = None


class ConfigDiffResponse(BaseModel):
    added: dict[str, Any] = Field(default_factory=dict)
    removed: dict[str, Any] = Field(default_factory=dict)
    changed: dict[str, Any] = Field(default_factory=dict)
    unchanged: dict[str, Any] = Field(default_factory=dict)


class ClientConfigResponse(BaseModel):
    version: int
    namespace: str
    configs: dict[str, Any]
