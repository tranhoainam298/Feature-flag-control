"""Evaluation Engine — pure, zero-I/O deterministic engine."""

from .bucketing import InvalidDistributionError, bucket
from .evaluator import evaluate
from .matcher import (
    ConditionDepthExceeded,
    SegmentDepthExceeded,
    match_condition_group,
)
from .operators import OPERATORS, apply_operator
from .types import (
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

__all__ = [
    "Condition",
    "ConditionDepthExceeded",
    "ConditionGroup",
    "DistributionEntry",
    "ErrorCode",
    "EvaluationContext",
    "EvaluationResult",
    "FlagRuleset",
    "IndividualOverride",
    "InvalidDistributionError",
    "OPERATORS",
    "Operator",
    "Reason",
    "Ruleset",
    "SegmentDepthExceeded",
    "TargetingRule",
    "Variation",
    "apply_operator",
    "bucket",
    "evaluate",
    "match_condition_group",
]
