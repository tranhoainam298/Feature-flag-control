"""Unit tests for flag debt score — PURE functions, no I/O.

TDD RED phase: all tests written BEFORE implementation.
Tests cover:
  - 5 state transition scenarios (derive_lifecycle_state)
  - 8+ parametric debt score cases (calculate_debt_score)
  - Config change effect
  - Breakdown parity (weighted components sum == total)
"""

from datetime import datetime, timezone

import pytest

from app.models.enums import LifecycleState
from app.services.flag_debt import (
    DebtResult,
    DebtWeights,
    FlagSnapshot,
    calculate_debt_score,
    derive_lifecycle_state,
    get_recommendations,
)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = DebtWeights()


def _snap(
    *,
    created_at: datetime | None = None,
    archived_at: datetime | None = None,
    is_temporary: bool = True,
    enabled_env_count: int = 0,
    production_rollout_pct: float = 0.0,
    days_at_full_rollout: int = 0,
    days_since_last_eval: int | None = None,
    stale_days: int = 30,
    now: datetime | None = None,
) -> FlagSnapshot:
    return FlagSnapshot(
        created_at=created_at or datetime(2024, 1, 1, tzinfo=timezone.utc),
        archived_at=archived_at,
        is_temporary=is_temporary,
        enabled_env_count=enabled_env_count,
        production_rollout_pct=production_rollout_pct,
        days_at_full_rollout=days_at_full_rollout,
        days_since_last_eval=days_since_last_eval,
        stale_days=stale_days,
        now=now or datetime(2024, 7, 1, tzinfo=timezone.utc),
    )


# ===========================================================================
# A. derive_lifecycle_state — 5 state transitions
# ===========================================================================


class TestDeriveLifecycleState:
    """Flag lifecycle state is DERIVED from data, not persisted."""

    def test_draft_when_not_enabled_anywhere(self):
        """Flag chưa bật ở bất kỳ env nào → DRAFT."""
        snap = _snap(enabled_env_count=0)
        assert derive_lifecycle_state(snap) == LifecycleState.DRAFT

    def test_active_when_enabled_but_not_full_rollout(self):
        """Flag bật ≥1 env, rollout < 100% → ACTIVE."""
        snap = _snap(enabled_env_count=2, production_rollout_pct=50.0)
        assert derive_lifecycle_state(snap) == LifecycleState.ACTIVE

    def test_rolled_out_when_100_pct_production(self):
        """Rollout = 100% ở production → ROLLED_OUT."""
        snap = _snap(
            enabled_env_count=3,
            production_rollout_pct=100.0,
            days_at_full_rollout=5,
        )
        assert derive_lifecycle_state(snap) == LifecycleState.ROLLED_OUT

    def test_stale_when_rolled_out_exceeds_stale_days(self):
        """ROLLED_OUT > stale_days → STALE."""
        snap = _snap(
            enabled_env_count=3,
            production_rollout_pct=100.0,
            days_at_full_rollout=31,
            stale_days=30,
        )
        assert derive_lifecycle_state(snap) == LifecycleState.STALE

    def test_stale_when_no_evaluation_14_days(self):
        """Không có evaluation trong 14 ngày → STALE."""
        snap = _snap(
            enabled_env_count=1,
            production_rollout_pct=100.0,
            days_at_full_rollout=5,
            days_since_last_eval=15,
        )
        assert derive_lifecycle_state(snap) == LifecycleState.STALE

    def test_stale_temporary_past_stale_days_age(self):
        """is_temporary flag quá stale_days tuổi + enabled → STALE."""
        snap = _snap(
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            is_temporary=True,
            enabled_env_count=1,
            production_rollout_pct=100.0,
            days_at_full_rollout=60,
            stale_days=30,
        )
        assert derive_lifecycle_state(snap) == LifecycleState.STALE

    def test_archived_when_archived_at_set(self):
        """archived_at not null → ARCHIVED, beats everything."""
        snap = _snap(
            archived_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
            enabled_env_count=3,
            production_rollout_pct=100.0,
        )
        assert derive_lifecycle_state(snap) == LifecycleState.ARCHIVED

    def test_active_when_enabled_but_zero_production_rollout(self):
        """Bật ở dev/staging nhưng production rollout = 0 → ACTIVE."""
        snap = _snap(enabled_env_count=2, production_rollout_pct=0.0)
        assert derive_lifecycle_state(snap) == LifecycleState.ACTIVE


