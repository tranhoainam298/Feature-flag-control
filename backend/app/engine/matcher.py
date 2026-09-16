"""Condition Matcher for Evaluation Engine.

Evaluates nested AND/OR condition trees with strict depth limits and
pre-loaded segment reference resolution (zero-I/O).
"""

from typing import Any

from app.engine.operators import apply_operator
from app.engine.types import Condition, ConditionGroup, EvaluationContext


class ConditionDepthExceeded(ValueError):
    """Raised when condition nesting depth exceeds the maximum allowed limit (5)."""

    pass


class SegmentDepthExceeded(ValueError):
    """Raised when segment reference nesting depth exceeds the maximum allowed limit (3)."""

    pass


def _eval_single_condition(
    cond: Condition | dict[str, Any],
    context: EvaluationContext,
    segments: dict[str, Any] | None = None,
    max_depth: int = 5,
    segment_depth: int = 1,
    max_segment_depth: int = 3,
) -> bool:
    """Evaluate a single Condition against the EvaluationContext."""
    if isinstance(cond, dict):
        attr = cond.get("attribute", "")
        op = cond.get("operator", "EQ")
        val = cond.get("value")
    else:
        attr = cond.attribute
        op = cond.operator
        val = cond.value

    op_upper = str(op).strip().upper()

    # Segment reference operator
    if op_upper == "IS_ONE_OF_SEGMENT":
        if segment_depth > max_segment_depth:
            raise SegmentDepthExceeded(
                f"Segment references exceeded maximum segment depth limit of {max_segment_depth}"
            )

        segment_key = str(val)
        if not segments or segment_key not in segments:
            return False

        segment_group = segments[segment_key]
        return match_condition_group(
            segment_group,
            context,
            segments=segments,
            depth=1,
            max_depth=max_depth,
            segment_depth=segment_depth + 1,
            max_segment_depth=max_segment_depth,
        )

    # Standard operator
    context_val = context.get(attr)
    return apply_operator(op_upper, context_val, val)


def match_condition_group(
    group: ConditionGroup | dict[str, Any] | list[Any],
    context: EvaluationContext,
    segments: dict[str, Any] | None = None,
    depth: int = 1,
    max_depth: int = 5,
    segment_depth: int = 1,
    max_segment_depth: int = 3,
) -> bool:
    """Recursively match an AND/OR condition tree against the EvaluationContext.

    Args:
        group: ConditionGroup dataclass, dict representation, or list of conditions.
        context: User/device evaluation context.
        segments: Pre-loaded segment map from ruleset (no DB I/O).
        depth: Current tree recursion depth.
        max_depth: Maximum tree depth allowed (default 5).
        segment_depth: Current segment reference recursion depth.
        max_segment_depth: Maximum segment reference depth allowed (default 3).

    Returns:
        True if the condition group evaluates to True, False otherwise.

    Raises:
        ConditionDepthExceeded: If depth exceeds max_depth.
        SegmentDepthExceeded: If segment reference recursion exceeds max_segment_depth.
    """
    if depth > max_depth:
        raise ConditionDepthExceeded(f"Condition tree exceeded maximum depth limit of {max_depth}")

    # Handle bare list of conditions as implicit AND
    if isinstance(group, list):
        for cond in group:
            if not _eval_single_condition(
                cond, context, segments, max_depth, segment_depth, max_segment_depth
            ):
                return False
        return True

    # Extract operator, conditions, and children
    if isinstance(group, dict):
        op_str = group.get("operator", "AND").strip().upper()
        conditions = group.get("conditions", [])
        children = group.get("children", [])
    else:
        op_str = group.operator.strip().upper()
        conditions = group.conditions
        children = getattr(group, "children", [])

    is_and = op_str == "AND"

    # For empty groups
    if not conditions and not children:
        return True if is_and else False

    # Evaluate direct conditions
    for cond in conditions:
        matched = _eval_single_condition(
            cond, context, segments, max_depth, segment_depth, max_segment_depth
        )
        if is_and and not matched:
            return False
        if not is_and and matched:
            return True

    # Evaluate recursive children
    for child in children:
        matched = match_condition_group(
            child,
            context,
            segments=segments,
            depth=depth + 1,
            max_depth=max_depth,
            segment_depth=segment_depth,
            max_segment_depth=max_segment_depth,
        )
        if is_and and not matched:
            return False
        if not is_and and matched:
            return True

    # If AND: all matched -> True. If OR: none matched -> False.
    return True if is_and else False
