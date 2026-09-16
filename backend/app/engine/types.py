"""Evaluation Engine Types — pure, zero-I/O frozen dataclasses and enums.

Follows evaluation-engine-purity rules:
- No imports of sqlalchemy, redis, httpx, fastapi, app.models, etc.
- Immutable via dataclass(frozen=True).
- Self-contained and portable to SDK or Relay Proxy.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Reason(str, Enum):
    """Reason codes for flag evaluation results."""

    TARGETING_MATCH = "TARGETING_MATCH"
    SPLIT = "SPLIT"
    DEFAULT = "DEFAULT"
    DISABLED = "DISABLED"
    ERROR = "ERROR"
    STATIC = "STATIC"
    CACHED = "CACHED"


class ErrorCode(str, Enum):
    """Standardized error codes for flag evaluation."""

    FLAG_NOT_FOUND = "FLAG_NOT_FOUND"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    PARSE_ERROR = "PARSE_ERROR"
    GENERAL_ERROR = "GENERAL_ERROR"
    INVALID_CONTEXT = "INVALID_CONTEXT"
    TARGETING_KEY_MISSING = "TARGETING_KEY_MISSING"


class Operator(str, Enum):
    """22 supported targeting condition operators."""

    # Equality & Comparison
    EQ = "EQ"
    NEQ = "NEQ"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"

    # Collections
    IN = "IN"
    NOT_IN = "NOT_IN"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"

    # String & Regex
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    MATCHES_REGEX = "MATCHES_REGEX"
    NOT_MATCHES_REGEX = "NOT_MATCHES_REGEX"

    # Semver
    SEMVER_EQ = "SEMVER_EQ"
    SEMVER_NEQ = "SEMVER_NEQ"
    SEMVER_GT = "SEMVER_GT"
    SEMVER_GTE = "SEMVER_GTE"
    SEMVER_LT = "SEMVER_LT"
    SEMVER_LTE = "SEMVER_LTE"

    # Existence
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"


@dataclass(frozen=True)
class EvaluationContext:
    """Evaluation context containing targeting key and arbitrary user/device attributes."""

    targeting_key: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve attribute by key with fallback to targeting_key or default."""
        if key in self.attributes:
            return self.attributes[key]
        if key in ("targetingKey", "targeting_key"):
            return self.targeting_key or default
        return default


@dataclass(frozen=True)
class Variation:
    """A variation configuration for a flag."""

    key: str
    value: Any
    id: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class Condition:
    """A single targeting condition evaluated against context attributes."""

    attribute: str
    operator: str
    value: Any


@dataclass(frozen=True)
class ConditionGroup:
    """Group of conditions combined by AND or OR logic."""

    operator: str = "AND"
    conditions: list[Condition] = field(default_factory=list)
    children: list["ConditionGroup"] = field(default_factory=list)


@dataclass(frozen=True)
class DistributionEntry:
    """Variation distribution entry with percentage weight (e.g. 50.0%)."""

    variation: Variation
    weight: float


@dataclass(frozen=True)
class TargetingRule:
    """Targeting rule evaluated by priority."""

    id: str
    priority: int
    conditions: ConditionGroup | list[Condition] | dict[str, Any] = field(default_factory=list)
    distribution: list[DistributionEntry] = field(default_factory=list)
    segment_id: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class IndividualOverride:
    """Direct override mapping a context key (e.g. userId) to a specific variation."""

    context_key: str
    variation: Variation
    id: str | None = None


@dataclass(frozen=True)
class FlagRuleset:
    """In-memory ruleset representing a flag and its environment settings."""

    flag_id: str
    flag_key: str
    flag_type: str
    enabled: bool = False
    bucketing_key: str = "targetingKey"
    default_variation: Variation | None = None
    off_variation: Variation | None = None
    variations: list[Variation] = field(default_factory=list)
    rules: list[TargetingRule] = field(default_factory=list)
    overrides: list[IndividualOverride] = field(default_factory=list)

    def get_override(self, key: str) -> IndividualOverride | None:
        """Find override matching context key."""
        for override in self.overrides:
            if override.context_key == key:
                return override
        return None


@dataclass(frozen=True)
class Ruleset:
    """Full environment ruleset for evaluation."""

    environment_id: str
    ruleset_version: int = 0
    flags: dict[str, FlagRuleset] = field(default_factory=dict)
    segments: dict[str, Any] = field(default_factory=dict)

    def get_flag(self, flag_key: str) -> FlagRuleset | None:
        """Lookup flag by key."""
        return self.flags.get(flag_key)


@dataclass(frozen=True)
class EvaluationResult:
    """Result of flag evaluation."""

    flag_key: str = ""
    value: Any = None
    variant: str = ""
    reason: Reason | str = Reason.DEFAULT
    flag_metadata: dict[str, Any] | None = None
    error_code: ErrorCode | str | None = None
    error_message: str | None = None
