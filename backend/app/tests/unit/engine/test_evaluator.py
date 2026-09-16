"""Unit tests for Core Evaluator (evaluate() function)."""

from typing import Any

import pytest

from app.engine.bucketing import InvalidDistributionError
from app.engine.evaluator import evaluate
from app.engine.types import (
    Condition,
    ConditionGroup,
    DistributionEntry,
    ErrorCode,
    EvaluationContext,
    FlagRuleset,
    IndividualOverride,
    Reason,
    Ruleset,
    TargetingRule,
    Variation,
)


@pytest.fixture
def sample_variations() -> tuple[Variation, Variation, Variation]:
    on_var = Variation(id="v-on", key="on", value=True)
    off_var = Variation(id="v-off", key="off", value=False)
    special_var = Variation(id="v-special", key="special", value="special-mode")
    return on_var, off_var, special_var


# ============================================================================
# 1. FLAG NOT FOUND & EMPTY RULESET
# ============================================================================


def test_evaluate_flag_not_found_returns_error() -> None:
    ruleset = Ruleset(environment_id="env-1", ruleset_version=42, flags={})
    ctx = EvaluationContext(targeting_key="usr-1")

    res = evaluate(ruleset, ctx, "missing-flag", default_value="my-fallback")

    assert res.flag_key == "missing-flag"
    assert res.value == "my-fallback"
    assert res.variant == ""
    assert res.reason == Reason.ERROR
    assert res.error_code == ErrorCode.FLAG_NOT_FOUND
    assert res.flag_metadata == {"ruleset_version": 42}


# ============================================================================
# 2. DISABLED FLAG
# ============================================================================


def test_evaluate_disabled_flag_returns_off_variation(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, off_var, _ = sample_variations
    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="feature-flag",
        flag_type="BOOLEAN",
        enabled=False,
        default_variation=on_var,
        off_variation=off_var,
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=5, flags={"feature-flag": flag})
    ctx = EvaluationContext(targeting_key="usr-1")

    res = evaluate(ruleset, ctx, "feature-flag", default_value=True)

    assert res.flag_key == "feature-flag"
    assert res.value is False
    assert res.variant == "off"
    assert res.reason == Reason.DISABLED
    assert res.flag_metadata == {"ruleset_version": 5}


def test_evaluate_disabled_flag_none_off_variation_falls_back_to_default(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, _, _ = sample_variations
    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="feature-flag",
        flag_type="BOOLEAN",
        enabled=False,
        default_variation=on_var,
        off_variation=None,
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=1, flags={"feature-flag": flag})
    res = evaluate(ruleset, EvaluationContext(), "feature-flag", default_value="safe-default")

    assert res.value == "safe-default"
    assert res.variant == ""
    assert res.reason == Reason.DISABLED


# ============================================================================
# 3. INDIVIDUAL OVERRIDE WINS OVER RULES
# ============================================================================


def test_evaluate_individual_override_wins_over_rules(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, off_var, special_var = sample_variations

    # Override for user 'vip-user' to receive special_var
    override = IndividualOverride(context_key="vip-user", variation=special_var)

    # Rule priority 1 that would otherwise match everyone
    rule = TargetingRule(
        id="r-1",
        priority=1,
        conditions=ConditionGroup(operator="AND", conditions=[]),
        distribution=[DistributionEntry(variation=off_var, weight=100.0)],
    )

    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="checkout",
        flag_type="STRING",
        enabled=True,
        default_variation=on_var,
        off_variation=off_var,
        overrides=[override],
        rules=[rule],
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=10, flags={"checkout": flag})

    # VIP user matches override
    ctx_vip = EvaluationContext(targeting_key="vip-user")
    res_vip = evaluate(ruleset, ctx_vip, "checkout")

    assert res_vip.value == "special-mode"
    assert res_vip.variant == "special"
    assert res_vip.reason == Reason.TARGETING_MATCH
    assert res_vip.flag_metadata == {"matched": "individual_override", "ruleset_version": 10}

    # Regular user bypasses override and hits Rule 1
    ctx_regular = EvaluationContext(targeting_key="regular-user")
    res_regular = evaluate(ruleset, ctx_regular, "checkout")
    assert res_regular.value is False
    assert res_regular.variant == "off"


# ============================================================================
# 4. RULE PRIORITY ORDER & SHORT-CIRCUIT
# ============================================================================


def test_evaluate_rule_priority_order_and_stops_at_first_match(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, off_var, special_var = sample_variations

    evaluated_attrs: list[str] = []

    class SpyContext(EvaluationContext):
        def get(self, key: str, default: Any = None) -> Any:
            evaluated_attrs.append(key)
            return super().get(key, default)

    # Condition on role
    cond1 = Condition(attribute="role_priority_1", operator="EQ", value="admin")
    cond2 = Condition(attribute="role_priority_2", operator="EQ", value="admin")

    rule_1 = TargetingRule(
        id="r-1",
        priority=1,
        description="Admin rule",
        conditions=ConditionGroup(operator="AND", conditions=[cond1]),
        distribution=[DistributionEntry(variation=special_var, weight=100.0)],
    )
    rule_2 = TargetingRule(
        id="r-2",
        priority=2,
        description="Secondary rule",
        conditions=ConditionGroup(operator="AND", conditions=[cond2]),
        distribution=[DistributionEntry(variation=off_var, weight=100.0)],
    )

    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="admin-feature",
        flag_type="STRING",
        enabled=True,
        default_variation=on_var,
        off_variation=off_var,
        # Intentionally give rules unsorted in the list to verify priority sort ASC
        rules=[rule_2, rule_1],
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=7, flags={"admin-feature": flag})

    ctx = SpyContext(targeting_key="usr-1", attributes={"role_priority_1": "admin"})
    res = evaluate(ruleset, ctx, "admin-feature")

    # Matched Rule 1
    assert res.value == "special-mode"
    assert res.variant == "special"
    assert res.reason == Reason.TARGETING_MATCH
    assert res.flag_metadata == {
        "matched_rule_id": "r-1",
        "matched_rule_description": "Admin rule",
        "ruleset_version": 7,
    }

    # Spy verification: rule 1 was checked, rule 2 was NEVER evaluated
    assert "role_priority_1" in evaluated_attrs
    assert "role_priority_2" not in evaluated_attrs


