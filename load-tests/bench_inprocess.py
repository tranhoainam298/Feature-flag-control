"""In-Process Evaluation Benchmark for FlagOps Python SDK.

Runs 100,000 evaluations across realistic feature flag rulesets:
- Boolean flags, string variations, JSON configs, numeric flags.
- Default variations, individual user overrides, targeting rules with conditions.
- Percentage rollout splits via MurmurHash3 bucketing.
- Disabled flags with off-variation fallbacks.

Measures:
- Throughput (ops/second)
- p50, p90, p95, p99, p99.9 latency in microseconds and milliseconds.
- Success rate and distribution of reasons.
Target: p99 < 1.0 ms.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add project roots to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
SDK_PATH = BASE_DIR / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from flagops.cache import parse_ruleset
from flagops.engine.evaluator import evaluate
from flagops.engine.types import EvaluationContext


def create_realistic_ruleset_payload() -> dict:
    """Create a realistic compiled ruleset payload with 10 varied flags."""
    return {
        "environmentId": "00000000-0000-0000-0000-000000000001",
        "rulesetVersion": 42,
        "segments": {
            "beta_testers": {
                "combinator": "AND",
                "rules": [{"field": "is_beta", "operator": "equals", "value": True}],
            },
            "apac_users": {
                "combinator": "OR",
                "rules": [
                    {"field": "country", "operator": "in", "value": ["VN", "SG", "JP", "TH"]}
                ],
            },
        },
        "flags": {
            # 1. Simple boolean flag (Default variation)
            "feature-dark-mode": {
                "flagKey": "feature-dark-mode",
                "type": "BOOLEAN",
                "enabled": True,
                "variations": [
                    {"id": "v-dark-true", "key": "true", "value": True},
                    {"id": "v-dark-false", "key": "false", "value": False},
                ],
                "defaultVariation": {"id": "v-dark-true", "key": "true", "value": True},
                "offVariation": {"id": "v-dark-false", "key": "false", "value": False},
                "targetingRules": [],
                "individualOverrides": [],
            },
            # 2. Disabled flag
            "feature-ai-assistant": {
                "flagKey": "feature-ai-assistant",
                "type": "BOOLEAN",
                "enabled": False,
                "variations": [
                    {"id": "v-ai-on", "key": "on", "value": True},
                    {"id": "v-ai-off", "key": "off", "value": False},
                ],
                "defaultVariation": {"id": "v-ai-on", "key": "on", "value": True},
                "offVariation": {"id": "v-ai-off", "key": "off", "value": False},
                "targetingRules": [],
                "individualOverrides": [],
            },
            # 3. Individual user override
            "payment-v2": {
                "flagKey": "payment-v2",
                "type": "STRING",
                "enabled": True,
                "variations": [
                    {"id": "v-pay-stripe", "key": "stripe", "value": "stripe_v2"},
                    {"id": "v-pay-paypal", "key": "paypal", "value": "paypal_v2"},
                    {"id": "v-pay-legacy", "key": "legacy", "value": "legacy_v1"},
                ],
                "defaultVariation": {"id": "v-pay-legacy", "key": "legacy", "value": "legacy_v1"},
                "offVariation": {"id": "v-pay-legacy", "key": "legacy", "value": "legacy_v1"},
                "overrides": [
                    {
                        "id": "ov-vip",
                        "contextKey": "user-vip-999",
                        "variationId": "v-pay-stripe",
                    }
                ],
                "rules": [],
            },
            # 4. Targeting rule with segment match
            "checkout-redesign": {
                "flagKey": "checkout-redesign",
                "type": "BOOLEAN",
                "enabled": True,
                "variations": [
                    {"id": "v-chk-new", "key": "treatment", "value": True},
                    {"id": "v-chk-old", "key": "control", "value": False},
                ],
                "defaultVariation": {"id": "v-chk-old", "key": "control", "value": False},
                "offVariation": {"id": "v-chk-old", "key": "control", "value": False},
                "rules": [
                    {
                        "id": "tr-beta",
                        "priority": 1,
                        "conditions": [
                            {
                                "attribute": "is_beta",
                                "operator": "EQ",
                                "value": True,
                            }
                        ],
                        "distribution": [
                            {"variationId": "v-chk-new", "weight": 100.0}
                        ],
                    }
                ],
                "overrides": [],
            },
            # 5. Percentage rollout (50/50 split with MurmurHash3)
            "new-recommendation-algorithm": {
                "flagKey": "new-recommendation-algorithm",
                "type": "STRING",
                "enabled": True,
                "variations": [
                    {"id": "v-algo-a", "key": "model_a", "value": "transformer_v3"},
                    {"id": "v-algo-b", "key": "model_b", "value": "collaborative_v1"},
                ],
                "defaultVariation": {"id": "v-algo-b", "key": "model_b", "value": "collaborative_v1"},
                "offVariation": {"id": "v-algo-b", "key": "model_b", "value": "collaborative_v1"},
                "rules": [
                    {
                        "id": "tr-rollout-50",
                        "priority": 1,
                        "conditions": [
                            {"attribute": "tier", "operator": "EQ", "value": "pro"}
                        ],
                        "distribution": [
                            {"variationId": "v-algo-a", "weight": 50.0},
                            {"variationId": "v-algo-b", "weight": 50.0},
                        ],
                    }
                ],
                "overrides": [],
            },
            # 6. JSON Configuration Flag
            "app-rate-limits": {
                "flagKey": "app-rate-limits",
                "type": "JSON",
                "enabled": True,
                "variations": [
                    {
                        "id": "v-rate-tier1",
                        "key": "tier1",
                        "value": {"max_requests": 1000, "burst": 50, "window_sec": 60},
                    },
                    {
                        "id": "v-rate-default",
                        "key": "default",
                        "value": {"max_requests": 100, "burst": 10, "window_sec": 60},
                    },
                ],
                "defaultVariation": {
                    "id": "v-rate-default",
                    "key": "default",
                    "value": {"max_requests": 100, "burst": 10, "window_sec": 60},
                },
                "offVariation": {
                    "id": "v-rate-default",
                    "key": "default",
                    "value": {"max_requests": 100, "burst": 10, "window_sec": 60},
                },
                "rules": [
                    {
                        "id": "tr-premium",
                        "priority": 1,
                        "conditions": [
                            {"attribute": "plan", "operator": "EQ", "value": "enterprise"}
                        ],
                        "distribution": [
                            {"variationId": "v-rate-tier1", "weight": 100.0}
                        ],
                    }
                ],
                "overrides": [],
            },
            # 7. Number flag with numeric comparison rule
            "max-upload-size-mb": {
                "flagKey": "max-upload-size-mb",
                "type": "NUMBER",
                "enabled": True,
                "variations": [
                    {"id": "v-size-500", "key": "large", "value": 500},
                    {"id": "v-size-50", "key": "standard", "value": 50},
                ],
                "defaultVariation": {"id": "v-size-50", "key": "standard", "value": 50},
                "offVariation": {"id": "v-size-50", "key": "standard", "value": 50},
                "rules": [
                    {
                        "id": "tr-storage-plan",
                        "priority": 1,
                        "conditions": [
                            {"attribute": "storage_tier", "operator": "GTE", "value": 3}
                        ],
                        "distribution": [
                            {"variationId": "v-size-500", "weight": 100.0}
                        ],
                    }
                ],
                "overrides": [],
            },
            # 8. Flag with Semver condition
            "mobile-v2-features": {
                "flagKey": "mobile-v2-features",
                "type": "BOOLEAN",
                "enabled": True,
                "variations": [
                    {"id": "v-mob-on", "key": "on", "value": True},
                    {"id": "v-mob-off", "key": "off", "value": False},
                ],
                "defaultVariation": {"id": "v-mob-off", "key": "off", "value": False},
                "offVariation": {"id": "v-mob-off", "key": "off", "value": False},
                "rules": [
                    {
                        "id": "tr-app-ver",
                        "priority": 1,
                        "conditions": [
                            {"attribute": "app_version", "operator": "SEMVER_GTE", "value": "2.4.0"}
                        ],
                        "distribution": [
                            {"variationId": "v-mob-on", "weight": 100.0}
                        ],
                    }
                ],
                "overrides": [],
            },
            # 9. Multi-condition targeting rule
            "regional-promo-banner": {
                "flagKey": "regional-promo-banner",
                "type": "STRING",
                "enabled": True,
                "variations": [
                    {"id": "v-banner-vn", "key": "vn_promo", "value": "Chuc Mung Nam Moi!"},
                    {"id": "v-banner-none", "key": "none", "value": ""},
                ],
                "defaultVariation": {"id": "v-banner-none", "key": "none", "value": ""},
                "offVariation": {"id": "v-banner-none", "key": "none", "value": ""},
                "rules": [
                    {
                        "id": "tr-vn-holiday",
                        "priority": 1,
                        "conditions": [
                            {"attribute": "country", "operator": "EQ", "value": "VN"},
                            {"attribute": "is_guest", "operator": "EQ", "value": False},
                        ],
                        "distribution": [
                            {"variationId": "v-banner-vn", "weight": 100.0}
                        ],
                    }
                ],
                "overrides": [],
            },
            # 10. Default boolean flag
            "analytics-beacon-v2": {
                "flagKey": "analytics-beacon-v2",
                "type": "BOOLEAN",
                "enabled": True,
                "variations": [
                    {"id": "v-beacon-on", "key": "enabled", "value": True},
                    {"id": "v-beacon-off", "key": "disabled", "value": False},
                ],
                "defaultVariation": {"id": "v-beacon-on", "key": "enabled", "value": True},
                "offVariation": {"id": "v-beacon-off", "key": "disabled", "value": False},
                "targetingRules": [],
                "individualOverrides": [],
            },
        },
    }


def run_benchmark(iterations: int = 100_000) -> dict:
    """Execute in-process evaluation benchmark."""
    print(f"=====================================================================")
    print(f" FlagOps In-Process Evaluation Benchmark ({iterations:,} iterations)")
    print(f"=====================================================================")

    payload = create_realistic_ruleset_payload()
    ruleset = parse_ruleset(payload)
    flag_keys = list(payload["flags"].keys())

    # Pre-generate 100 varied evaluation contexts to simulate production traffic
    contexts: list[EvaluationContext] = []
    for i in range(100):
        t_key = f"user-vip-999" if i % 10 == 0 else f"user_{i:05d}"
        ctx = EvaluationContext(
            targeting_key=t_key,
            attributes={
                "is_beta": (i % 4 == 0),
                "country": ["VN", "SG", "US", "JP", "DE"][i % 5],
                "tier": "pro" if (i % 2 == 0) else "free",
                "plan": "enterprise" if (i % 6 == 0) else "standard",
                "storage_tier": (i % 5) + 1,
                "app_version": f"2.{i % 6}.0",
                "is_guest": (i % 3 == 0),
            },
        )
        contexts.append(ctx)

    num_contexts = len(contexts)
    num_flags = len(flag_keys)

    # Warm-up (1,000 evaluations)
    for i in range(1_000):
        fk = flag_keys[i % num_flags]
        ctx = contexts[i % num_contexts]
        evaluate(ruleset, ctx, fk, default_value=None)

    # Main measurement run
    latencies_ns: list[int] = [0] * iterations
    reason_counts: dict[str, int] = {}

    start_bench_time = time.perf_counter()

    for i in range(iterations):
        fk = flag_keys[i % num_flags]
        ctx = contexts[i % num_contexts]

        t0 = time.perf_counter_ns()
        res = evaluate(ruleset, ctx, fk, default_value=None)
        t1 = time.perf_counter_ns()

        latencies_ns[i] = t1 - t0
        r_name = str(res.reason.value if hasattr(res.reason, "value") else res.reason)
        reason_counts[r_name] = reason_counts.get(r_name, 0) + 1

    total_bench_duration_s = time.perf_counter() - start_bench_time

    # Sort latencies for percentiles
    latencies_ns.sort()

    def get_percentile(p: float) -> float:
        idx = min(int(iterations * (p / 100.0)), iterations - 1)
        return latencies_ns[idx]

    p50_ns = get_percentile(50.0)
    p90_ns = get_percentile(90.0)
    p95_ns = get_percentile(95.0)
    p99_ns = get_percentile(99.0)
    p999_ns = get_percentile(99.9)

    min_ns = latencies_ns[0]
    max_ns = latencies_ns[-1]
    mean_ns = sum(latencies_ns) / iterations

    ops_per_sec = iterations / total_bench_duration_s

    # Conversion helpers
    to_us = lambda ns: ns / 1_000.0
    to_ms = lambda ns: ns / 1_000_000.0

    print(f"\nCompleted in {total_bench_duration_s:.3f} seconds.")
    print(f"Throughput: {ops_per_sec:,.0f} ops/sec")
    print(f"\nLatency Distribution:")
    print(f"  Min:    {to_us(min_ns):8.2f} µs  ({to_ms(min_ns):.4f} ms)")
    print(f"  Mean:   {to_us(mean_ns):8.2f} µs  ({to_ms(mean_ns):.4f} ms)")
    print(f"  p50:    {to_us(p50_ns):8.2f} µs  ({to_ms(p50_ns):.4f} ms)")
    print(f"  p90:    {to_us(p90_ns):8.2f} µs  ({to_ms(p90_ns):.4f} ms)")
    print(f"  p95:    {to_us(p95_ns):8.2f} µs  ({to_ms(p95_ns):.4f} ms)")
    print(f"  p99:    {to_us(p99_ns):8.2f} µs  ({to_ms(p99_ns):.4f} ms)  <-- Target: < 1.0 ms")
    print(f"  p99.9:  {to_us(p999_ns):8.2f} µs  ({to_ms(p999_ns):.4f} ms)")
    print(f"  Max:    {to_us(max_ns):8.2f} µs  ({to_ms(max_ns):.4f} ms)")

    p99_ms = to_ms(p99_ns)
    passed_target = p99_ms < 1.0
    print(f"\nEvaluation Reason Distribution:")
    for reason, count in sorted(reason_counts.items()):
        print(f"  - {reason:20s}: {count:6d} ({count/iterations*100:5.1f}%)")

    status_str = "PASSED" if passed_target else "FAILED"
    print(f"\np99 SLA Check (< 1.0 ms): {status_str} (actual: {p99_ms:.4f} ms)\n")

    results = {
        "iterations": iterations,
        "duration_seconds": total_bench_duration_s,
        "throughput_ops_sec": ops_per_sec,
        "latency_us": {
            "min": to_us(min_ns),
            "mean": to_us(mean_ns),
            "p50": to_us(p50_ns),
            "p90": to_us(p90_ns),
            "p95": to_us(p95_ns),
            "p99": to_us(p99_ns),
            "p99_9": to_us(p999_ns),
            "max": to_us(max_ns),
        },
        "latency_ms": {
            "min": to_ms(min_ns),
            "mean": to_ms(mean_ns),
            "p50": to_ms(p50_ns),
            "p90": to_ms(p90_ns),
            "p95": to_ms(p95_ns),
            "p99": p99_ms,
            "p99_9": to_ms(p999_ns),
            "max": to_ms(max_ns),
        },
        "target_p99_ms": 1.0,
        "p99_passed": passed_target,
        "reason_distribution": reason_counts,
    }

    results_dir = BASE_DIR / "load-tests" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "bench_inprocess.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {out_path}")

    return results


if __name__ == "__main__":
    run_benchmark(100_000)
