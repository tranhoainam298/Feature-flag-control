"""Unit tests for Evaluation Engine: Types and 22 Operators."""

import time
from decimal import Decimal

from app.engine.operators import OPERATORS, apply_operator
from app.engine.types import (
    Condition,
    ConditionGroup,
    ErrorCode,
    EvaluationContext,
    EvaluationResult,
    FlagRuleset,
    IndividualOverride,
    Reason,
    Ruleset,
    TargetingRule,
    Variation,
)

# ============================================================================
# 1. TEST TYPES
# ============================================================================


def test_engine_types_dataclasses() -> None:
    """Verify engine types are frozen dataclasses and enums."""
    # Reason Enum check
    assert Reason.TARGETING_MATCH.value == "TARGETING_MATCH"
    assert Reason.SPLIT.value == "SPLIT"
    assert Reason.DEFAULT.value == "DEFAULT"
    assert Reason.DISABLED.value == "DISABLED"
    assert Reason.ERROR.value == "ERROR"
    assert Reason.STATIC.value == "STATIC"
    assert Reason.CACHED.value == "CACHED"
    assert len(Reason) == 7

    # ErrorCode Enum check
    assert ErrorCode.FLAG_NOT_FOUND.value == "FLAG_NOT_FOUND"

    # EvaluationContext
    ctx = EvaluationContext(targeting_key="usr_123", attributes={"country": "VN", "age": 25})
    assert ctx.targeting_key == "usr_123"
    assert ctx.get("country") == "VN"
    assert ctx.get("age") == 25
    assert ctx.get("missing", "default_val") == "default_val"
    assert ctx.get("targetingKey") == "usr_123"
    assert ctx.get("targeting_key") == "usr_123"

    # Variation & Result
    var_on = Variation(key="on", value=True)
    var_off = Variation(key="off", value=False)
    res = EvaluationResult(value=True, variant="on", reason=Reason.TARGETING_MATCH)
    assert res.value is True
    assert res.variant == "on"
    assert res.reason == Reason.TARGETING_MATCH

    # Condition & Group
    cond = Condition(attribute="country", operator="EQ", value="VN")
    group = ConditionGroup(operator="AND", conditions=[cond])
    assert group.operator == "AND"
    assert len(group.conditions) == 1

    # TargetingRule & Override
    rule = TargetingRule(id="r1", priority=1, conditions=group)
    override = IndividualOverride(context_key="usr_123", variation=var_on)
    flag_rs = FlagRuleset(
        flag_id="f1",
        flag_key="my-flag",
        flag_type="BOOLEAN",
        enabled=True,
        default_variation=var_on,
        off_variation=var_off,
        variations=[var_on, var_off],
        rules=[rule],
        overrides=[override],
    )
    ruleset = Ruleset(environment_id="env_1", ruleset_version=1, flags={"my-flag": flag_rs})
    assert ruleset.get_flag("my-flag") == flag_rs
    assert ruleset.get_flag("unknown") is None


# ============================================================================
# 2. TEST 22 OPERATORS — 3 CASES PER OPERATOR (MATCH / NO MATCH / MISSING)
# ============================================================================


# --- 1. EQ ---
def test_op_eq_match() -> None:
    assert apply_operator("EQ", "admin", "admin") is True
    assert apply_operator("EQ", 100, 100) is True
    assert apply_operator("EQ", 100, "100") is True
    assert apply_operator("EQ", True, True) is True


def test_op_eq_no_match() -> None:
    assert apply_operator("EQ", "user", "admin") is False
    assert apply_operator("EQ", 100, 200) is False
    assert apply_operator("EQ", True, False) is False
    assert apply_operator("EQ", True, 1) is False  # bool vs number strictness


def test_op_eq_missing() -> None:
    assert apply_operator("EQ", None, "admin") is False
    assert apply_operator("EQ", None, None) is False


# --- 2. NEQ ---
def test_op_neq_match() -> None:
    assert apply_operator("NEQ", "user", "admin") is True
    assert apply_operator("NEQ", 100, 200) is True


def test_op_neq_no_match() -> None:
    assert apply_operator("NEQ", "admin", "admin") is False
    assert apply_operator("NEQ", 100, 100) is False
    assert apply_operator("NEQ", 100, "100") is False


def test_op_neq_missing() -> None:
    assert apply_operator("NEQ", None, "admin") is False


# --- 3. GT ---
def test_op_gt_match() -> None:
    assert apply_operator("GT", 25, 18) is True
    assert apply_operator("GT", "25.5", 18.2) is True
    assert apply_operator("GT", Decimal("10.01"), Decimal("10.00")) is True


