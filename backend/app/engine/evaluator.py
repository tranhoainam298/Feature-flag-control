"""Core Evaluation Engine for FlagOps.

Strictly adheres to evaluation-engine-purity rules:
- Pure synchronous function, zero I/O, no DB/cache/network access.
- Deterministic and portable across Server, Relay Proxy, and Python SDK.
- Mandatory evaluation order:
  1. FLAG_NOT_FOUND  -> default_value, ERROR
  2. DISABLED        -> off_variation, DISABLED
  3. OVERRIDE        -> individual override match, TARGETING_MATCH
  4. RULES           -> first matching rule by priority ASC stops immediately:
                        - single variation (weight 100) -> TARGETING_MATCH
                        - multiple variations          -> MurmurHash3 bucket -> SPLIT
  5. DEFAULT         -> default_variation, DEFAULT
"""

from typing import Any

from app.engine.bucketing import bucket
from app.engine.matcher import match_condition_group
from app.engine.types import (
    ErrorCode,
    EvaluationContext,
    EvaluationResult,
    Reason,
    Ruleset,
)


def evaluate(
    ruleset: Ruleset,
    context: EvaluationContext,
    flag_key: str,
    default_value: Any = None,
) -> EvaluationResult:
    """Evaluate a feature flag deterministically against an in-memory Ruleset.

    Args:
        ruleset: Pre-loaded compiled ruleset for the environment.
        context: User/device evaluation context.
        flag_key: Key of the feature flag to evaluate.
        default_value: Fallback value if flag is not found or error occurs.

    Returns:
        EvaluationResult containing flag_key, value, variant, reason, error_code,
        and flag_metadata.
    """
    flag_setting = ruleset.get_flag(flag_key)

    # 1. Flag not found in ruleset
    if flag_setting is None:
        return EvaluationResult(
            flag_key=flag_key,
            value=default_value,
            variant="",
            reason=Reason.ERROR,
            error_code=ErrorCode.FLAG_NOT_FOUND,
            flag_metadata={"ruleset_version": ruleset.ruleset_version},
        )

    # 2. Flag is disabled in environment
    if not flag_setting.enabled:
        off_var = flag_setting.off_variation
        val = off_var.value if off_var is not None else default_value
        var_key = off_var.key if off_var is not None else ""
        return EvaluationResult(
            flag_key=flag_key,
            value=val,
            variant=var_key,
            reason=Reason.DISABLED,
            flag_metadata={"ruleset_version": ruleset.ruleset_version},
        )

    # Determine context value for bucketing/override
    bucketing_attr = flag_setting.bucketing_key or "targetingKey"
    bucketing_value = str(context.get(bucketing_attr, context.targeting_key))

    # 3. Individual override
    override = flag_setting.get_override(bucketing_value)
    if override is not None:
        return EvaluationResult(
            flag_key=flag_key,
            value=override.variation.value,
            variant=override.variation.key,
            reason=Reason.TARGETING_MATCH,
            flag_metadata={
                "matched": "individual_override",
                "ruleset_version": ruleset.ruleset_version,
            },
        )

    # 4. Targeting rules evaluated by priority ASC
    rules_sorted = sorted(flag_setting.rules, key=lambda r: r.priority)
    for rule in rules_sorted:
        if match_condition_group(rule.conditions, context, segments=ruleset.segments):
            # First matching rule wins: STOP IMMEDIATELY
            if len(rule.distribution) == 1 and rule.distribution[0].weight == 100.0:
                var = rule.distribution[0].variation
                reason = Reason.TARGETING_MATCH
            else:
                var = bucket(bucketing_value, flag_key, str(rule.id), rule.distribution)
                reason = Reason.SPLIT

            return EvaluationResult(
                flag_key=flag_key,
                value=var.value,
                variant=var.key,
                reason=reason,
                flag_metadata={
                    "matched_rule_id": str(rule.id),
                    "matched_rule_description": rule.description,
                    "ruleset_version": ruleset.ruleset_version,
                },
            )

    # 5. Default variation when no rules match
    def_var = flag_setting.default_variation
    val = def_var.value if def_var is not None else default_value
    var_key = def_var.key if def_var is not None else ""

    return EvaluationResult(
        flag_key=flag_key,
        value=val,
        variant=var_key,
        reason=Reason.DEFAULT,
        flag_metadata={"ruleset_version": ruleset.ruleset_version},
    )
