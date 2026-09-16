"""Unit tests for Condition Matcher (AND/OR Condition Tree and Segment Resolution)."""

import pytest

from app.engine.matcher import (
    ConditionDepthExceeded,
    SegmentDepthExceeded,
    match_condition_group,
)
from app.engine.types import Condition, ConditionGroup, EvaluationContext

# ============================================================================
# 1. BASIC CONDITION MATCHING
# ============================================================================


def test_matcher_single_condition_match() -> None:
    cond = Condition(attribute="country", operator="EQ", value="VN")
    group = ConditionGroup(operator="AND", conditions=[cond])
    ctx = EvaluationContext(attributes={"country": "VN"})

    assert match_condition_group(group, ctx) is True


def test_matcher_single_condition_mismatch() -> None:
    cond = Condition(attribute="country", operator="EQ", value="VN")
    group = ConditionGroup(operator="AND", conditions=[cond])
    ctx = EvaluationContext(attributes={"country": "US"})

    assert match_condition_group(group, ctx) is False


def test_matcher_missing_attribute_evaluates_false() -> None:
    cond = Condition(attribute="non_existent", operator="EQ", value="VN")
    group = ConditionGroup(operator="AND", conditions=[cond])
    ctx = EvaluationContext(attributes={"country": "VN"})

    assert match_condition_group(group, ctx) is False


# ============================================================================
# 2. AND / OR LOGIC
# ============================================================================


def test_matcher_and_logic() -> None:
    cond1 = Condition(attribute="country", operator="EQ", value="VN")
    cond2 = Condition(attribute="age", operator="GTE", value=18)
    group = ConditionGroup(operator="AND", conditions=[cond1, cond2])

    ctx_vn_20 = EvaluationContext(attributes={"country": "VN", "age": 20})
    ctx_vn_16 = EvaluationContext(attributes={"country": "VN", "age": 16})
    ctx_us_20 = EvaluationContext(attributes={"country": "US", "age": 20})

    assert match_condition_group(group, ctx_vn_20) is True
    assert match_condition_group(group, ctx_vn_16) is False
    assert match_condition_group(group, ctx_us_20) is False

    # Empty AND group defaults to True
    empty_and = ConditionGroup(operator="AND", conditions=[])
    assert match_condition_group(empty_and, EvaluationContext()) is True


def test_matcher_or_logic() -> None:
    cond1 = Condition(attribute="tier", operator="EQ", value="gold")
    cond2 = Condition(attribute="tier", operator="EQ", value="platinum")
    group = ConditionGroup(operator="OR", conditions=[cond1, cond2])

    assert match_condition_group(group, EvaluationContext(attributes={"tier": "gold"})) is True
    assert match_condition_group(group, EvaluationContext(attributes={"tier": "platinum"})) is True
    assert match_condition_group(group, EvaluationContext(attributes={"tier": "silver"})) is False

    # Empty OR group defaults to False
    empty_or = ConditionGroup(operator="OR", conditions=[])
    assert match_condition_group(empty_or, EvaluationContext()) is False


# ============================================================================
# 3. NESTED CONDITION TREE (3 LEVELS)
# ============================================================================


def test_matcher_three_level_nested_tree() -> None:
    """AND( country == 'VN', OR( tier == 'gold', AND( age >= 18, loyalty > 5 ) ) )"""
    level_3_and = ConditionGroup(
        operator="AND",
        conditions=[
            Condition(attribute="age", operator="GTE", value=18),
            Condition(attribute="loyalty", operator="GT", value=5),
        ],
    )
    level_2_or = ConditionGroup(
        operator="OR",
        conditions=[Condition(attribute="tier", operator="EQ", value="gold")],
        children=[level_3_and],
    )
    root_and = ConditionGroup(
        operator="AND",
        conditions=[Condition(attribute="country", operator="EQ", value="VN")],
        children=[level_2_or],
    )

    # Match via tier == 'gold'
    ctx1 = EvaluationContext(attributes={"country": "VN", "tier": "gold", "age": 15, "loyalty": 0})
    assert match_condition_group(root_and, ctx1) is True

    # Match via age >= 18 and loyalty > 5
    ctx2 = EvaluationContext(
        attributes={"country": "VN", "tier": "silver", "age": 25, "loyalty": 10}
    )
    assert match_condition_group(root_and, ctx2) is True

    # Mismatch country
    ctx3 = EvaluationContext(attributes={"country": "US", "tier": "gold"})
    assert match_condition_group(root_and, ctx3) is False

    # Mismatch inner OR
    ctx4 = EvaluationContext(
        attributes={"country": "VN", "tier": "silver", "age": 25, "loyalty": 2}
    )
    assert match_condition_group(root_and, ctx4) is False


# ============================================================================
# 4. DEPTH LIMIT VALIDATION (MAX DEPTH 5)
# ============================================================================


