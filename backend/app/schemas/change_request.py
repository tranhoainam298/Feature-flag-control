"""Schemas for Change Request API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChangeRequestStatus


class ChangeRequestCreate(BaseModel):
    """Payload to create a new change request."""

    title: str = Field(..., max_length=200, description="Brief summary of proposed change")
    description: str | None = Field(None, description="Detailed explanation or rationale")
    payload: dict[str, Any] = Field(..., description="JSON representation of target changes")
    scheduled_at: datetime | None = Field(None, description="Optional scheduled execution time")
    status: ChangeRequestStatus = Field(
        default=ChangeRequestStatus.PENDING,
        description="Initial status (defaults to PENDING)",
    )


class ChangeRequestResponse(BaseModel):
    """Change request details response."""

    id: UUID
    environment_id: UUID
    title: str
    description: str | None = None
    payload: dict[str, Any]
    status: ChangeRequestStatus
    requested_by: UUID
    reviewed_by: UUID | None = None
    scheduled_at: datetime | None = None
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImpactTransition(BaseModel):
    """Single variation transition record in impact simulation."""

    from_variation: str = Field(..., description="Previous variation name or key")
    to_variation: str = Field(..., description="Simulated variation name or key")
    count: int = Field(..., description="Number of evaluated contexts undergoing this transition")


class ChangeRequestImpactResponse(BaseModel):
    """Impact simulation result comparing current vs simulated rulesets."""

    total_contexts: int = Field(..., description="Total evaluated historical contexts (up to 1000)")
    affected_contexts: int = Field(..., description="Number of contexts whose evaluated variation changed")
    change_percentage: float = Field(..., description="Percentage of contexts affected (0-100%)")
    transitions: list[ImpactTransition] = Field(
        default_factory=list,
        description="Breakdown of variation transitions",
    )
    summary: str = Field(..., description="Human-readable impact explanation")
    flag_key: str | None = Field(None, description="Key of the primary flag simulated")
