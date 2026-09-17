"""Targeting, Segment, and Evaluation Simulation Service."""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FlagOpsError
from app.engine.evaluator import evaluate as engine_evaluate
from app.engine.matcher import match_condition_group
from app.engine.operators import OPERATORS
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
from app.models.audit import AuditLog
from app.models.flag import (
    Flag,
    FlagEnvironmentSetting,
    IndividualOverride,
    Segment,
    TargetingRule,
    Variation,
)
from app.models.project import Environment, Project
from app.schemas.segment import SegmentCreate, SegmentUpdate
from app.schemas.targeting import (
    IndividualOverrideCreate,
    RuleTraceItem,
    SimulateResponse,
    TargetingRulesUpdate,
)
from app.services.flag import bump_ruleset_version

# ============================================================================
# VALIDATION HELPERS
# ============================================================================


def validate_condition_tree(conditions: Any, depth: int = 1, max_depth: int = 5) -> None:
    """Validate condition operators and nesting depth limit."""
    if depth > max_depth:
        raise FlagOpsError(
            code="CONDITION_DEPTH_EXCEEDED",
            message=f"Condition tree exceeded maximum depth limit of {max_depth}",
            status_code=400,
        )

    if not conditions:
        return

    if isinstance(conditions, dict):
        # Could be a condition group or a single condition
        if "children" in conditions or conditions.get("operator") in ("AND", "OR"):
            for cond in conditions.get("conditions", []):
                validate_condition_tree(cond, depth=depth, max_depth=max_depth)
            for child in conditions.get("children", []):
                validate_condition_tree(child, depth=depth + 1, max_depth=max_depth)
        else:
            op = conditions.get("operator")
            if not op or (
                str(op).upper() not in OPERATORS and str(op).upper() != "IS_ONE_OF_SEGMENT"
            ):
                raise FlagOpsError(
                    code="INVALID_OPERATOR",
                    message=f"Invalid operator: '{op}'",
                    status_code=422,
                )
    elif isinstance(conditions, list):
        for item in conditions:
            validate_condition_tree(item, depth=depth, max_depth=max_depth)


def _extract_segment_refs(conditions: Any) -> list[str]:
    """Recursively collect all segment identifiers from IS_ONE_OF_SEGMENT conditions."""
    refs: list[str] = []
    if isinstance(conditions, dict):
        op = conditions.get("operator")
        if op and str(op).upper() == "IS_ONE_OF_SEGMENT":
            val = conditions.get("value")
            if val is not None:
                if isinstance(val, list):
                    refs.extend(str(v) for v in val)
                else:
                    refs.append(str(val))
        for child in conditions.get("children", []):
            refs.extend(_extract_segment_refs(child))
        for cond in conditions.get("conditions", []):
            refs.extend(_extract_segment_refs(cond))
    elif isinstance(conditions, list):
        for item in conditions:
            refs.extend(_extract_segment_refs(item))
    return refs


def _is_valid_uuid(val: Any) -> bool:
    try:
        UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


async def check_cyclic_segment_reference(
    db: AsyncSession,
    project_id: UUID,
    current_key: str,
    conditions: Any,
    visited: set[str] | None = None,
) -> None:
    """Detect circular references between segments."""
    if visited is None:
        visited = {current_key}
    else:
        visited = set(visited)
        visited.add(current_key)

    refs = _extract_segment_refs(conditions)
    for ref in refs:
        if ref in visited:
            raise FlagOpsError(
                code="CYCLIC_SEGMENT_REFERENCE",
                message=f"Cyclic segment reference detected involving '{ref}'",
                status_code=400,
            )
        query = select(Segment).where(Segment.project_id == project_id)
        if _is_valid_uuid(ref):
            query = query.where((Segment.key == ref) | (Segment.id == UUID(str(ref))))
        else:
            query = query.where(Segment.key == ref)

        referenced_seg = await db.scalar(query)
        if referenced_seg and referenced_seg.conditions:
            await check_cyclic_segment_reference(
                db=db,
                project_id=project_id,
                current_key=referenced_seg.key,
                conditions=referenced_seg.conditions,
                visited=visited | {ref, referenced_seg.key},
            )


