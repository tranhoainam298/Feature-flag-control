"""Engine unit tests executed directly against flagops.engine package."""

from decimal import Decimal
import pytest

from flagops.engine.bucketing import InvalidDistributionError, bucket
from flagops.engine.evaluator import evaluate
from flagops.engine.matcher import (
    ConditionDepthExceeded,
    SegmentDepthExceeded,
    match_condition_group,
)
from flagops.engine.operators import OPERATORS, apply_operator
from flagops.engine.types import (
    Condition,
    ConditionGroup,
    DistributionEntry,
    ErrorCode,
    EvaluationContext,
    EvaluationResult,
    FlagRuleset,
    IndividualOverride,
    Operator,
    Reason,
    Ruleset,
    TargetingRule,
    Variation,
)


def test_operators_all_22():
    """Verify all 22 condition operators in flagops.engine."""
    # Comparisons
    assert apply_operator("EQ", 10, 10) is True
    assert apply_operator("EQ", 10, 20) is False
    assert apply_operator("NEQ", 10, 20) is True
    assert apply_operator("GT", 20, 10) is True
    assert apply_operator("GTE", 10, 10) is True
    assert apply_operator("LT", 5, 10) is True
    assert apply_operator("LTE", 10, 10) is True

    # Collections
    assert apply_operator("IN", "a", ["a", "b"]) is True
    assert apply_operator("IN", "c", ["a", "b"]) is False
    assert apply_operator("NOT_IN", "c", ["a", "b"]) is True
    assert apply_operator("CONTAINS", "hello world", "world") is True
    assert apply_operator("NOT_CONTAINS", "hello world", "planet") is True

    # String & Regex
    assert apply_operator("STARTS_WITH", "prefix_123", "prefix") is True
    assert apply_operator("ENDS_WITH", "123_suffix", "suffix") is True
    assert apply_operator("MATCHES_REGEX", "user@flagops.io", r"^[\w\.-]+@[\w\.-]+\.\w+$") is True
    assert apply_operator("NOT_MATCHES_REGEX", "bad-email", r"^[\w\.-]+@[\w\.-]+\.\w+$") is True

    # Semver
    assert apply_operator("SEMVER_EQ", "1.2.0", "1.2.0") is True
    assert apply_operator("SEMVER_NEQ", "1.2.0", "1.3.0") is True
    assert apply_operator("SEMVER_GT", "2.0.0", "1.9.9") is True
    assert apply_operator("SEMVER_GTE", "2.0.0", "2.0.0") is True
    assert apply_operator("SEMVER_LT", "1.0.0", "1.0.1") is True
    assert apply_operator("SEMVER_LTE", "1.0.0", "1.0.0") is True

    # Existence
    assert apply_operator("EXISTS", "val", None) is True
    assert apply_operator("EXISTS", None, None) is False
    assert apply_operator("NOT_EXISTS", None, None) is True
    assert apply_operator("NOT_EXISTS", "val", None) is False

    # Edge cases
    assert apply_operator("UNKNOWN_OP", 1, 1) is False
    assert apply_operator("", 1, 1) is False
    assert apply_operator("EQ", None, 1) is False


def test_bucketing_distribution_and_validation():
    """Verify bucketing algorithm and distribution validation."""
    var_a = Variation(id="v-a", key="a", value="A")
    var_b = Variation(id="v-b", key="b", value="B")

    dist = [
        DistributionEntry(variation=var_a, weight=50.0),
        DistributionEntry(variation=var_b, weight=50.0),
    ]

    # Determinism
    r1 = bucket("user-123", "feature-x", "rule-1", dist)
    r2 = bucket("user-123", "feature-x", "rule-1", dist)
    assert r1 == r2

    # Validation errors
    with pytest.raises(InvalidDistributionError):
        bucket("u", "f", "r", [])

    with pytest.raises(InvalidDistributionError):
        bucket("u", "f", "r", [DistributionEntry(variation=var_a, weight=-10.0)])

    with pytest.raises(InvalidDistributionError):
        bucket("u", "f", "r", [DistributionEntry(variation=var_a, weight=70.0)])


def test_matcher_trees_and_recursion_limits():
    """Verify condition matcher logic, nesting and depth protection."""
    ctx = EvaluationContext(targeting_key="u1", attributes={"country": "VN", "age": 25})

    group_and = ConditionGroup(
        operator="AND",
        conditions=[
            Condition(attribute="country", operator="EQ", value="VN"),
            Condition(attribute="age", operator="GTE", value="18"),
        ],
    )
    assert match_condition_group(group_and, ctx) is True

    group_or = ConditionGroup(
        operator="OR",
        conditions=[
            Condition(attribute="country", operator="EQ", value="US"),
            Condition(attribute="country", operator="EQ", value="VN"),
        ],
    )
    assert match_condition_group(group_or, ctx) is True

    # Depth limit exceeded (> 5)
    deep_group = ConditionGroup(operator="AND", conditions=[])
    curr = deep_group
    for _ in range(6):
        child = ConditionGroup(operator="AND", conditions=[])
        curr.children.append(child)
        curr = child

    with pytest.raises(ConditionDepthExceeded):
        match_condition_group(deep_group, ctx)


def test_evaluator_order_of_precedence():
    """Verify strict evaluator precedence: DISABLED -> OVERRIDE -> RULE -> DEFAULT."""
    v_on = Variation(id="v-on", key="on", value=True)
    v_off = Variation(id="v-off", key="off", value=False)

    flag = FlagRuleset(
        flag_id="f1",
        flag_key="flag-1",
        flag_type="BOOLEAN",
        enabled=True,
        default_variation=v_off,
        off_variation=v_off,
        variations=[v_on, v_off],
        overrides=[IndividualOverride(context_key="override-user", variation=v_on)],
        rules=[
            TargetingRule(
                id="r1",
                priority=1,
                conditions=[Condition(attribute="role", operator="EQ", value="admin")],
                distribution=[DistributionEntry(variation=v_on, weight=100.0)],
            )
        ],
    )
    ruleset = Ruleset(environment_id="e1", ruleset_version=1, flags={"flag-1": flag})

    # 1. Override
    res_ov = evaluate(ruleset, EvaluationContext(targeting_key="override-user"), "flag-1")
    assert res_ov.value is True
    assert res_ov.reason == Reason.TARGETING_MATCH

    # 2. Rule
    res_rule = evaluate(ruleset, EvaluationContext(targeting_key="u2", attributes={"role": "admin"}), "flag-1")
    assert res_rule.value is True
    assert res_rule.reason == Reason.TARGETING_MATCH

    # 3. Default
    res_def = evaluate(ruleset, EvaluationContext(targeting_key="u3"), "flag-1")
    assert res_def.value is False
    assert res_def.reason == Reason.DEFAULT

    # 4. Disabled
    flag_disabled = FlagRuleset(
        flag_id="f2",
        flag_key="flag-disabled",
        flag_type="BOOLEAN",
        enabled=False,
        default_variation=v_on,
        off_variation=v_off,
    )
    ruleset_disabled = Ruleset(environment_id="e1", ruleset_version=1, flags={"flag-disabled": flag_disabled})
    res_dis = evaluate(ruleset_disabled, EvaluationContext(targeting_key="u1"), "flag-disabled")
    assert res_dis.value is False
    assert res_dis.reason == Reason.DISABLED
