from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DistributionItem(BaseModel):
    variation_id: UUID
    weight: float = Field(..., ge=0.0, le=100.0)


class TargetingRuleCreate(BaseModel):
    priority: int = Field(..., ge=1)
    description: str | None = Field(default=None, max_length=255)
    segment_id: UUID | None = None
    conditions: dict[str, Any] | list[dict[str, Any]] | None = None
    distribution: list[DistributionItem] = Field(..., min_length=1)


class TargetingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flag_environment_setting_id: UUID
    priority: int
    description: str | None = None
    segment_id: UUID | None = None
    conditions: dict[str, Any] | list[dict[str, Any]] | None = None
    distribution: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class TargetingRulesUpdate(BaseModel):
    rules: list[TargetingRuleCreate]


class IndividualOverrideCreate(BaseModel):
    context_key: str = Field(..., min_length=1, max_length=200)
    variation_id: UUID


class IndividualOverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flag_environment_setting_id: UUID
    context_key: str
    variation_id: UUID
    created_at: datetime
    updated_at: datetime


class SimulateRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class RuleTraceItem(BaseModel):
    rule_id: str | None = None
    priority: int | None = None
    description: str | None = None
    matched: bool
    reason: str


class SimulateResponse(BaseModel):
    flag_key: str
    value: Any
    variant: str
    reason: str
    matched_rule_id: str | None = None
    matched_rule_description: str | None = None
    trace: list[RuleTraceItem] = Field(default_factory=list)
