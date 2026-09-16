"""22 Pure Condition Operators for Evaluation Engine.

Pure computation rules:
- No I/O, no DB, no Redis, no network, no FastAPI imports.
- Missing attribute in context -> returns False (NOT_EXISTS returns True). Never raises.
- Numeric comparisons cast to Decimal.
- Semver comparisons use packaging.version.Version.
- MATCHES_REGEX enforces a strict 50ms timeout via regex C-level timeout.
- Operators resolved via dispatch table (dict mapping operator -> function).
"""

from collections.abc import Callable, Collection
from decimal import Decimal, InvalidOperation
from typing import Any

import regex
from packaging.version import InvalidVersion, Version

REGEX_TIMEOUT_SECONDS: float = 0.05  # 50ms ReDoS timeout


# ============================================================================
# TYPE CONVERSION HELPERS (SAFE, PURE, NEVER RAISE)
# ============================================================================


def _to_decimal(val: Any) -> Decimal | None:
    """Safely convert value to Decimal. Returns None if invalid or boolean."""
    if isinstance(val, bool) or val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_version(val: Any) -> Version | None:
    """Safely convert value to packaging Version. Returns None if invalid."""
    if val is None or isinstance(val, bool):
        return None
    try:
        return Version(str(val).strip())
    except (InvalidVersion, TypeError):
        return None


# ============================================================================
# OPERATOR IMPLEMENTATIONS
# ============================================================================


def op_eq(ctx: Any, rule: Any) -> bool:
    """Equality comparison with safe type coercions."""
    # Strict boolean comparison
    if isinstance(ctx, bool) or isinstance(rule, bool):
        if type(ctx) is not type(rule):
            return False
        return ctx is rule

    # Decimal comparison for numbers/numeric strings
    d_ctx, d_rule = _to_decimal(ctx), _to_decimal(rule)
    if d_ctx is not None and d_rule is not None:
        return d_ctx == d_rule

    return str(ctx) == str(rule)


def op_neq(ctx: Any, rule: Any) -> bool:
    """Inequality comparison."""
    return not op_eq(ctx, rule)


def op_gt(ctx: Any, rule: Any) -> bool:
    """Greater than comparison via Decimal."""
    d_ctx, d_rule = _to_decimal(ctx), _to_decimal(rule)
    if d_ctx is None or d_rule is None:
        return False
    return d_ctx > d_rule


def op_gte(ctx: Any, rule: Any) -> bool:
    """Greater than or equal to comparison via Decimal."""
    d_ctx, d_rule = _to_decimal(ctx), _to_decimal(rule)
    if d_ctx is None or d_rule is None:
        return False
    return d_ctx >= d_rule


def op_lt(ctx: Any, rule: Any) -> bool:
    """Less than comparison via Decimal."""
    d_ctx, d_rule = _to_decimal(ctx), _to_decimal(rule)
    if d_ctx is None or d_rule is None:
        return False
    return d_ctx < d_rule


def op_lte(ctx: Any, rule: Any) -> bool:
    """Less than or equal to comparison via Decimal."""
    d_ctx, d_rule = _to_decimal(ctx), _to_decimal(rule)
    if d_ctx is None or d_rule is None:
        return False
    return d_ctx <= d_rule


def op_in(ctx: Any, rule: Any) -> bool:
    """Check if context value exists in collection rule value."""
    if not isinstance(rule, Collection) or isinstance(rule, (str, bytes)):
        rule_items = [rule]
    else:
        rule_items = list(rule)

    # Check direct containment
    if ctx in rule_items:
        return True

    # Check stringified containment for loose matching
    ctx_str = str(ctx)
    return ctx_str in {str(item) for item in rule_items}


def op_not_in(ctx: Any, rule: Any) -> bool:
    """Check if context value does not exist in collection."""
    return not op_in(ctx, rule)


def op_contains(ctx: Any, rule: Any) -> bool:
    """Check if context string contains rule string."""
    return str(rule) in str(ctx)


def op_not_contains(ctx: Any, rule: Any) -> bool:
    """Check if context string does not contain rule string."""
    return str(rule) not in str(ctx)


def op_starts_with(ctx: Any, rule: Any) -> bool:
    """Check if context string starts with rule string."""
    return str(ctx).startswith(str(rule))