def test_op_gt_no_match() -> None:
    assert apply_operator("GT", 18, 25) is False
    assert apply_operator("GT", 18, 18) is False
    assert apply_operator("GT", "not_a_number", 18) is False


def test_op_gt_missing() -> None:
    assert apply_operator("GT", None, 18) is False


# --- 4. GTE ---
def test_op_gte_match() -> None:
    assert apply_operator("GTE", 25, 18) is True
    assert apply_operator("GTE", 18, 18) is True
    assert apply_operator("GTE", "18.0", 18) is True


def test_op_gte_no_match() -> None:
    assert apply_operator("GTE", 17, 18) is False
    assert apply_operator("GTE", "xyz", 18) is False


def test_op_gte_missing() -> None:
    assert apply_operator("GTE", None, 18) is False


# --- 5. LT ---
def test_op_lt_match() -> None:
    assert apply_operator("LT", 15, 18) is True
    assert apply_operator("LT", "17.9", 18) is True


def test_op_lt_no_match() -> None:
    assert apply_operator("LT", 18, 18) is False
    assert apply_operator("LT", 25, 18) is False
    assert apply_operator("LT", "abc", 18) is False


def test_op_lt_missing() -> None:
    assert apply_operator("LT", None, 18) is False


# --- 6. LTE ---
def test_op_lte_match() -> None:
    assert apply_operator("LTE", 15, 18) is True
    assert apply_operator("LTE", 18, 18) is True
    assert apply_operator("LTE", "18", 18) is True


def test_op_lte_no_match() -> None:
    assert apply_operator("LTE", 19, 18) is False
    assert apply_operator("LTE", "invalid", 18) is False


def test_op_lte_missing() -> None:
    assert apply_operator("LTE", None, 18) is False


# --- 7. IN ---
def test_op_in_match() -> None:
    assert apply_operator("IN", "VN", ["VN", "SG", "MY"]) is True
    assert apply_operator("IN", 42, [1, 2, 42]) is True
    assert apply_operator("IN", "42", [1, 2, 42]) is True


def test_op_in_no_match() -> None:
    assert apply_operator("IN", "US", ["VN", "SG", "MY"]) is False
    assert apply_operator("IN", 99, [1, 2, 42]) is False


def test_op_in_missing() -> None:
    assert apply_operator("IN", None, ["VN", "SG"]) is False


# --- 8. NOT_IN ---
def test_op_not_in_match() -> None:
    assert apply_operator("NOT_IN", "US", ["VN", "SG", "MY"]) is True
    assert apply_operator("NOT_IN", 99, [1, 2, 42]) is True


def test_op_not_in_no_match() -> None:
    assert apply_operator("NOT_IN", "VN", ["VN", "SG", "MY"]) is False
    assert apply_operator("NOT_IN", 42, [1, 2, 42]) is False


def test_op_not_in_missing() -> None:
    assert apply_operator("NOT_IN", None, ["VN", "SG"]) is False


# --- 9. CONTAINS ---
def test_op_contains_match() -> None:
    assert apply_operator("CONTAINS", "flagops-team@company.com", "company.com") is True
    assert apply_operator("CONTAINS", "super-admin", "admin") is True


def test_op_contains_no_match() -> None:
    assert apply_operator("CONTAINS", "user@gmail.com", "company.com") is False


def test_op_contains_missing() -> None:
    assert apply_operator("CONTAINS", None, "company.com") is False


# --- 10. NOT_CONTAINS ---
def test_op_not_contains_match() -> None:
    assert apply_operator("NOT_CONTAINS", "user@gmail.com", "company.com") is True


def test_op_not_contains_no_match() -> None:
    assert apply_operator("NOT_CONTAINS", "flagops-team@company.com", "company.com") is False


def test_op_not_contains_missing() -> None:
    assert apply_operator("NOT_CONTAINS", None, "company.com") is False


# --- 11. STARTS_WITH ---
def test_op_starts_with_match() -> None:
    assert apply_operator("STARTS_WITH", "prod-api-server", "prod-") is True


def test_op_starts_with_no_match() -> None:
    assert apply_operator("STARTS_WITH", "staging-api-server", "prod-") is False


def test_op_starts_with_missing() -> None:
    assert apply_operator("STARTS_WITH", None, "prod-") is False


# --- 12. ENDS_WITH ---
def test_op_ends_with_match() -> None:
    assert apply_operator("ENDS_WITH", "user@gmail.com", "@gmail.com") is True


