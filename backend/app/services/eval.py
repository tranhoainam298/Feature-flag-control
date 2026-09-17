"""Evaluation service — ruleset building, evaluation execution, and event ingestion."""

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from app.core.exceptions import FlagOpsError
from app.engine.evaluator import evaluate as engine_evaluate
from app.engine.types import (
    DistributionEntry as EngineDistributionEntry,
)
from app.engine.types import (
    EvaluationContext,
)
from app.engine.types import (
    FlagRuleset as EngineFlagRuleset,
)
from app.engine.types import (
    IndividualOverride as EngineIndividualOverride,
)
from app.engine.types import (
    Ruleset as EngineRuleset,
)
from app.engine.types import (
    TargetingRule as EngineTargetingRule,
)
from app.engine.types import (
    Variation as EngineVariation,
)
from app.models.enums import ApiKeyScope
from app.models.evaluation import EvaluationEvent
from app.models.flag import (
    Flag,
    FlagEnvironmentSetting,
    IndividualOverride,
    Segment,
)
from app.models.project import Environment
from app.schemas.eval import (
    EvaluateAllResponse,
    EvaluationResponse,
    EventItem,
)
from app.services import ruleset_cache


class EvaluationTracker:
    """Batches last_evaluated_at timestamps to prevent DB writes on every evaluation."""

    def __init__(self, batch_size: int = 50) -> None:
        self.batch_size = batch_size
        self._pending_setting_ids: set[UUID] = set()
        self._lock = asyncio.Lock()

    async def record(self, setting_id: UUID, db: AsyncSession | None = None) -> None:
        async with self._lock:
            self._pending_setting_ids.add(setting_id)
            should_flush = len(self._pending_setting_ids) >= self.batch_size

        if should_flush and db is not None:
            await self.flush(db)

    async def flush(self, db: AsyncSession) -> int:
        async with self._lock:
            if not self._pending_setting_ids:
                return 0
            to_flush = list(self._pending_setting_ids)
            self._pending_setting_ids.clear()

        await db.execute(
            update(FlagEnvironmentSetting)
            .where(FlagEnvironmentSetting.id.in_(to_flush))
            .values(last_evaluated_at=func.now())
        )
        await db.commit()
        return len(to_flush)


eval_tracker = EvaluationTracker()


async def get_environment_version(db: AsyncSession, env_id: UUID) -> int:
    """Fast query for ruleset_version only (used for ETag / 304 Not Modified)."""
    ver = await db.scalar(select(Environment.ruleset_version).where(Environment.id == env_id))
    if ver is None:
        raise FlagOpsError(
            code="ENVIRONMENT_NOT_FOUND",
            message="Environment not found",
            status_code=404,
        )
    return int(ver)


