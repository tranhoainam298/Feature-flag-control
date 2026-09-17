"""Pydantic v2 schemas for Flag Health API responses."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LifecycleState


class FlagHealthResponse(BaseModel):
    """Health data for a single flag."""

    model_config = ConfigDict(from_attributes=True)

    flag_id: UUID
    flag_key: str
    flag_name: str
    state: LifecycleState
    score: int = Field(ge=0, le=100)
    age_score: float
    rollout_score: float
    staleness_score: float
    temporary_score: float
    recommendations: list[str] = Field(default_factory=list)
    is_temporary: bool
    tags: list[str] = Field(default_factory=list)


class FlagHealthSummary(BaseModel):
    """Summary statistics across all flags."""

    total: int
    draft_count: int
    active_count: int
    rolled_out_count: int
    stale_count: int
    archived_count: int
    avg_score: float


class FlagHealthListResponse(BaseModel):
    """List of flag health items with summary."""

    items: list[FlagHealthResponse]
    summary: FlagHealthSummary