def test_op_ends_with_no_match() -> None:
    assert apply_operator("ENDS_WITH", "user@yahoo.com", "@gmail.com") is False


def test_op_ends_with_missing() -> None:
    assert apply_operator("ENDS_WITH", None, "@gmail.com") is False


# --- 13. MATCHES_REGEX ---
def test_op_matches_regex_match() -> None:
    assert apply_operator("MATCHES_REGEX", "user_12345", r"^user_\d+$") is True


def test_op_matches_regex_no_match() -> None:
    assert apply_operator("MATCHES_REGEX", "user_abc", r"^user_\d+$") is False
    assert apply_operator("MATCHES_REGEX", "invalid", r"[") is False  # invalid regex syntax


def test_op_matches_regex_missing() -> None:
    assert apply_operator("MATCHES_REGEX", None, r"^user_\d+$") is False


# --- 14. NOT_MATCHES_REGEX ---
def test_op_not_matches_regex_match() -> None:
    assert apply_operator("NOT_MATCHES_REGEX", "admin_123", r"^user_\d+$") is True


def test_op_not_matches_regex_no_match() -> None:
    assert apply_operator("NOT_MATCHES_REGEX", "user_123", r"^user_\d+$") is False


def test_op_not_matches_regex_missing() -> None:
    assert apply_operator("NOT_MATCHES_REGEX", None, r"^user_\d+$") is False


# --- 15. SEMVER_EQ ---
def test_op_semver_eq_match() -> None:
    assert apply_operator("SEMVER_EQ", "1.2.3", "1.2.3") is True
    assert apply_operator("SEMVER_EQ", "v1.2.3", "1.2.3") is True


def test_op_semver_eq_no_match() -> None:
    assert apply_operator("SEMVER_EQ", "1.2.3", "1.2.4") is False
    assert apply_operator("SEMVER_EQ", "invalid_ver", "1.2.4") is False


def test_op_semver_eq_missing() -> None:
    assert apply_operator("SEMVER_EQ", None, "1.2.3") is False


# --- 16. SEMVER_NEQ ---
def test_op_semver_neq_match() -> None:
    assert apply_operator("SEMVER_NEQ", "1.2.3", "1.2.4") is True


def test_op_semver_neq_no_match() -> None:
    assert apply_operator("SEMVER_NEQ", "1.2.3", "1.2.3") is False


def test_op_semver_neq_missing() -> None:
    assert apply_operator("SEMVER_NEQ", None, "1.2.3") is False


# --- 17. SEMVER_GT ---
def test_op_semver_gt_match() -> None:
    assert apply_operator("SEMVER_GT", "2.0.0", "1.9.9") is True
    assert apply_operator("SEMVER_GT", "1.10.0", "1.9.0") is True


def test_op_semver_gt_no_match() -> None:
    assert apply_operator("SEMVER_GT", "1.0.0", "2.0.0") is False
    assert apply_operator("SEMVER_GT", "2.0.0", "2.0.0") is False
    assert apply_operator("SEMVER_GT", "invalid", "1.0.0") is False


def test_op_semver_gt_missing() -> None:
    assert apply_operator("SEMVER_GT", None, "1.0.0") is False


# --- 18. SEMVER_GTE ---
def test_op_semver_gte_match() -> None:
    assert apply_operator("SEMVER_GTE", "2.0.0", "1.9.9") is True
    assert apply_operator("SEMVER_GTE", "2.0.0", "2.0.0") is True


def test_op_semver_gte_no_match() -> None:
    assert apply_operator("SEMVER_GTE", "1.9.9", "2.0.0") is False


def test_op_semver_gte_missing() -> None:
    assert apply_operator("SEMVER_GTE", None, "2.0.0") is False


# --- 19. SEMVER_LT ---
def test_op_semver_lt_match() -> None:
    assert apply_operator("SEMVER_LT", "1.9.9", "2.0.0") is True


def test_op_semver_lt_no_match() -> None:
    assert apply_operator("SEMVER_LT", "2.0.0", "1.9.9") is False
    assert apply_operator("SEMVER_LT", "2.0.0", "2.0.0") is False


def test_op_semver_lt_missing() -> None:
    assert apply_operator("SEMVER_LT", None, "2.0.0") is False


# --- 20. SEMVER_LTE ---
def test_op_semver_lte_match() -> None:
    assert apply_operator("SEMVER_LTE", "1.9.9", "2.0.0") is True
    assert apply_operator("SEMVER_LTE", "2.0.0", "2.0.0") is True


def test_op_semver_lte_no_match() -> None:
    assert apply_operator("SEMVER_LTE", "2.0.1", "2.0.0") is False