def op_ends_with(ctx: Any, rule: Any) -> bool:
    """Check if context string ends with rule string."""
    return str(ctx).endswith(str(rule))


def op_matches_regex(ctx: Any, rule: Any) -> bool:
    """Regex matching with 50ms ReDoS timeout protection."""
    try:
        compiled = regex.compile(str(rule))
        match = compiled.search(str(ctx), timeout=REGEX_TIMEOUT_SECONDS)
        return match is not None
    except (regex.error, TimeoutError, Exception):
        return False


def op_not_matches_regex(ctx: Any, rule: Any) -> bool:
    """Inverted regex matching with timeout protection."""
    return not op_matches_regex(ctx, rule)


def op_semver_eq(ctx: Any, rule: Any) -> bool:
    """Semver equality comparison."""
    v_ctx, v_rule = _to_version(ctx), _to_version(rule)
    if v_ctx is None or v_rule is None:
        return False
    return v_ctx == v_rule


def op_semver_neq(ctx: Any, rule: Any) -> bool:
    """Semver inequality comparison."""
    v_ctx, v_rule = _to_version(ctx), _to_version(rule)
    if v_ctx is None or v_rule is None:
        return False
    return v_ctx != v_rule


def op_semver_gt(ctx: Any, rule: Any) -> bool:
    """Semver greater than comparison."""
    v_ctx, v_rule = _to_version(ctx), _to_version(rule)
    if v_ctx is None or v_rule is None:
        return False
    return v_ctx > v_rule


def op_semver_gte(ctx: Any, rule: Any) -> bool:
    """Semver greater than or equal to comparison."""
    v_ctx, v_rule = _to_version(ctx), _to_version(rule)
    if v_ctx is None or v_rule is None:
        return False
    return v_ctx >= v_rule


def op_semver_lt(ctx: Any, rule: Any) -> bool:
    """Semver less than comparison."""
    v_ctx, v_rule = _to_version(ctx), _to_version(rule)
    if v_ctx is None or v_rule is None:
        return False
    return v_ctx < v_rule


def op_semver_lte(ctx: Any, rule: Any) -> bool:
    """Semver less than or equal to comparison."""
    v_ctx, v_rule = _to_version(ctx), _to_version(rule)
    if v_ctx is None or v_rule is None:
        return False
    return v_ctx <= v_rule


def op_exists(ctx: Any, _rule: Any) -> bool:
    """Check if context value exists and is not None."""
    return ctx is not None


def op_not_exists(ctx: Any, _rule: Any) -> bool:
    """Check if context value does not exist or is None."""
    return ctx is None


# ============================================================================
# DISPATCH TABLE
# ============================================================================

OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    # 6 Comparison operators
    "EQ": op_eq,
    "NEQ": op_neq,
    "GT": op_gt,
    "GTE": op_gte,
    "LT": op_lt,
    "LTE": op_lte,
    # 4 Collection operators
    "IN": op_in,
    "NOT_IN": op_not_in,
    "CONTAINS": op_contains,
    "NOT_CONTAINS": op_not_contains,
    # 4 String and Regex operators
    "STARTS_WITH": op_starts_with,
    "ENDS_WITH": op_ends_with,
    "MATCHES_REGEX": op_matches_regex,
    "NOT_MATCHES_REGEX": op_not_matches_regex,
    # 6 Semver operators
    "SEMVER_EQ": op_semver_eq,
    "SEMVER_NEQ": op_semver_neq,
    "SEMVER_GT": op_semver_gt,
    "SEMVER_GTE": op_semver_gte,
    "SEMVER_LT": op_semver_lt,
    "SEMVER_LTE": op_semver_lte,
    # 2 Existence operators
    "EXISTS": op_exists,
    "NOT_EXISTS": op_not_exists,
}


def apply_operator(operator: str, context_value: Any, rule_value: Any) -> bool:
    """Dispatch operator evaluation safely.

    - Missing attribute in context (context_value is None) always returns False,
      except for NOT_EXISTS which returns True.
    - Unknown operator returns False.
    - Never raises exceptions.
    """
    if not operator:
        return False

    op_key = operator.strip().upper()
    op_func = OPERATORS.get(op_key)
    if op_func is None:
        return False

    # Enforce missing attribute purity rule
    if context_value is None and op_key != "NOT_EXISTS":
        return False

    return op_func(context_value, rule_value)
