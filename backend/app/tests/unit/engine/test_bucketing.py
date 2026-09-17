"""Unit tests for MurmurHash3 Bucketing (Sticky Percentage Rollout)."""

import json
import subprocess
import sys
import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.engine.bucketing import InvalidDistributionError, bucket
from app.engine.types import DistributionEntry, Variation

# ============================================================================
# 1. INPUT VALIDATION TESTS
# ============================================================================


def test_bucket_empty_distribution_raises() -> None:
    with pytest.raises(InvalidDistributionError, match="cannot be empty"):
        bucket("user-1", "flag-1", "rule-1", [])


def test_bucket_negative_weight_raises() -> None:
    dist = [
        {"variation_id": "on", "weight": -10.0},
        {"variation_id": "off", "weight": 110.0},
    ]
    with pytest.raises(InvalidDistributionError, match="negative"):
        bucket("user-1", "flag-1", "rule-1", dist)


def test_bucket_sum_not_100_raises() -> None:
    dist_under = [
        {"variation_id": "on", "weight": 30.0},
        {"variation_id": "off", "weight": 60.0},
    ]
    with pytest.raises(InvalidDistributionError, match="equal 100"):
        bucket("user-1", "flag-1", "rule-1", dist_under)

    dist_over = [
        {"variation_id": "on", "weight": 60.0},
        {"variation_id": "off", "weight": 50.0},
    ]
    with pytest.raises(InvalidDistributionError, match="equal 100"):
        bucket("user-1", "flag-1", "rule-1", dist_over)


def test_bucket_invalid_entry_format_raises() -> None:
    with pytest.raises(InvalidDistributionError, match="invalid format"):
        bucket("user-1", "flag-1", "rule-1", ["invalid_entry"])  # type: ignore


def test_bucket_fallback_last_variation(monkeypatch: pytest.MonkeyPatch) -> None:
    import mmh3

    # Force hash result such that bucket_value is 9999 and cumulative is 9999.0
    monkeypatch.setattr(mmh3, "hash", lambda *args, **kwargs: 9999)
    dist = [
        {"variation_id": "A", "weight": 99.98},
        {"variation_id": "B", "weight": 0.02},
    ]
    # When cumulative reaches 9999.0 and bucket_value is 9999 (not < cumulative),
    # it safely falls through to return parsed_entries[-1][0]
    result = bucket("user-1", "flag-1", "rule-1", dist)
    assert result == "B"


def test_bucket_supports_dataclass_distribution_entry() -> None:
    var_on = Variation(key="on", value=True)
    var_off = Variation(key="off", value=False)
    dist = [
        DistributionEntry(variation=var_on, weight=50.0),
        DistributionEntry(variation=var_off, weight=50.0),
    ]
    result = bucket("user-1", "flag-1", "rule-1", dist)
    assert result in (var_on, var_off)


# ============================================================================
# 2. PROPERTY 1: DETERMINISM
# ============================================================================


@given(user_id=st.text(min_size=1, max_size=64))
def test_bucket_determinism(user_id: str) -> None:
    """Calling bucket twice with identical inputs must produce identical outputs."""
    dist = [
        {"variation_id": "A", "weight": 33.33},
        {"variation_id": "B", "weight": 33.33},
        {"variation_id": "C", "weight": 33.34},
    ]
    res1 = bucket(user_id, "search-flag", "rule-abc", dist)
    res2 = bucket(user_id, "search-flag", "rule-abc", dist)
    assert res1 == res2


# ============================================================================
# 3. PROPERTY 2: UNIFORM DISTRIBUTION
# ============================================================================


def test_bucket_uniform_distribution_50_50() -> None:
    """10,000 users on a 50/50 split must distribute within 0.48 - 0.52."""
    dist = [
        {"variation_id": "control", "weight": 50.0},
        {"variation_id": "treatment", "weight": 50.0},
    ]
    sample_size = 10000
    counts: dict[str, int] = {"control": 0, "treatment": 0}

    for i in range(sample_size):
        user_id = str(uuid.UUID(int=i + 1))
        assigned = bucket(user_id, "perf-flag", "rule-1", dist)
        counts[assigned] += 1

    ratio_control = counts["control"] / sample_size
    ratio_treatment = counts["treatment"] / sample_size
    assert 0.48 <= ratio_control <= 0.52, f"Control ratio {ratio_control} out of range"
    assert 0.48 <= ratio_treatment <= 0.52, f"Treatment ratio {ratio_treatment} out of range"


def test_bucket_uniform_distribution_10_90() -> None:
    """10,000 users on a 10/90 split must distribute within 0.09 - 0.11."""
    dist = [
        {"variation_id": "on", "weight": 10.0},
        {"variation_id": "off", "weight": 90.0},
    ]
    sample_size = 10000
    counts: dict[str, int] = {"on": 0, "off": 0}

    for i in range(sample_size):
        user_id = str(uuid.UUID(int=i + 1))
        assigned = bucket(user_id, "canary-flag", "rule-1", dist)
        counts[assigned] += 1

    ratio_on = counts["on"] / sample_size
    assert 0.09 <= ratio_on <= 0.11, f"Rollout 10% ratio {ratio_on} out of range"


