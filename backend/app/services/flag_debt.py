"""Flag lifecycle state machine and debt score — PURE functions, no I/O.

This module derives lifecycle state and calculates debt score from a FlagSnapshot.
All functions are deterministic and side-effect-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.enums import LifecycleState

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_DAYS_NO_EVAL_STALE = 14  # no evaluation in this many days → considered stale


@dataclass(frozen=True)
class DebtWeights:
    """Configurable weights for debt score formula. Must sum to 1.0."""

    w_age: float = 0.25
    w_rollout: float = 0.35
    w_staleness: float = 0.25
    w_temporary: float = 0.15


@dataclass(frozen=True)
class FlagSnapshot:
    """Plain data prepared by I/O layer. Debt module only computes."""

    created_at: datetime
    archived_at: datetime | None
    is_temporary: bool
    enabled_env_count: int
    production_rollout_pct: float  # 0.0 - 100.0
    days_at_full_rollout: int
    days_since_last_eval: int | None  # None = never evaluated
    stale_days: int  # from project.default_stale_days
    now: datetime = None  # type: ignore[assignment]  # injected by caller for determinism

    def __post_init__(self) -> None:
        if self.now is None:
            object.__setattr__(self, "now", datetime.now(timezone.utc))


@dataclass(frozen=True)
class DebtResult:
    """Debt score breakdown."""

    score: int  # 0-100
    state: LifecycleState
    age_score: float  # 0-100 raw component
    rollout_score: float
    staleness_score: float
    temporary_score: float
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lifecycle state machine (derived, not persisted)
# ---------------------------------------------------------------------------


def derive_lifecycle_state(snap: FlagSnapshot) -> LifecycleState:
    """Derive lifecycle state from current flag data. Pure, deterministic."""
    # ARCHIVED beats everything
    if snap.archived_at is not None:
        return LifecycleState.ARCHIVED

    # DRAFT: not enabled anywhere
    if snap.enabled_env_count == 0:
        return LifecycleState.DRAFT

    # Check stale conditions (before ROLLED_OUT since stale overrides it)
    is_full_rollout = snap.production_rollout_pct >= 100.0

    if is_full_rollout and snap.days_at_full_rollout > snap.stale_days:
        return LifecycleState.STALE

    if snap.days_since_last_eval is not None and snap.days_since_last_eval >= _DAYS_NO_EVAL_STALE:
        return LifecycleState.STALE

    # ROLLED_OUT: 100% production
    if is_full_rollout:
        return LifecycleState.ROLLED_OUT

    # ACTIVE: enabled somewhere, not full rollout
    return LifecycleState.ACTIVE


# ---------------------------------------------------------------------------
# Debt score calculation
# ---------------------------------------------------------------------------

_AGE_MAX_DAYS = 365  # age component reaches 100 at 1 year
_ROLLOUT_MAX_DAYS = 90  # rollout component reaches 100 at 90 days at full rollout
_STALENESS_MAX_DAYS = 30  # staleness component reaches 100 at 30 days no eval


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _calc_age_score(snap: FlagSnapshot) -> float:
    """Age component: older flag → higher score."""
    age_days = (snap.now - snap.created_at).days
    if age_days <= 0:
        return 0.0
    return _clamp(age_days / _AGE_MAX_DAYS * 100)


def _calc_rollout_score(snap: FlagSnapshot) -> float:
    """Rollout component: longer at full rollout → higher score."""
    if snap.days_at_full_rollout <= 0:
        return 0.0
    return _clamp(snap.days_at_full_rollout / _ROLLOUT_MAX_DAYS * 100)


def _calc_staleness_score(snap: FlagSnapshot) -> float:
    """Staleness component: longer without evaluation → higher score."""
    if snap.days_since_last_eval is None or snap.days_since_last_eval <= 0:
        return 0.0
    return _clamp(snap.days_since_last_eval / _STALENESS_MAX_DAYS * 100)


def _calc_temporary_score(snap: FlagSnapshot) -> float:
    """Temporary component: is_temporary flag that's old gets penalty."""
    if not snap.is_temporary:
        return 0.0
    age_days = (snap.now - snap.created_at).days
    if age_days <= 0:
        return 0.0
    # Temporary flags should be short-lived; penalize based on age vs stale_days
    return _clamp(age_days / max(snap.stale_days, 1) * 100)


def calculate_debt_score(snap: FlagSnapshot, weights: DebtWeights) -> DebtResult:
    """Calculate debt score 0-100 from snapshot. Pure, deterministic."""
    age = _calc_age_score(snap)
    rollout = _calc_rollout_score(snap)
    staleness = _calc_staleness_score(snap)
    temporary = _calc_temporary_score(snap)

    raw = (
        weights.w_age * age
        + weights.w_rollout * rollout
        + weights.w_staleness * staleness
        + weights.w_temporary * temporary
    )
    score = min(100, round(raw))

    state = derive_lifecycle_state(snap)
    recs = get_recommendations(state, snap)

    return DebtResult(
        score=score,
        state=state,
        age_score=age,
        rollout_score=rollout,
        staleness_score=staleness,
        temporary_score=temporary,
        recommendations=recs,
    )


# ---------------------------------------------------------------------------
# Recommendations (Vietnamese)
# ---------------------------------------------------------------------------


def get_recommendations(state: LifecycleState, snap: FlagSnapshot) -> list[str]:
    """Generate Vietnamese recommendations based on state and snapshot."""
    recs: list[str] = []

    if state == LifecycleState.ARCHIVED:
        return recs

    if state == LifecycleState.STALE:
        recs.append("Flag này đã ổn định quá lâu, cân nhắc gỡ bỏ khỏi code.")
        if snap.is_temporary:
            recs.append("Flag tạm thời nên được xóa sau khi rollout hoàn tất.")

    if state == LifecycleState.ROLLED_OUT:
        if snap.is_temporary:
            recs.append("Flag tạm thời đã rollout 100% — nên gỡ bỏ và biến thành permanent code.")
        recs.append("Cân nhắc archive flag nếu tính năng đã ổn định.")

    if state == LifecycleState.DRAFT:
        if snap.is_temporary:
            recs.append("Flag chưa được bật ở môi trường nào.")

    if snap.days_since_last_eval is not None and snap.days_since_last_eval >= _DAYS_NO_EVAL_STALE:
        if "gỡ bỏ" not in " ".join(recs):
            recs.append("Không có evaluation trong 14+ ngày — kiểm tra xem flag còn được sử dụng không.")

    return recs