async def load_ruleset_bundle(
    db: AsyncSession,
    env: Environment,
    scope: ApiKeyScope,
) -> tuple[EngineRuleset, dict[str, FlagEnvironmentSetting], dict[str, Flag]]:
    """Load complete ruleset using exactly 4 consolidated queries (zero N+1 queries).

    Queries executed:
    1. Flags joined with Variations (1 query)
    2. FlagEnvironmentSettings joined with TargetingRules (1 query)
    3. IndividualOverrides for this environment (1 query)
    4. Segments for this project (1 query)
    """
    project_id = env.project_id

    # 1. Query Flags with Variations in 1 joined query
    flag_query = (
        select(Flag)
        .options(joinedload(Flag.variations))
        .where(Flag.project_id == project_id, Flag.archived_at.is_(None))
    )
    if scope == ApiKeyScope.CLIENT:
        flag_query = flag_query.where(Flag.is_client_visible.is_(True))

    flags_res = await db.scalars(flag_query)
    flags_list = list(flags_res.unique().all())
    flag_map: dict[str, Flag] = {f.key: f for f in flags_list}

    # 2. Query Settings joined with TargetingRules in 1 query
    settings_res = await db.scalars(
        select(FlagEnvironmentSetting)
        .options(joinedload(FlagEnvironmentSetting.targeting_rules))
        .where(FlagEnvironmentSetting.environment_id == env.id)
    )
    settings_list = list(settings_res.unique().all())
    settings_by_flag_id: dict[UUID, FlagEnvironmentSetting] = {s.flag_id: s for s in settings_list}

    # 3. Query IndividualOverrides in 1 query
    overrides_res = await db.scalars(
        select(IndividualOverride)
        .join(FlagEnvironmentSetting)
        .where(FlagEnvironmentSetting.environment_id == env.id)
    )
    overrides_by_setting_id: dict[UUID, list[IndividualOverride]] = {}
    for ov in overrides_res.all():
        overrides_by_setting_id.setdefault(ov.flag_environment_setting_id, []).append(ov)

    # 4. Query Segments for this project in 1 query
    segments_res = await db.scalars(select(Segment).where(Segment.project_id == project_id))
    segments_list = list(segments_res.all())
    segments_dict: dict[str, Any] = {}
    for s in segments_list:
        segments_dict[s.key] = s.conditions
        segments_dict[str(s.id)] = s.conditions

    # Build Engine Ruleset in memory
    engine_flags: dict[str, EngineFlagRuleset] = {}
    settings_by_flag_key: dict[str, FlagEnvironmentSetting] = {}

    for flag_key, flag in flag_map.items():
        var_dict = {
            v.id: EngineVariation(id=str(v.id), key=v.key, value=v.value) for v in flag.variations
        }
        engine_variations = list(var_dict.values())

        setting = settings_by_flag_id.get(flag.id)
        if not setting:
            # Setting not initialized yet: default disabled
            default_var = engine_variations[0] if engine_variations else None
            off_var = default_var
            flag_ruleset = EngineFlagRuleset(
                flag_id=str(flag.id),
                flag_key=flag.key,
                flag_type=flag.type.value if hasattr(flag.type, "value") else str(flag.type),
                enabled=False,
                variations=engine_variations,
                default_variation=default_var,  # type: ignore[arg-type]
                off_variation=off_var,
                bucketing_key="userId",
                rules=[],
                overrides=[],
            )
            engine_flags[flag_key] = flag_ruleset
            continue

        settings_by_flag_key[flag_key] = setting
        if setting.default_variation_id:
            default_var = var_dict.get(setting.default_variation_id)
        else:
            default_var = engine_variations[0] if engine_variations else None

        if setting.off_variation_id:
            off_var = var_dict.get(setting.off_variation_id)
        else:
            off_var = default_var

        # Map overrides
        db_overrides = overrides_by_setting_id.get(setting.id, [])
        engine_overrides = [
            EngineIndividualOverride(
                id=str(o.id),
                context_key=o.context_key,
                variation=var_dict[o.variation_id],
            )
            for o in db_overrides
            if o.variation_id in var_dict
        ]

        # Map rules
        engine_rules: list[EngineTargetingRule] = []
        for r in sorted(setting.targeting_rules, key=lambda x: x.priority):
            dist_entries: list[EngineDistributionEntry] = []
            for d in r.distribution:
                v_id = UUID(str(d["variation_id"]))
                if v_id in var_dict:
                    dist_entries.append(
                        EngineDistributionEntry(
                            variation=var_dict[v_id],
                            weight=float(d["weight"]),
                        )
                    )

            engine_rules.append(
                EngineTargetingRule(
                    id=str(r.id),
                    priority=r.priority,
                    description=r.description,
                    conditions=r.conditions or {},
                    distribution=dist_entries,
                    segment_id=str(r.segment_id) if r.segment_id else None,
                )
            )

        engine_flags[flag_key] = EngineFlagRuleset(
            flag_id=str(flag.id),
            flag_key=flag.key,
            flag_type=flag.type.value if hasattr(flag.type, "value") else str(flag.type),
            enabled=setting.enabled,
            variations=engine_variations,
            default_variation=default_var,  # type: ignore[arg-type]
            off_variation=off_var,
            bucketing_key=setting.bucketing_key,
            rules=engine_rules,
            overrides=engine_overrides,
        )

    ruleset = EngineRuleset(
        environment_id=str(env.id),
        ruleset_version=env.ruleset_version,
        flags=engine_flags,
        segments=segments_dict,
    )
    return ruleset, settings_by_flag_key, flag_map


def _build_evaluation_context(raw_context: dict[str, Any]) -> EvaluationContext:
    """Extract targetingKey/userId and attributes from raw context dict."""
    if "targeting_key" in raw_context:
        t_key = str(raw_context["targeting_key"])
        attrs = raw_context.get("attributes", {})
    elif "targetingKey" in raw_context:
        t_key = str(raw_context["targetingKey"])
        attrs = {k: v for k, v in raw_context.items() if k != "targetingKey"}
    elif "userId" in raw_context:
        t_key = str(raw_context["userId"])
        attrs = {k: v for k, v in raw_context.items() if k != "userId"}
    else:
        t_key = ""
        attrs = raw_context

    return EvaluationContext(targeting_key=t_key, attributes=attrs)


