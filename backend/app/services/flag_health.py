"""Flag health service — I/O layer that queries DB and calls pure debt score module."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import FlagOpsError
from app.models.audit import AuditLog
from app.models.enums import LifecycleState
from app.models.evaluation import EvaluationEvent
from app.models.flag import Flag, FlagEnvironmentSetting, TargetingRule
from app.models.project import Environment
from app.schemas.flag_health import FlagHealthListResponse, FlagHealthResponse, FlagHealthSummary
from app.services.flag_debt import DebtWeights, FlagSnapshot, calculate_debt_score


def _build_weights() -> DebtWeights:
    """Build weights from settings."""
    return DebtWeights(
        w_age=settings.DEBT_W_AGE,
        w_rollout=settings.DEBT_W_ROLLOUT,
        w_staleness=settings.DEBT_W_STALENESS,
        w_temporary=settings.DEBT_W_TEMPORARY,
    )


async def _get_production_rollout_pct(
    db: AsyncSession, flag_id: UUID, project_id: UUID
) -> tuple[float, int]:
    """Get production rollout percentage and days at full rollout for a flag.

    Returns (rollout_pct, days_at_full_rollout).
    """
    # Find production environments for this project
    prod_envs = await db.scalars(
        select(Environment).where(
            Environment.project_id == project_id,
            Environment.is_production.is_(True),
        )
    )
    prod_env_list = list(prod_envs.all())
    if not prod_env_list:
        return 0.0, 0

    # Get settings for production environments
    prod_env_ids = [e.id for e in prod_env_list]
    settings_result = await db.scalars(
        select(FlagEnvironmentSetting)
        .where(
            FlagEnvironmentSetting.flag_id == flag_id,
            FlagEnvironmentSetting.environment_id.in_(prod_env_ids),
        )
        .options(selectinload(FlagEnvironmentSetting.targeting_rules))
    )
    prod_settings = list(settings_result.all())

    if not prod_settings:
        return 0.0, 0

    # Calculate rollout pct from targeting rules distribution
    max_rollout = 0.0
    for fes in prod_settings:
        if not fes.enabled:
            continue
        if not fes.targeting_rules:
            # Enabled with no rules = 100% default
            max_rollout = 100.0
            continue
        # Sum up the "on" distribution weights
        for rule in fes.targeting_rules:
            if rule.distribution:
                total_weight = sum(d.get("weight", 0) for d in rule.distribution)
                if total_weight > 0:
                    max_rollout = max(max_rollout, total_weight)

    # Estimate days at full rollout (simplified: if 100% now, check last update)
    days_at_full_rollout = 0
    if max_rollout >= 100.0:
        # Use the most recent update timestamp of the production settings
        latest_update = max(fes.updated_at for fes in prod_settings if fes.enabled)
        days_at_full_rollout = (datetime.now(timezone.utc) - latest_update).days

    return max_rollout, days_at_full_rollout


async def _get_days_since_last_eval(db: AsyncSession, flag_id: UUID) -> int | None:
    """Get days since last evaluation event for a flag."""
    try:
        last_eval = await db.scalar(
            select(func.max(EvaluationEvent.created_at)).where(
                EvaluationEvent.flag_id == flag_id
            )
        )
    except Exception:
        # Table might not exist or be partitioned differently
        return None
    if last_eval is None:
        return None
    return (datetime.now(timezone.utc) - last_eval).days


async def _build_snapshot(
    db: AsyncSession, flag: Flag, project_id: UUID
) -> FlagSnapshot:
    """Build a FlagSnapshot from DB data."""
    # Count enabled environments
    enabled_count = await db.scalar(
        select(func.count()).where(
            FlagEnvironmentSetting.flag_id == flag.id,
            FlagEnvironmentSetting.enabled.is_(True),
        )
    ) or 0

    rollout_pct, days_at_full_rollout = await _get_production_rollout_pct(
        db, flag.id, project_id
    )
    days_since_last_eval = await _get_days_since_last_eval(db, flag.id)

    # Get project's stale_days
    from app.models.project import Project

    project = await db.get(Project, project_id)
    stale_days = project.default_stale_days if project else 30

    return FlagSnapshot(
        created_at=flag.created_at,
        archived_at=flag.archived_at,
        is_temporary=flag.is_temporary,
        enabled_env_count=enabled_count,
        production_rollout_pct=rollout_pct,
        days_at_full_rollout=days_at_full_rollout,
        days_since_last_eval=days_since_last_eval,
        stale_days=stale_days,
    )


async def get_flag_health_list(
    db: AsyncSession,
    project_id: UUID,
    *,
    state_filter: LifecycleState | None = None,
    min_score: int | None = None,
    sort_by: str = "score",
) -> FlagHealthListResponse:
    """Get health data for all flags in a project."""
    flags = await db.scalars(
        select(Flag).where(Flag.project_id == project_id).order_by(Flag.created_at.desc())
    )
    flag_list = list(flags.all())
    weights = _build_weights()

    items: list[FlagHealthResponse] = []
    for flag in flag_list:
        snap = await _build_snapshot(db, flag, project_id)
        result = calculate_debt_score(snap, weights)

        item = FlagHealthResponse(
            flag_id=flag.id,
            flag_key=flag.key,
            flag_name=flag.name,
            state=result.state,
            score=result.score,
            age_score=result.age_score,
            rollout_score=result.rollout_score,
            staleness_score=result.staleness_score,
            temporary_score=result.temporary_score,
            recommendations=result.recommendations,
            is_temporary=flag.is_temporary,
            tags=flag.tags or [],
        )

        # Apply filters
        if state_filter and item.state != state_filter:
            continue
        if min_score is not None and item.score < min_score:
            continue

        items.append(item)

    # Sort
    if sort_by == "score":
        items.sort(key=lambda x: x.score, reverse=True)
    elif sort_by == "name":
        items.sort(key=lambda x: x.flag_name)
    elif sort_by == "state":
        state_order = {s: i for i, s in enumerate(LifecycleState)}
        items.sort(key=lambda x: state_order.get(x.state, 99))

    # Build summary
    state_counts = {s: 0 for s in LifecycleState}
    for item in items:
        state_counts[item.state] += 1

    total = len(items)
    avg_score = sum(i.score for i in items) / total if total > 0 else 0.0

    summary = FlagHealthSummary(
        total=total,
        draft_count=state_counts[LifecycleState.DRAFT],
        active_count=state_counts[LifecycleState.ACTIVE],
        rolled_out_count=state_counts[LifecycleState.ROLLED_OUT],
        stale_count=state_counts[LifecycleState.STALE],
        archived_count=state_counts[LifecycleState.ARCHIVED],
        avg_score=round(avg_score, 1),
    )

    return FlagHealthListResponse(items=items, summary=summary)


async def get_single_flag_health(
    db: AsyncSession, flag_id: UUID, project_id: UUID
) -> FlagHealthResponse:
    """Get health data for a single flag."""
    flag = await db.scalar(
        select(Flag).where(Flag.id == flag_id, Flag.project_id == project_id)
    )
    if not flag:
        raise FlagOpsError(code="NOT_FOUND", message="Flag not found", status_code=404)

    weights = _build_weights()
    snap = await _build_snapshot(db, flag, project_id)
    result = calculate_debt_score(snap, weights)

    return FlagHealthResponse(
        flag_id=flag.id,
        flag_key=flag.key,
        flag_name=flag.name,
        state=result.state,
        score=result.score,
        age_score=result.age_score,
        rollout_score=result.rollout_score,
        staleness_score=result.staleness_score,
        temporary_score=result.temporary_score,
        recommendations=result.recommendations,
        is_temporary=flag.is_temporary,
        tags=flag.tags or [],
    )


async def archive_flag(
    db: AsyncSession, flag_id: UUID, project_id: UUID, actor_id: UUID
) -> FlagHealthResponse:
    """Archive a flag and return updated health data."""
    flag = await db.scalar(
        select(Flag).where(Flag.id == flag_id, Flag.project_id == project_id)
    )
    if not flag:
        raise FlagOpsError(code="NOT_FOUND", message="Flag not found", status_code=404)
    if flag.archived_at is not None:
        raise FlagOpsError(code="CONFLICT", message="Flag already archived", status_code=409)

    now = datetime.now(timezone.utc)
    flag.archived_at = now

    # Audit log
    from app.models.project import Project

    project = await db.get(Project, project_id)
    org_id = project.organization_id if project else None

    audit = AuditLog(
        actor_id=actor_id,
        action="flag.archived",
        entity_type="flag",
        entity_id=str(flag.id),
        organization_id=org_id,
        project_id=project_id,
        before={"archived_at": None},
        after={"archived_at": now.isoformat()},
    )
    db.add(audit)
    await db.flush()

    return await get_single_flag_health(db, flag_id, project_id)
