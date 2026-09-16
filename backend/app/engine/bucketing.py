"""MurmurHash3 Sticky Bucketing Algorithm for FlagOps Evaluation Engine.

Pure computation rules:
- Zero I/O, deterministic, pure function.
- Uses 32-bit unsigned MurmurHash3.
- Normalizes to [0..9999] (0.01% resolution).
- Concatenates {flag_key}:{rule_id}:{context_value} for inter-flag independence.
- Strictly validates distribution weights (must be non-negative and sum to 100).
"""

from collections.abc import Sequence
from typing import Any

import mmh3

from app.engine.types import DistributionEntry


class InvalidDistributionError(ValueError):
    """Raised when distribution entries fail validation (e.g. empty, negative, or sum != 100)."""

    pass


def bucket(
    context_value: str,
    flag_key: str,
    rule_id: str,
    distribution: Sequence[DistributionEntry | dict[str, Any]],
    seed: int = 0,
) -> Any:
    """Bucket a context value into a variation deterministically using MurmurHash3.

    Args:
        context_value: Identifier to hash (e.g. user ID, session ID).
        flag_key: Key of the feature flag (ensures flag independence).
        rule_id: Targeting rule ID (ensures rule independence).
        distribution: Sequence of variations with percentage weights.
        seed: Optional hash seed (default 0).

    Returns:
        The matched variation object or variation_id.

    Raises:
        InvalidDistributionError: If distribution is empty, has negative weights,
                                 or weights do not sum to 100.
    """
    if not distribution:
        raise InvalidDistributionError("Distribution cannot be empty")

    parsed_entries: list[tuple[Any, float]] = []
    total_weight = 0.0

    for idx, entry in enumerate(distribution):
        if isinstance(entry, dict):
            weight = entry.get("weight")
            var = entry.get("variation", entry.get("variation_id"))
        elif hasattr(entry, "weight"):
            weight = getattr(entry, "weight")
            var = getattr(entry, "variation", getattr(entry, "variation_id", entry))
        else:
            raise InvalidDistributionError(f"Entry at index {idx} has invalid format")

        if weight is None or weight < 0:
            raise InvalidDistributionError(f"Weights cannot be negative, got {weight}")

        parsed_weight = float(weight)
        parsed_entries.append((var, parsed_weight))
        total_weight += parsed_weight

    # Validate sum equals 100 within a small float tolerance
    if abs(total_weight - 100.0) > 0.001:
        raise InvalidDistributionError(
            f"Total distribution weight must equal 100, got {total_weight}"
        )

    # Hash input format: {flag_key}:{rule_id}:{context_value}
    hash_input = f"{flag_key}:{rule_id}:{context_value}"
    h = mmh3.hash(hash_input, seed, signed=False)
    bucket_value = h % 10000

    cumulative = 0.0
    for var, weight in parsed_entries:
        cumulative += weight * 100.0
        if bucket_value < cumulative:
            return var

    # Fallback to last variation to protect against floating point rounding
    return parsed_entries[-1][0]