async def evaluate_flag(
    db: AsyncSession,
    env: Environment,
    flag_key: str,
    raw_context: dict[str, Any],
    scope: ApiKeyScope,
) -> EvaluationResponse:
    """Evaluate a single flag for the given environment and context."""
    ruleset, settings_map, flag_map = await load_ruleset_bundle(db, env, scope)

    if flag_key not in flag_map:
        raise FlagOpsError(
            code="FLAG_NOT_FOUND",
            message=f"Flag '{flag_key}' not found in this environment",
            status_code=404,
        )

    context = _build_evaluation_context(raw_context)
    eval_result = engine_evaluate(ruleset, context, flag_key)

    # Record evaluation tracking
    setting = settings_map.get(flag_key)
    if setting:
        await eval_tracker.record(setting.id, db)

    reason_str = (
        eval_result.reason.value
        if hasattr(eval_result.reason, "value")
        else str(eval_result.reason)
    )
    error_code_str = (
        eval_result.error_code.value
        if eval_result.error_code and hasattr(eval_result.error_code, "value")
        else str(eval_result.error_code)
        if eval_result.error_code
        else None
    )

    return EvaluationResponse(
        flag_key=eval_result.flag_key,
        value=eval_result.value,
        variant=eval_result.variant,
        reason=reason_str,
        error_code=error_code_str,
        flag_metadata=eval_result.flag_metadata,
    )


async def evaluate_all_flags(
    db: AsyncSession,
    env: Environment,
    raw_context: dict[str, Any],
    scope: ApiKeyScope,
) -> EvaluateAllResponse:
    """Evaluate all flags in the environment."""
    ruleset, settings_map, flag_map = await load_ruleset_bundle(db, env, scope)
    context = _build_evaluation_context(raw_context)

    evaluated_flags: dict[str, EvaluationResponse] = {}
    for flag_key in flag_map:
        res = engine_evaluate(ruleset, context, flag_key)
        reason_str = res.reason.value if hasattr(res.reason, "value") else str(res.reason)
        error_code_str = (
            res.error_code.value
            if res.error_code and hasattr(res.error_code, "value")
            else str(res.error_code)
            if res.error_code
            else None
        )

        evaluated_flags[flag_key] = EvaluationResponse(
            flag_key=res.flag_key,
            value=res.value,
            variant=res.variant,
            reason=reason_str,
            error_code=error_code_str,
            flag_metadata=res.flag_metadata,
        )

        setting = settings_map.get(flag_key)
        if setting:
            await eval_tracker.record(setting.id, db)

    return EvaluateAllResponse(flags=evaluated_flags)


async def get_ruleset_payload(
    db: AsyncSession,
    env: Environment,
    scope: ApiKeyScope,
) -> dict[str, Any]:
    """Serialize the ruleset for SDK / in-process evaluation.

    Uses Redis cache when available. Only SERVER scope payloads are cached
    to avoid scope-mixing (CLIENT payload is a subset).
    """
    if scope == ApiKeyScope.SERVER:
        cached = await ruleset_cache.get_cached_ruleset(env.id)
        if cached is not None:
            return cached

    ruleset, _, _ = await load_ruleset_bundle(db, env, scope)

    flags_dict: dict[str, Any] = {}
    for key, f in ruleset.flags.items():
        flags_dict[key] = {
            "flagId": f.flag_id,
            "flagKey": f.flag_key,
            "flagType": f.flag_type,
            "enabled": f.enabled,
            "variations": [{"id": v.id, "key": v.key, "value": v.value} for v in f.variations],
            "defaultVariation": (
                {
                    "id": f.default_variation.id,
                    "key": f.default_variation.key,
                    "value": f.default_variation.value,
                }
                if f.default_variation
                else None
            ),
            "offVariation": (
                {
                    "id": f.off_variation.id,
                    "key": f.off_variation.key,
                    "value": f.off_variation.value,
                }
                if f.off_variation
                else None
            ),
            "bucketingKey": f.bucketing_key,
            "rules": [
                {
                    "id": r.id,
                    "priority": r.priority,
                    "description": r.description,
                    "conditions": r.conditions,
                    "distribution": [
                        {"variationId": d.variation.id, "weight": d.weight} for d in r.distribution
                    ],
                    "segmentId": r.segment_id,
                }
                for r in f.rules
            ],
            "overrides": [
                {"id": o.id, "contextKey": o.context_key, "variationId": o.variation.id}
                for o in f.overrides
            ],
        }

    payload = {
        "rulesetVersion": ruleset.ruleset_version,
        "flags": flags_dict,
        "segments": ruleset.segments,
    }

    if scope == ApiKeyScope.SERVER:
        await ruleset_cache.set_cached_ruleset(env.id, payload)

    return payload


async def record_events_batch(
    db: AsyncSession,
    env_id: UUID,
    events: list[EventItem],
) -> int:
    """Ingest evaluation events batch with SHA-256 hashed context keys."""
    now = datetime.now(timezone.utc)
    records: list[EvaluationEvent] = []

    for evt in events:
        key_hash = hashlib.sha256(evt.context_key.strip().encode("utf-8")).hexdigest()
        records.append(
            EvaluationEvent(
                environment_id=env_id,
                flag_id=evt.flag_id,
                variation_id=evt.variation_id,
                reason=evt.reason[:30],
                context_key_hash=key_hash,
                context=evt.context or {"targeting_key": evt.context_key},
                created_at=evt.created_at or now,
            )
        )

    db.add_all(records)
    await db.commit()
    return len(records)