def test_matcher_depth_exceeded_raises() -> None:
    """A tree with depth > 5 must raise ConditionDepthExceeded."""
    # Build a chain of 6 nested groups
    cond_a = Condition(attribute="a", operator="EQ", value=1)
    node = ConditionGroup(operator="AND", conditions=[cond_a])
    for _ in range(5):
        node = ConditionGroup(operator="AND", children=[node])

    # Total depth is 6 -> must raise
    with pytest.raises(ConditionDepthExceeded, match="depth limit of 5"):
        match_condition_group(node, EvaluationContext(attributes={"a": 1}))


def test_matcher_depth_five_allowed() -> None:
    """A tree with depth exactly 5 must evaluate without error."""
    cond_a = Condition(attribute="a", operator="EQ", value=1)
    node = ConditionGroup(operator="AND", conditions=[cond_a])
    for _ in range(4):
        node = ConditionGroup(operator="AND", children=[node])

    # Total depth is 5 -> allowed
    assert match_condition_group(node, EvaluationContext(attributes={"a": 1})) is True


# ============================================================================
# 5. SEGMENT REFERENCE & RECURSION (IS_ONE_OF_SEGMENT)
# ============================================================================


def test_matcher_segment_reference_matching() -> None:
    """Reference preloaded segment in ruleset."""
    segments = {
        "beta-testers": ConditionGroup(
            operator="AND",
            conditions=[Condition(attribute="role", operator="IN", value=["beta", "qa"])],
        ),
    }

    cond = Condition(attribute="", operator="IS_ONE_OF_SEGMENT", value="beta-testers")
    group = ConditionGroup(operator="AND", conditions=[cond])

    # Matching context
    ctx_beta = EvaluationContext(attributes={"role": "beta"})
    assert match_condition_group(group, ctx_beta, segments=segments) is True

    # Non-matching context
    ctx_user = EvaluationContext(attributes={"role": "user"})
    assert match_condition_group(group, ctx_user, segments=segments) is False


def test_matcher_unknown_segment_returns_false() -> None:
    cond = Condition(attribute="", operator="IS_ONE_OF_SEGMENT", value="non-existent-segment")
    group = ConditionGroup(operator="AND", conditions=[cond])

    assert match_condition_group(group, EvaluationContext(), segments={}) is False
    assert match_condition_group(group, EvaluationContext(), segments=None) is False


def test_matcher_nested_segment_recursion_limit() -> None:
    """Segment referencing another segment up to depth 3 is allowed, > 3 raises."""

    # Build recursive segment references
    def make_seg(target: str) -> ConditionGroup:
        return ConditionGroup(
            operator="AND",
            conditions=[Condition(attribute="", operator="IS_ONE_OF_SEGMENT", value=target)],
        )

    segments = {
        "seg1": make_seg("seg2"),
        "seg2": make_seg("seg3"),
        "seg3": make_seg("seg4"),
        "seg4": ConditionGroup(
            operator="AND",
            conditions=[Condition(attribute="valid", operator="EQ", value=True)],
        ),
    }

    root_cond = Condition(attribute="", operator="IS_ONE_OF_SEGMENT", value="seg1")
    root_group = ConditionGroup(operator="AND", conditions=[root_cond])

    ctx = EvaluationContext(attributes={"valid": True})
    with pytest.raises(SegmentDepthExceeded, match="segment depth limit of 3"):
        match_condition_group(root_group, ctx, segments=segments)


# ============================================================================
# 6. DICT-BASED SPECIFICATION SUPPORT
# ============================================================================


def test_matcher_dict_based_condition_tree() -> None:
    """Ensure raw JSONB dictionary condition trees evaluate identical to dataclasses."""
    raw_dict = {
        "operator": "AND",
        "conditions": [
            {"attribute": "country", "operator": "EQ", "value": "VN"},
        ],
        "children": [
            {
                "operator": "OR",
                "conditions": [
                    {"attribute": "plan", "operator": "EQ", "value": "enterprise"},
                    {"attribute": "credits", "operator": "GT", "value": 100},
                ],
            }
        ],
    }

    ctx_ok = EvaluationContext(attributes={"country": "VN", "plan": "free", "credits": 500})
    assert match_condition_group(raw_dict, ctx_ok) is True

    ctx_fail = EvaluationContext(attributes={"country": "VN", "plan": "free", "credits": 50})
    assert match_condition_group(raw_dict, ctx_fail) is False


def test_matcher_bare_list_conditions() -> None:
    """Ensure bare list of conditions acts as an implicit AND."""
    conds = [
        Condition(attribute="env", operator="EQ", value="prod"),
        Condition(attribute="region", operator="EQ", value="ap-southeast-1"),
    ]
    ctx_match = EvaluationContext(attributes={"env": "prod", "region": "ap-southeast-1"})
    ctx_mismatch = EvaluationContext(attributes={"env": "prod", "region": "us-east-1"})

    assert match_condition_group(conds, ctx_match) is True
    assert match_condition_group(conds, ctx_mismatch) is False