def test_op_semver_lte_missing() -> None:
    assert apply_operator("SEMVER_LTE", None, "2.0.0") is False


# --- 21. EXISTS ---
def test_op_exists_match() -> None:
    assert apply_operator("EXISTS", "user_123", None) is True
    assert apply_operator("EXISTS", 0, None) is True
    assert apply_operator("EXISTS", False, None) is True


def test_op_exists_no_match() -> None:
    assert apply_operator("EXISTS", None, None) is False


def test_op_exists_missing() -> None:
    assert apply_operator("EXISTS", None, True) is False


# --- 22. NOT_EXISTS ---
def test_op_not_exists_match() -> None:
    assert apply_operator("NOT_EXISTS", None, None) is True


def test_op_not_exists_no_match() -> None:
    assert apply_operator("NOT_EXISTS", "any_value", None) is False
    assert apply_operator("NOT_EXISTS", 0, None) is False
    assert apply_operator("NOT_EXISTS", False, None) is False


def test_op_not_exists_missing() -> None:
    # When context property is missing/None, NOT_EXISTS must be True
    assert apply_operator("NOT_EXISTS", None, True) is True


# ============================================================================
# 3. REDOS & TOXIC REGEX TIMEOUT TEST (< 200ms, NO HANG)
# ============================================================================


def test_toxic_regex_timeout_under_200ms() -> None:
    """Test catastrophic backtracking regex '(a+)+$' on 50 'a's.

    Must not hang and must finish < 200ms.
    """
    toxic_pattern = r"(a+)+$"
    toxic_input_50 = "a" * 50

    start_time = time.perf_counter()
    # Should evaluate safely without hanging
    result_match = apply_operator("MATCHES_REGEX", toxic_input_50, toxic_pattern)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert elapsed_ms < 200.0, f"Toxic regex took {elapsed_ms}ms, exceeding 200ms limit!"
    # With matching input it matches quickly
    assert result_match is True

    # With non-matching input (catastrophic backtracking trigger in standard engines)
    toxic_input_backtrack = "a" * 30 + "!"
    start_time = time.perf_counter()
    result_nomatch = apply_operator("MATCHES_REGEX", toxic_input_backtrack, toxic_pattern)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert elapsed_ms < 200.0, f"Toxic regex backtrack took {elapsed_ms}ms, exceeding 200ms limit!"
    assert result_nomatch is False


# ============================================================================
# 4. DISPATCH TABLE & GENERAL EDGE CASES
# ============================================================================


def test_unknown_operator_returns_false() -> None:
    assert apply_operator("UNKNOWN_OP", "val", "rule_val") is False


def test_operator_dispatch_table_contains_all_22() -> None:
    expected_operators = {
        "EQ",
        "NEQ",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "IN",
        "NOT_IN",
        "CONTAINS",
        "NOT_CONTAINS",
        "STARTS_WITH",
        "ENDS_WITH",
        "MATCHES_REGEX",
        "NOT_MATCHES_REGEX",
        "SEMVER_EQ",
        "SEMVER_NEQ",
        "SEMVER_GT",
        "SEMVER_GTE",
        "SEMVER_LT",
        "SEMVER_LTE",
        "EXISTS",
        "NOT_EXISTS",
    }
    assert expected_operators.issubset(set(OPERATORS.keys()))
    assert len(expected_operators) == 22


def test_edge_cases_and_invalid_inputs() -> None:
    """Test helper edge cases for 100% branch coverage."""
    # Empty or None operator string
    assert apply_operator("", "val", "rule") is False
    assert apply_operator(None, "val", "rule") is False  # type: ignore

    # IN / NOT_IN with scalar rule value
    assert apply_operator("IN", "test", "test") is True
    assert apply_operator("IN", 123, 123) is True
    assert apply_operator("IN", "test", "other") is False
    assert apply_operator("NOT_IN", "test", "other") is True

    # Semver invalid version on comparison
    assert apply_operator("SEMVER_NEQ", "invalid_ver", "1.0.0") is False
    assert apply_operator("SEMVER_GTE", "invalid_ver", "1.0.0") is False
    assert apply_operator("SEMVER_LT", "1.0.0", "invalid_ver") is False
    assert apply_operator("SEMVER_LTE", "invalid_ver", "1.0.0") is False
    assert apply_operator("SEMVER_EQ", True, "1.0.0") is False

    from app.engine.operators import _to_decimal, _to_version

    assert _to_decimal(None) is None
    assert _to_version(None) is None