# ===========================================================================
# B. calculate_debt_score — 8+ parametric tests
# ===========================================================================


class TestCalculateDebtScore:
    """Debt score 0-100, weighted formula, pure function."""

    def test_brand_new_flag_low_score(self):
        """Flag mới tạo, chưa bật → score rất thấp."""
        snap = _snap(
            created_at=datetime(2024, 6, 28, tzinfo=timezone.utc),
            now=datetime(2024, 7, 1, tzinfo=timezone.utc),  # 3 days old
            enabled_env_count=0,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert 0 <= result.score <= 15

    def test_old_flag_high_age_score(self):
        """Flag 1 năm tuổi → age component cao."""
        snap = _snap(
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            enabled_env_count=1,
            production_rollout_pct=50.0,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.age_score > 50  # age component is high

    def test_full_rollout_long_time_high_rollout_score(self):
        """Flag rolled out 100% lâu ngày → rollout component cao."""
        snap = _snap(
            enabled_env_count=3,
            production_rollout_pct=100.0,
            days_at_full_rollout=90,
            stale_days=30,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.rollout_score > 50

    def test_no_eval_14_days_high_staleness(self):
        """Không evaluation 14+ ngày → staleness component cao."""
        snap = _snap(
            enabled_env_count=1,
            production_rollout_pct=50.0,
            days_since_last_eval=20,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.staleness_score > 50

    def test_temporary_flag_adds_penalty(self):
        """is_temporary=True + old → temporary component > 0."""
        snap = _snap(
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            is_temporary=True,
            enabled_env_count=1,
            production_rollout_pct=100.0,
            days_at_full_rollout=60,
            stale_days=30,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.temporary_score > 0

    def test_permanent_flag_zero_temporary_score(self):
        """is_temporary=False → temporary component = 0."""
        snap = _snap(
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            is_temporary=False,
            enabled_env_count=1,
            production_rollout_pct=100.0,
            days_at_full_rollout=60,
            stale_days=30,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.temporary_score == 0.0

    def test_all_zero_inputs_score_zero(self):
        """Mọi input ở mức thấp nhất → score = 0."""
        snap = _snap(
            created_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
            now=datetime(2024, 6, 15, tzinfo=timezone.utc),  # same day
            is_temporary=False,
            enabled_env_count=0,
            production_rollout_pct=0.0,
            days_at_full_rollout=0,
            days_since_last_eval=0,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.score == 0

    def test_max_inputs_score_capped_at_100(self):
        """Mọi input ở mức cao nhất → score capped tại 100."""
        snap = _snap(
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            is_temporary=True,
            enabled_env_count=5,
            production_rollout_pct=100.0,
            days_at_full_rollout=365,
            days_since_last_eval=365,
            stale_days=30,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.score == 100

    def test_score_is_integer(self):
        """Score PHẢI là int, rounded."""
        snap = _snap(enabled_env_count=1, production_rollout_pct=33.3)
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert isinstance(result.score, int)

    def test_score_within_bounds(self):
        """Score luôn trong [0, 100]."""
        snap = _snap(
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            enabled_env_count=10,
            production_rollout_pct=100.0,
            days_at_full_rollout=999,
            days_since_last_eval=999,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert 0 <= result.score <= 100


# ===========================================================================
# C. Config change effect
# ===========================================================================


class TestConfigChangeEffect:
    """Changing weights changes the score."""

    def test_higher_age_weight_increases_score_for_old_flag(self):
        """Tăng w_age → score tăng cho flag cũ."""
        snap = _snap(
            created_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
            enabled_env_count=1,
            production_rollout_pct=50.0,
        )
        low_w = DebtWeights(w_age=0.10, w_rollout=0.40, w_staleness=0.30, w_temporary=0.20)
        high_w = DebtWeights(w_age=0.50, w_rollout=0.20, w_staleness=0.20, w_temporary=0.10)

        result_low = calculate_debt_score(snap, low_w)
        result_high = calculate_debt_score(snap, high_w)
        assert result_high.score >= result_low.score

    def test_zero_weight_zeroes_component(self):
        """w_age=0 → age không ảnh hưởng score."""
        snap = _snap(
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            is_temporary=False,
            enabled_env_count=0,
        )
        zero_age = DebtWeights(w_age=0.0, w_rollout=0.50, w_staleness=0.50, w_temporary=0.0)
        result = calculate_debt_score(snap, zero_age)
        # Only age contributes, but weight is 0 and rollout/staleness are 0 too
        assert result.score == 0


# ===========================================================================
# D. Breakdown parity
# ===========================================================================


class TestBreakdownParity:
    """Sum of weighted components must equal total score."""

    def test_breakdown_sums_to_score(self):
        """weighted sum of components == score (before rounding)."""
        snap = _snap(
            created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
            is_temporary=True,
            enabled_env_count=2,
            production_rollout_pct=75.0,
            days_at_full_rollout=10,
            days_since_last_eval=7,
            stale_days=30,
        )
        w = DEFAULT_WEIGHTS
        result = calculate_debt_score(snap, w)

        weighted_sum = (
            w.w_age * result.age_score
            + w.w_rollout * result.rollout_score
            + w.w_staleness * result.staleness_score
            + w.w_temporary * result.temporary_score
        )
        assert result.score == min(100, round(weighted_sum))


# ===========================================================================
# E. get_recommendations
# ===========================================================================


class TestGetRecommendations:
    """Recommendations in Vietnamese based on state + snapshot."""

    def test_stale_flag_has_recommendations(self):
        """STALE flag → at least 1 recommendation."""
        snap = _snap(
            enabled_env_count=3,
            production_rollout_pct=100.0,
            days_at_full_rollout=60,
            stale_days=30,
        )
        recs = get_recommendations(LifecycleState.STALE, snap)
        assert len(recs) >= 1

    def test_draft_flag_no_urgent_recommendations(self):
        """DRAFT flag → ít recommendation hơn."""
        snap = _snap(enabled_env_count=0)
        recs = get_recommendations(LifecycleState.DRAFT, snap)
        # Draft is fine, maybe suggest enabling
        assert isinstance(recs, list)

    def test_archived_flag_no_action_needed(self):
        """ARCHIVED → no action needed."""
        snap = _snap(archived_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
        recs = get_recommendations(LifecycleState.ARCHIVED, snap)
        assert len(recs) == 0

    def test_temporary_rolled_out_suggests_cleanup(self):
        """Temporary flag at ROLLED_OUT → suggest cleanup."""
        snap = _snap(
            is_temporary=True,
            enabled_env_count=3,
            production_rollout_pct=100.0,
            days_at_full_rollout=10,
            stale_days=30,
        )
        recs = get_recommendations(LifecycleState.ROLLED_OUT, snap)
        assert any("permanent" in r.lower() or "gỡ" in r.lower() or "xóa" in r.lower() for r in recs)


# ===========================================================================
# F. DebtResult contains correct state
# ===========================================================================


class TestDebtResultIntegration:
    """calculate_debt_score returns a DebtResult with correct state."""

    def test_result_contains_state(self):
        snap = _snap(enabled_env_count=0)
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert result.state == LifecycleState.DRAFT

    def test_result_contains_recommendations(self):
        snap = _snap(
            enabled_env_count=3,
            production_rollout_pct=100.0,
            days_at_full_rollout=60,
            stale_days=30,
        )
        result = calculate_debt_score(snap, DEFAULT_WEIGHTS)
        assert isinstance(result.recommendations, list)