# ============================================================================
# 5. TARGETING_MATCH VS SPLIT (BUCKETING)
# ============================================================================


def test_evaluate_single_variation_100_weight_returns_targeting_match(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, off_var, _ = sample_variations
    rule = TargetingRule(
        id="r-all",
        priority=1,
        conditions=ConditionGroup(operator="AND", conditions=[]),
        distribution=[DistributionEntry(variation=on_var, weight=100.0)],
    )
    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="flag-100",
        flag_type="BOOLEAN",
        enabled=True,
        default_variation=off_var,
        off_variation=off_var,
        rules=[rule],
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=1, flags={"flag-100": flag})
    res = evaluate(ruleset, EvaluationContext(targeting_key="u1"), "flag-100")

    assert res.value is True
    assert res.variant == "on"
    assert res.reason == Reason.TARGETING_MATCH


def test_evaluate_multi_variation_returns_split(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, off_var, _ = sample_variations
    rule = TargetingRule(
        id="r-split",
        priority=1,
        conditions=ConditionGroup(operator="AND", conditions=[]),
        distribution=[
            DistributionEntry(variation=on_var, weight=50.0),
            DistributionEntry(variation=off_var, weight=50.0),
        ],
    )
    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="flag-split",
        flag_type="BOOLEAN",
        enabled=True,
        default_variation=off_var,
        off_variation=off_var,
        rules=[rule],
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=2, flags={"flag-split": flag})
    res = evaluate(ruleset, EvaluationContext(targeting_key="u1"), "flag-split")

    assert res.variant in ("on", "off")
    assert res.reason == Reason.SPLIT
    assert res.flag_metadata["matched_rule_id"] == "r-split"  # type: ignore


# ============================================================================
# 6. DEFAULT VARIATION WHEN NO RULES MATCH
# ============================================================================


def test_evaluate_default_variation_when_no_rules_match(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, off_var, _ = sample_variations
    # Rule only matches country == 'VN'
    rule = TargetingRule(
        id="r-vn",
        priority=1,
        conditions=ConditionGroup(
            operator="AND",
            conditions=[Condition(attribute="country", operator="EQ", value="VN")],
        ),
        distribution=[DistributionEntry(variation=on_var, weight=100.0)],
    )
    flag = FlagRuleset(
        flag_id="f-1",
        flag_key="flag-geo",
        flag_type="BOOLEAN",
        enabled=True,
        default_variation=off_var,
        off_variation=off_var,
        rules=[rule],
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=3, flags={"flag-geo": flag})

    # Context with country == 'US' does not match rule
    res = evaluate(ruleset, EvaluationContext(attributes={"country": "US"}), "flag-geo")

    assert res.value is False
    assert res.variant == "off"
    assert res.reason == Reason.DEFAULT
    assert res.flag_metadata == {"ruleset_version": 3}


# ============================================================================
# 7. JSON FLAG TYPE OBJECT PRESERVATION
# ============================================================================


def test_evaluate_json_flag_type_preserves_nested_structure() -> None:
    json_config = {
        "theme": "dark",
        "features": ["search", "analytics"],
        "limits": {"max_files": 100, "quota_mb": 2048},
    }
    json_var = Variation(id="v-json", key="dark-tier", value=json_config)

    flag = FlagRuleset(
        flag_id="f-json",
        flag_key="app-config",
        flag_type="JSON",
        enabled=True,
        default_variation=json_var,
        off_variation=json_var,
    )
    ruleset = Ruleset(environment_id="env-1", ruleset_version=9, flags={"app-config": flag})

    res = evaluate(ruleset, EvaluationContext(targeting_key="usr-1"), "app-config")

    assert res.value == json_config
    assert res.value["limits"]["max_files"] == 100
    assert res.variant == "dark-tier"
    assert res.reason == Reason.DEFAULT


# ============================================================================
# 8. INVALID DISTRIBUTION WEIGHT IN RULE RAISES
# ============================================================================


def test_evaluate_invalid_distribution_weight_raises(
    sample_variations: tuple[Variation, Variation, Variation],
) -> None:
    on_var, _, _ = sample_variations
    invalid_rule = TargetingRule(
        id="r-bad",
        priority=1,
        conditions=ConditionGroup(operator="AND", conditions=[]),
        distribution=[DistributionEntry(variation=on_var, weight=80.0)],  # sum != 100
    )
    flag = FlagRuleset(
        flag_id="f-bad",
        flag_key="bad-flag",
        flag_type="BOOLEAN",
        enabled=True,
        default_variation=on_var,
        off_variation=on_var,
        rules=[invalid_rule],
    )
    ruleset = Ruleset(environment_id="env-1", flags={"bad-flag": flag})

    with pytest.raises(InvalidDistributionError, match="equal 100"):
        evaluate(ruleset, EvaluationContext(targeting_key="usr-1"), "bad-flag")