# ============================================================================
# SEGMENT SERVICES
# ============================================================================


async def get_project_segments(db: AsyncSession, project_id: UUID) -> list[Segment]:
    """Retrieve all segments for a project."""
    res = await db.scalars(
        select(Segment).where(Segment.project_id == project_id).order_by(Segment.name.asc())
    )
    return list(res.all())


async def create_segment(
    db: AsyncSession,
    project: Project,
    data: SegmentCreate,
    user_id: UUID,
) -> Segment:
    """Create a new segment within a project."""
    # Check duplicate key
    existing = await db.scalar(
        select(Segment).where(Segment.project_id == project.id, Segment.key == data.key)
    )
    if existing:
        raise FlagOpsError(
            code="SEGMENT_KEY_EXISTS",
            message=f"Segment key '{data.key}' already exists in this project",
            status_code=409,
        )

    # Validate conditions
    validate_condition_tree(data.conditions)
    if data.conditions:
        await check_cyclic_segment_reference(db, project.id, data.key, data.conditions)

    segment = Segment(
        project_id=project.id,
        key=data.key,
        name=data.name,
        description=data.description,
        conditions=data.conditions,
    )
    db.add(segment)

    # Bump ruleset_version for all environments of this project
    envs = await db.scalars(select(Environment).where(Environment.project_id == project.id))
    for env in envs:
        await bump_ruleset_version(db, env.id)

    # Audit log
    audit = AuditLog(
        organization_id=project.organization_id,
        project_id=project.id,
        actor_id=user_id,
        action="CREATE",
        entity_type="SEGMENT",
        entity_id=str(segment.id),
        after=data.model_dump(),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(segment)
    return segment


async def get_segment(db: AsyncSession, project_id: UUID, segment_id: UUID) -> Segment:
    """Get segment by ID within project."""
    segment = await db.scalar(
        select(Segment).where(Segment.id == segment_id, Segment.project_id == project_id)
    )
    if not segment:
        raise FlagOpsError(
            code="SEGMENT_NOT_FOUND",
            message="Segment not found",
            status_code=404,
        )
    return segment


async def update_segment(
    db: AsyncSession,
    project: Project,
    segment_id: UUID,
    data: SegmentUpdate,
    user_id: UUID,
) -> Segment:
    """Update a segment."""
    segment = await get_segment(db, project.id, segment_id)
    before_data = {
        "name": segment.name,
        "description": segment.description,
        "conditions": segment.conditions,
    }

    if data.conditions is not None:
        validate_condition_tree(data.conditions)
        await check_cyclic_segment_reference(db, project.id, segment.key, data.conditions)
        segment.conditions = data.conditions

    if data.name is not None:
        segment.name = data.name
    if data.description is not None:
        segment.description = data.description

    # Bump ruleset_version for all environments
    envs = await db.scalars(select(Environment).where(Environment.project_id == project.id))
    for env in envs:
        await bump_ruleset_version(db, env.id)

    audit = AuditLog(
        organization_id=project.organization_id,
        project_id=project.id,
        actor_id=user_id,
        action="UPDATE",
        entity_type="SEGMENT",
        entity_id=str(segment.id),
        before=before_data,
        after={
            "name": segment.name,
            "description": segment.description,
            "conditions": segment.conditions,
        },
    )
    db.add(audit)

    await db.commit()
    await db.refresh(segment)
    return segment


async def delete_segment(
    db: AsyncSession,
    project: Project,
    segment_id: UUID,
    user_id: UUID,
) -> None:
    """Delete a segment."""
    segment = await get_segment(db, project.id, segment_id)
    before_data = {"key": segment.key, "name": segment.name}

    await db.delete(segment)

    # Bump ruleset_version for all environments
    envs = await db.scalars(select(Environment).where(Environment.project_id == project.id))
    for env in envs:
        await bump_ruleset_version(db, env.id)

    audit = AuditLog(
        organization_id=project.organization_id,
        project_id=project.id,
        actor_id=user_id,
        action="DELETE",
        entity_type="SEGMENT",
        entity_id=str(segment_id),
        before=before_data,
    )
    db.add(audit)

    await db.commit()


# ============================================================================
# TARGETING RULES & OVERRIDES SERVICES
# ============================================================================


async def get_or_create_flag_setting(
    db: AsyncSession, flag_id: UUID, environment_id: UUID
) -> FlagEnvironmentSetting:
    """Get or auto-create FlagEnvironmentSetting."""
    setting = await db.scalar(
        select(FlagEnvironmentSetting).where(
            FlagEnvironmentSetting.flag_id == flag_id,
            FlagEnvironmentSetting.environment_id == environment_id,
        )
    )
    if not setting:
        setting = FlagEnvironmentSetting(
            flag_id=flag_id,
            environment_id=environment_id,
            enabled=False,
        )
        db.add(setting)
        await db.flush()
    return setting


async def get_targeting_rules(db: AsyncSession, flag_id: UUID, env_id: UUID) -> list[TargetingRule]:
    """Retrieve targeting rules for a flag in an environment ordered by priority ASC."""
    setting = await get_or_create_flag_setting(db, flag_id, env_id)
    rules = await db.scalars(
        select(TargetingRule)
        .where(TargetingRule.flag_environment_setting_id == setting.id)
        .order_by(TargetingRule.priority.asc())
    )
    return list(rules.all())


async def set_targeting_rules_atomic(
    db: AsyncSession,
    flag: Flag,
    env: Environment,
    rules_data: TargetingRulesUpdate,
    user_id: UUID,
) -> list[TargetingRule]:
    """Atomically replace all targeting rules for a flag environment setting.

    Strict validation:
    - Unique priorities
    - Distribution sum == 100
    - Variation IDs belong to this flag
    - Valid operators
    - Condition tree depth <= 5
    - Referenced segment belongs to same project
    """
    setting = await get_or_create_flag_setting(db, flag.id, env.id)

    # 1. Validate priority uniqueness
    priorities = [r.priority for r in rules_data.rules]
    if len(priorities) != len(set(priorities)):
        raise FlagOpsError(
            code="DUPLICATE_PRIORITY",
            message="Rule priorities within a flag environment setting must be unique",
            status_code=422,
        )

    # Load valid variations for this flag
    flag_vars = await db.scalars(select(Variation).where(Variation.flag_id == flag.id))
    valid_var_ids = {v.id for v in flag_vars.all()}

    # 2. Validate each rule
    for rule in rules_data.rules:
        # Check distribution weight sum
        total_w = sum(d.weight for d in rule.distribution)
        if abs(total_w - 100.0) > 0.001:
            raise FlagOpsError(
                code="INVALID_DISTRIBUTION_WEIGHT",
                message=f"Total distribution weight must equal 100, got {total_w}",
                status_code=422,
            )

        # Check variations belong to flag
        for d in rule.distribution:
            if d.variation_id not in valid_var_ids:
                raise FlagOpsError(
                    code="INVALID_VARIATION",
                    message=f"Variation {d.variation_id} does not belong to flag '{flag.key}'",
                    status_code=422,
                )

        # Check conditions
        if rule.conditions:
            validate_condition_tree(rule.conditions)
            for seg_ref in _extract_segment_refs(rule.conditions):
                seg_obj = None
                try:
                    seg_uuid = UUID(seg_ref)
                    seg_obj = await db.scalar(
                        select(Segment).where(
                            Segment.id == seg_uuid, Segment.project_id == flag.project_id
                        )
                    )
                except (ValueError, TypeError):
                    seg_obj = await db.scalar(
                        select(Segment).where(
                            Segment.key == seg_ref, Segment.project_id == flag.project_id
                        )
                    )
                if not seg_obj:
                    raise FlagOpsError(
                        code="SEGMENT_PROJECT_MISMATCH",
                        message=f"Referenced segment '{seg_ref}' does not exist in this project",
                        status_code=422,
                    )

        # Check direct segment_id reference
        if rule.segment_id:
            seg = await db.scalar(
                select(Segment).where(
                    Segment.id == rule.segment_id, Segment.project_id == flag.project_id
                )
            )
            if not seg:
                raise FlagOpsError(
                    code="SEGMENT_PROJECT_MISMATCH",
                    message="Referenced segment does not exist in this project",
                    status_code=422,
                )

    # 3. Fetch old rules for audit log before deletion
    old_rules = await db.scalars(
        select(TargetingRule).where(TargetingRule.flag_environment_setting_id == setting.id)
    )
    before_rules = [
        {"id": str(r.id), "priority": r.priority, "description": r.description}
        for r in old_rules.all()
    ]

    # 4. Atomic delete + insert in single transaction
    await db.execute(
        delete(TargetingRule).where(TargetingRule.flag_environment_setting_id == setting.id)
    )

    new_rule_records: list[TargetingRule] = []
    for r in sorted(rules_data.rules, key=lambda x: x.priority):
        rec = TargetingRule(
            flag_environment_setting_id=setting.id,
            priority=r.priority,
            description=r.description,
            segment_id=r.segment_id,
            conditions=r.conditions,
            distribution=[d.model_dump(mode="json") for d in r.distribution],
        )
        db.add(rec)
        new_rule_records.append(rec)

    # 5. Bump ruleset_version & audit log
    await bump_ruleset_version(db, env.id)

    project = await db.scalar(select(Project).where(Project.id == flag.project_id))
    org_id = project.organization_id if project else None

    audit = AuditLog(
        organization_id=org_id,
        project_id=flag.project_id,
        environment_id=env.id,
        actor_id=user_id,
        action="UPDATE",
        entity_type="TARGETING_RULES",
        entity_id=str(setting.id),
        before={"rules": before_rules},
        after={"rules": [r.model_dump(mode="json") for r in rules_data.rules]},
    )
    db.add(audit)

    await db.commit()
    for rec in new_rule_records:
        await db.refresh(rec)

    return new_rule_records


async def create_individual_override(
    db: AsyncSession,
    flag: Flag,
    env: Environment,
    data: IndividualOverrideCreate,
    user_id: UUID,
) -> IndividualOverride:
    """Create or update an individual override."""
    setting = await get_or_create_flag_setting(db, flag.id, env.id)

    # Validate variation belongs to flag
    flag_vars = await db.scalars(select(Variation).where(Variation.flag_id == flag.id))
    valid_var_ids = {v.id for v in flag_vars.all()}
    if data.variation_id not in valid_var_ids:
        raise FlagOpsError(
            code="INVALID_VARIATION",
            message=f"Variation {data.variation_id} does not belong to flag '{flag.key}'",
            status_code=422,
        )

    # Upsert override
    override = await db.scalar(
        select(IndividualOverride).where(
            IndividualOverride.flag_environment_setting_id == setting.id,
            IndividualOverride.context_key == data.context_key,
        )
    )

    action = "UPDATE" if override else "CREATE"
    before = {"variation_id": str(override.variation_id)} if override else None

    if override:
        override.variation_id = data.variation_id
    else:
        override = IndividualOverride(
            flag_environment_setting_id=setting.id,
            context_key=data.context_key,
            variation_id=data.variation_id,
        )
        db.add(override)

    await bump_ruleset_version(db, env.id)

    project = await db.scalar(select(Project).where(Project.id == flag.project_id))
    audit = AuditLog(
        organization_id=project.organization_id if project else None,
        project_id=flag.project_id,
        environment_id=env.id,
        actor_id=user_id,
        action=action,
        entity_type="INDIVIDUAL_OVERRIDE",
        entity_id=str(setting.id),
        before=before,
        after=data.model_dump(mode="json"),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(override)
    return override


async def delete_individual_override(
    db: AsyncSession,
    flag: Flag,
    env: Environment,
    override_id: UUID,
    user_id: UUID,
) -> None:
    """Delete an individual override."""
    setting = await get_or_create_flag_setting(db, flag.id, env.id)

    override = await db.scalar(
        select(IndividualOverride).where(
            IndividualOverride.id == override_id,
            IndividualOverride.flag_environment_setting_id == setting.id,
        )
    )
    if not override:
        raise FlagOpsError(
            code="OVERRIDE_NOT_FOUND",
            message="Individual override not found",
            status_code=404,
        )

    before = {
        "id": str(override.id),
        "context_key": override.context_key,
        "variation_id": str(override.variation_id),
    }
    await db.delete(override)
    await bump_ruleset_version(db, env.id)

    project = await db.scalar(select(Project).where(Project.id == flag.project_id))
    audit = AuditLog(
        organization_id=project.organization_id if project else None,
        project_id=flag.project_id,
        environment_id=env.id,
        actor_id=user_id,
        action="DELETE",
        entity_type="INDIVIDUAL_OVERRIDE",
        entity_id=str(override_id),
        before=before,
    )
    db.add(audit)

    await db.commit()


# ============================================================================
# EVALUATION SIMULATION SERVICE
# ============================================================================


async def simulate_flag_evaluation(
    db: AsyncSession,
    flag: Flag,
    env: Environment,
    context_raw: dict[str, Any],
) -> SimulateResponse:
    """Simulate evaluation of a flag with detailed rule evaluation trace."""
    setting = await get_or_create_flag_setting(db, flag.id, env.id)

    # Load all variations
    variations_res = await db.scalars(select(Variation).where(Variation.flag_id == flag.id))
    variations_list = list(variations_res.all())
    var_map = {
        v.id: EngineVariation(id=str(v.id), key=v.key, value=v.value, name=v.name)
        for v in variations_list
    }

    # Load rules and overrides
    rules_res = await db.scalars(
        select(TargetingRule)
        .where(TargetingRule.flag_environment_setting_id == setting.id)
        .order_by(TargetingRule.priority.asc())
    )
    db_rules = list(rules_res.all())

    overrides_res = await db.scalars(
        select(IndividualOverride).where(
            IndividualOverride.flag_environment_setting_id == setting.id
        )
    )
    db_overrides = list(overrides_res.all())

    # Load all project segments
    segments_res = await db.scalars(select(Segment).where(Segment.project_id == flag.project_id))
    segments_all = list(segments_res.all())
    segments_map: dict[str, Any] = {}
    for s in segments_all:
        segments_map[s.key] = s.conditions
        segments_map[str(s.id)] = s.conditions

    # Construct EvaluationContext
    if "targeting_key" in context_raw:
        t_key = str(context_raw["targeting_key"])
        attrs = context_raw.get("attributes", {})
    elif "userId" in context_raw:
        t_key = str(context_raw["userId"])
        attrs = {k: v for k, v in context_raw.items() if k != "userId"}
    elif "targetingKey" in context_raw:
        t_key = str(context_raw["targetingKey"])
        attrs = {k: v for k, v in context_raw.items() if k != "targetingKey"}
    else:
        t_key = ""
        attrs = context_raw

    eval_ctx = EvaluationContext(targeting_key=t_key, attributes=attrs)

    # Construct Engine Ruleset
    default_var = (
        var_map.get(setting.default_variation_id) if setting.default_variation_id else None
    )
    off_var = var_map.get(setting.off_variation_id) if setting.off_variation_id else None

    engine_overrides = [
        EngineIndividualOverride(
            id=str(o.id),
            context_key=o.context_key,
            variation=var_map[o.variation_id],
        )
        for o in db_overrides
        if o.variation_id in var_map
    ]

    engine_rules: list[EngineTargetingRule] = []
    for r in db_rules:
        # Build distribution entries
        dist_entries: list[EngineDistributionEntry] = []
        for d in r.distribution:
            var_id = UUID(str(d["variation_id"]))
            if var_id in var_map:
                dist_entries.append(
                    EngineDistributionEntry(
                        variation=var_map[var_id],
                        weight=float(d["weight"]),
                    )
                )

        # Merge segment condition into conditions if segment_id is set
        rule_conditions = r.conditions or {}
        if r.segment_id:
            seg_rec = await db.scalar(select(Segment).where(Segment.id == r.segment_id))
            if seg_rec:
                seg_cond = {
                    "attribute": "",
                    "operator": "IS_ONE_OF_SEGMENT",
                    "value": seg_rec.key,
                }
                if isinstance(rule_conditions, dict) and "conditions" in rule_conditions:
                    rule_conditions["conditions"].append(seg_cond)
                else:
                    rule_conditions = {
                        "operator": "AND",
                        "conditions": [seg_cond]
                        + (
                            rule_conditions
                            if isinstance(rule_conditions, list)
                            else [rule_conditions]
                            if rule_conditions
                            else []
                        ),
                    }

        engine_rules.append(
            EngineTargetingRule(
                id=str(r.id),
                priority=r.priority,
                description=r.description,
                conditions=rule_conditions,
                distribution=dist_entries,
                segment_id=str(r.segment_id) if r.segment_id else None,
            )
        )

    flag_ruleset = EngineFlagRuleset(
        flag_id=str(flag.id),
        flag_key=flag.key,
        flag_type=flag.type.value if hasattr(flag.type, "value") else str(flag.type),
        enabled=setting.enabled,
        bucketing_key=setting.bucketing_key or "targetingKey",
        default_variation=default_var,
        off_variation=off_var,
        variations=list(var_map.values()),
        rules=engine_rules,
        overrides=engine_overrides,
    )

    ruleset = EngineRuleset(
        environment_id=str(env.id),
        ruleset_version=env.ruleset_version,
        flags={flag.key: flag_ruleset},
        segments=segments_map,
    )

    # Build Evaluation Trace
    trace: list[RuleTraceItem] = []

    if not setting.enabled:
        trace.append(
            RuleTraceItem(
                description="Flag is disabled in this environment",
                matched=False,
                reason="DISABLED",
            )
        )
    else:
        # Check override
        bucketing_attr = setting.bucketing_key or "targetingKey"
        bucketing_value = str(eval_ctx.get(bucketing_attr, eval_ctx.targeting_key))
        matching_override = flag_ruleset.get_override(bucketing_value)
        if matching_override:
            trace.append(
                RuleTraceItem(
                    description=f"Individual override matched for '{bucketing_value}'",
                    matched=True,
                    reason="OVERRIDE_MATCH",
                )
            )
        else:
            # Check rules
            rule_matched = False
            for rule in engine_rules:
                is_match = match_condition_group(rule.conditions, eval_ctx, segments=segments_map)
                if is_match:
                    trace.append(
                        RuleTraceItem(
                            rule_id=str(rule.id),
                            priority=rule.priority,
                            description=rule.description,
                            matched=True,
                            reason="Conditions matched",
                        )
                    )
                    rule_matched = True
                    break
                else:
                    trace.append(
                        RuleTraceItem(
                            rule_id=str(rule.id),
                            priority=rule.priority,
                            description=rule.description,
                            matched=False,
                            reason="Conditions did not match",
                        )
                    )

            if not rule_matched:
                trace.append(
                    RuleTraceItem(
                        description="No rules matched, fell back to default variation",
                        matched=False,
                        reason="DEFAULT_FALLBACK",
                    )
                )

    # Perform evaluation
    eval_res = engine_evaluate(ruleset, eval_ctx, flag.key, default_value=None)

    return SimulateResponse(
        flag_key=flag.key,
        value=eval_res.value,
        variant=eval_res.variant,
        reason=str(eval_res.reason.value if hasattr(eval_res.reason, "value") else eval_res.reason),
        matched_rule_id=eval_res.flag_metadata.get("matched_rule_id")
        if eval_res.flag_metadata
        else None,
        matched_rule_description=eval_res.flag_metadata.get("matched_rule_description")
        if eval_res.flag_metadata
        else None,
        trace=trace,
    )
