"""Schemas for Evaluation API (Hot Path)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRequest(BaseModel):
    """Payload for evaluating flags."""

    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation context containing targetingKey/userId and user attributes",
    )


class EvaluationResponse(BaseModel):
    """Result of evaluating a single feature flag."""

    model_config = ConfigDict(populate_by_name=True)

    flag_key: str = Field(..., serialization_alias="flagKey")
    value: Any
    variant: str | None = None
    reason: str
    error_code: str | None = Field(default=None, serialization_alias="errorCode")
    flag_metadata: dict[str, Any] | None = Field(default=None, serialization_alias="flagMetadata")


class EvaluateAllResponse(BaseModel):
    """Result of evaluating all feature flags in an environment."""

    flags: dict[str, EvaluationResponse]


class EventItem(BaseModel):
    """Single evaluation event payload."""

    flag_id: UUID
    variation_id: UUID
    reason: str = Field(..., max_length=30)
    context_key: str = Field(..., min_length=1, max_length=200)
    created_at: datetime | None = None


class EventBatchRequest(BaseModel):
    """Batch of evaluation events to be ingested."""

    events: list[EventItem] = Field(..., min_length=1)


class EventBatchResponse(BaseModel):
    """Response after ingesting event batch."""

    status: str = "accepted"
    count: int


class RulesetResponse(BaseModel):
    """Full ruleset for SDK in-process evaluation."""

    model_config = ConfigDict(populate_by_name=True)

    ruleset_version: int = Field(..., serialization_alias="rulesetVersion")
    flags: dict[str, Any]
    segments: dict[str, Any]