def test_bucket_uniform_distribution_25_75() -> None:
    """10,000 users on a 25/75 split must distribute within 0.235 - 0.265."""
    dist = [
        {"variation_id": "v1", "weight": 25.0},
        {"variation_id": "v2", "weight": 75.0},
    ]
    sample_size = 10000
    counts: dict[str, int] = {"v1": 0, "v2": 0}

    for i in range(sample_size):
        user_id = str(uuid.UUID(int=i + 1))
        assigned = bucket(user_id, "split-flag", "rule-1", dist)
        counts[assigned] += 1

    ratio_v1 = counts["v1"] / sample_size
    assert 0.235 <= ratio_v1 <= 0.265, f"Rollout 25% ratio {ratio_v1} out of range"


# ============================================================================
# 4. PROPERTY 3: MONOTONIC ROLLOUT (CRITICAL)
# ============================================================================


def test_bucket_monotonic_rollout() -> None:
    """Users receiving 'on' at 10% must remain in 'on' at 20% rollout."""
    dist_10 = [
        {"variation_id": "on", "weight": 10.0},
        {"variation_id": "off", "weight": 90.0},
    ]
    dist_20 = [
        {"variation_id": "on", "weight": 20.0},
        {"variation_id": "off", "weight": 80.0},
    ]

    sample_size = 20000
    nhom_10: set[str] = set()
    nhom_20: set[str] = set()

    for i in range(sample_size):
        user_id = f"user-{i}"
        if bucket(user_id, "feature-x", "rule-1", dist_10) == "on":
            nhom_10.add(user_id)
        if bucket(user_id, "feature-x", "rule-1", dist_20) == "on":
            nhom_20.add(user_id)

    # Monotonic property: group 10 MUST be a strict subset of group 20
    assert nhom_10.issubset(nhom_20), (
        f"Monotonic violation: {len(nhom_10 - nhom_20)} users lost feature upon rollout increase!"
    )
    assert len(nhom_10) > 0
    assert len(nhom_20) > len(nhom_10)


# ============================================================================
# 5. PROPERTY 4: INDEPENDENCE BETWEEN FLAGS (CRITICAL)
# ============================================================================


def test_bucket_independence_between_flags() -> None:
    """Two different flags at 10% rollout must have intersection approx 1% (not 10%)."""
    dist_10 = [
        {"variation_id": "on", "weight": 10.0},
        {"variation_id": "off", "weight": 90.0},
    ]

    sample_size = 10000
    flag_a_users: set[str] = set()
    flag_b_users: set[str] = set()

    for i in range(sample_size):
        user_id = f"user-{i}"
        if bucket(user_id, "flag-alpha", "rule-1", dist_10) == "on":
            flag_a_users.add(user_id)
        if bucket(user_id, "flag-beta", "rule-1", dist_10) == "on":
            flag_b_users.add(user_id)

    overlap = flag_a_users.intersection(flag_b_users)
    overlap_ratio = len(overlap) / sample_size

    # Statistically, 10% * 10% = 1.0% overlap.
    # Must be in 0.5% - 1.8%, NOT ~10% (which happens if flag_key is omitted from hash).
    assert 0.005 <= overlap_ratio <= 0.018, (
        f"Overlap ratio {overlap_ratio:.4f} indicates flags are not independent!"
    )


# ============================================================================
# 6. PROPERTY 5: STABILITY ACROSS PROCESSES
# ============================================================================


def test_bucket_stability_across_processes() -> None:
    """MurmurHash3 must yield identical bucket results across independent Python processes."""
    dist = [
        {"variation_id": "A", "weight": 40.0},
        {"variation_id": "B", "weight": 60.0},
    ]
    test_users = [f"proc-user-{i}" for i in range(50)]

    # Result in current process
    expected_results = [bucket(uid, "cross-proc-flag", "rule-1", dist) for uid in test_users]

    # Run in fresh subprocess
    script = (
        "import json, sys\n"
        "from app.engine.bucketing import bucket\n"
        "users = json.loads(sys.argv[1])\n"
        "dist = json.loads(sys.argv[2])\n"
        "res = [bucket(uid, 'cross-proc-flag', 'rule-1', dist) for uid in users]\n"
        "print(json.dumps(res))\n"
    )

    import os

    env = os.environ.copy()
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    env["PYTHONPATH"] = os.pathsep.join([backend_dir, env.get("PYTHONPATH", "")])

    proc = subprocess.run(
        [sys.executable, "-c", script, json.dumps(test_users), json.dumps(dist)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    actual_results = json.loads(proc.stdout.strip())
    assert actual_results == expected_results
