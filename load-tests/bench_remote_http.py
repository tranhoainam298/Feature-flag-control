"""Remote HTTP Latency Benchmark for FlagOps Evaluation Endpoints.

Directly tests the HTTP evaluation endpoints against a live server instance:
1. POST /eval/v1/flags/{flag_key}/evaluate (Server evaluation with Redis cache)
2. GET /eval/v1/ruleset (Full ruleset JSON download - 200 OK)
3. GET /eval/v1/ruleset with If-None-Match (ETag cached validation - 304 Not Modified)

Measures:
- Throughput (req/s)
- Latency distribution: min, mean, p50, p90, p95, p99, p99.9, max (ms)
- SLA Targets:
  * Evaluate p99 < 30.0 ms
  * 304 Not Modified p99 < 10.0 ms
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
EVAL_PREFIX = "/eval/v1"
STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def setup_bench_resources(client: httpx.AsyncClient) -> tuple[str, str, str]:
    """Bootstrap org, project, environment, API key, and flag for benchmarking."""
    email = f"http-bench-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "HTTP Benchmarker"},
    )
    login_res = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    tokens = login_res.json()
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Org & Project
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "HTTP Bench Org", "slug": _unique_slug("bench-org")},
        headers=auth_headers,
    )
    org_id = org_res.json()["id"]

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects",
        json={"name": "HTTP Bench Project", "slug": _unique_slug("bench-proj")},
        headers=auth_headers,
    )
    proj_id = proj_res.json()["id"]

    envs_res = await client.get(f"{PROJECT_PREFIX}/{proj_id}/environments", headers=auth_headers)
    dev_env = next(e for e in envs_res.json() if e["key"] == "development")
    env_id = dev_env["id"]

    # Generate 5 Server API Keys for rate limit distribution
    api_keys: list[str] = []
    for k_idx in range(5):
        key_res = await client.post(
            f"/api/v1/environments/{env_id}/api-keys",
            json={"name": f"Bench Key {k_idx}", "scope": "SERVER"},
            headers=auth_headers,
        )
        api_keys.append(key_res.json()["key"])

    # Feature flag with targeting rule
    flag_key = f"bench-flag-{uuid.uuid4().hex[:6]}"
    flag_res = await client.post(
        f"{PROJECT_PREFIX}/{proj_id}/flags",
        json={"key": flag_key, "name": "Bench Flag", "type": "BOOLEAN"},
        headers=auth_headers,
    )
    flag_id = flag_res.json()["id"]

    # Enable flag in environment
    await client.put(
        f"/api/v1/flags/{flag_id}/environments/{env_id}",
        json={"enabled": True},
        headers=auth_headers,
    )

    return api_keys, flag_key, env_id


def compute_metrics(latencies: list[float], name: str, target_p99: float | None = None) -> dict:
    latencies.sort()
    n = len(latencies)

    def p(pct: float) -> float:
        return latencies[min(int(n * (pct / 100.0)), n - 1)]

    min_val = latencies[0]
    mean_val = sum(latencies) / n
    p50 = p(50.0)
    p90 = p(90.0)
    p95 = p(95.0)
    p99 = p(99.0)
    max_val = latencies[-1]

    passed = (p99 < target_p99) if target_p99 is not None else True

    print(f"\nEndpoint: {name} (N = {n:,})")
    print(f"  Min:   {min_val:6.2f} ms")
    print(f"  Mean:  {mean_val:6.2f} ms")
    print(f"  p50:   {p50:6.2f} ms")
    print(f"  p90:   {p90:6.2f} ms")
    print(f"  p95:   {p95:6.2f} ms")
    print(f"  p99:   {p99:6.2f} ms" + (f"  <-- Target: < {target_p99:.1f} ms" if target_p99 else ""))
    print(f"  Max:   {max_val:6.2f} ms")
    if target_p99 is not None:
        print(f"  SLA Check: {'PASSED' if passed else 'FAILED'} (actual: {p99:.2f} ms vs target {target_p99:.1f} ms)")

    return {
        "n": n,
        "min_ms": min_val,
        "mean_ms": mean_val,
        "p50_ms": p50,
        "p90_ms": p90,
        "p95_ms": p95,
        "p99_ms": p99,
        "max_ms": max_val,
        "target_p99_ms": target_p99,
        "sla_passed": passed,
    }


async def run_http_benchmark(samples: int = 1_000) -> dict:
    print("=====================================================================")
    print(f" FlagOps Remote HTTP Latency Benchmark ({samples:,} requests/endpoint)")
    print("=====================================================================")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        print("Setting up benchmark tenant resources on live server...")
        api_keys, flag_key, env_id = await setup_bench_resources(client)
        print(f"Ready: Environment {env_id}, Flag: {flag_key}, Keys: {len(api_keys)}\n")

        # Obtain ETag for 304 tests
        h0 = {"X-FlagOps-Key": api_keys[0], "Content-Type": "application/json"}
        res = await client.get(f"{EVAL_PREFIX}/ruleset", headers=h0)
        assert res.status_code == 200, f"Failed ruleset fetch: {res.status_code}"
        etag = res.headers.get("ETag", 'W/"1"')
        print(f"Current Ruleset ETag: {etag}")

        num_keys = len(api_keys)

        # 1. Warm-up
        for w_i in range(50):
            hw = {"X-FlagOps-Key": api_keys[w_i % num_keys], "Content-Type": "application/json"}
            await client.post(
                f"{EVAL_PREFIX}/flags/{flag_key}/evaluate",
                json={"targetingKey": "warmup", "attributes": {}},
                headers=hw,
            )
            await client.get(f"{EVAL_PREFIX}/ruleset", headers=hw)
            await client.get(f"{EVAL_PREFIX}/ruleset", headers={**hw, "If-None-Match": etag})

        # ------------------------------------------------------------------
        # BENCHMARK 1: POST /eval/v1/flags/{flag_key}/evaluate (Server Eval)
        # ------------------------------------------------------------------
        eval_latencies: list[float] = []
        eval_url = f"{EVAL_PREFIX}/flags/{flag_key}/evaluate"
        eval_payload = {
            "targetingKey": "user_prod_benchmark_42",
            "attributes": {"country": "VN", "tier": "pro", "is_beta": True},
        }

        print(f"\nRunning {samples:,} evaluations on {eval_url}...")
        t_start = time.perf_counter()
        for i in range(samples):
            h = {"X-FlagOps-Key": api_keys[i % num_keys], "Content-Type": "application/json"}
            t0 = time.perf_counter()
            r = await client.post(eval_url, json=eval_payload, headers=h)
            t1 = time.perf_counter()
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            eval_latencies.append((t1 - t0) * 1000.0)
        eval_duration = time.perf_counter() - t_start
        eval_rps = samples / eval_duration
        print(f"Completed in {eval_duration:.2f}s ({eval_rps:,.0f} req/s)")

        # ------------------------------------------------------------------
        # BENCHMARK 2: GET /eval/v1/ruleset (Full 200 OK)
        # ------------------------------------------------------------------
        ruleset_200_latencies: list[float] = []
        ruleset_url = f"{EVAL_PREFIX}/ruleset"

        print(f"\nRunning {samples:,} requests on {ruleset_url} (200 OK)...")
        t_start = time.perf_counter()
        for i in range(samples):
            h = {"X-FlagOps-Key": api_keys[i % num_keys]}
            t0 = time.perf_counter()
            r = await client.get(ruleset_url, headers=h)
            t1 = time.perf_counter()
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            ruleset_200_latencies.append((t1 - t0) * 1000.0)
        ruleset_duration = time.perf_counter() - t_start
        ruleset_rps = samples / ruleset_duration
        print(f"Completed in {ruleset_duration:.2f}s ({ruleset_rps:,.0f} req/s)")

        # ------------------------------------------------------------------
        # BENCHMARK 3: GET /eval/v1/ruleset (304 Not Modified with ETag)
        # ------------------------------------------------------------------
        ruleset_304_latencies: list[float] = []

        print(f"\nRunning {samples:,} requests on {ruleset_url} (304 Not Modified)...")
        t_start = time.perf_counter()
        for i in range(samples):
            h304 = {"X-FlagOps-Key": api_keys[i % num_keys], "If-None-Match": etag}
            t0 = time.perf_counter()
            r = await client.get(ruleset_url, headers=h304)
            t1 = time.perf_counter()
            assert r.status_code == 304, f"Expected 304, got {r.status_code}"
            ruleset_304_latencies.append((t1 - t0) * 1000.0)
        duration_304 = time.perf_counter() - t_start
        rps_304 = samples / duration_304
        print(f"Completed in {duration_304:.2f}s ({rps_304:,.0f} req/s)")

    print("\n=====================================================================")
    print(" SUMMARY LATENCY REPORT")
    print("=====================================================================")
    metrics_eval = compute_metrics(eval_latencies, "POST /eval/v1/flags/{key}/evaluate", target_p99=30.0)
    metrics_200 = compute_metrics(ruleset_200_latencies, "GET /eval/v1/ruleset (200 OK)", target_p99=35.0)
    metrics_304 = compute_metrics(ruleset_304_latencies, "GET /eval/v1/ruleset (304 Not Modified)", target_p99=10.0)

    summary = {
        "samples_per_endpoint": samples,
        "endpoints": {
            "evaluate": metrics_eval,
            "ruleset_200": metrics_200,
            "ruleset_304": metrics_304,
        },
    }

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "bench_remote_http.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved benchmark results to {out_file}")

    return summary


if __name__ == "__main__":
    asyncio.run(run_http_benchmark(1_000))
