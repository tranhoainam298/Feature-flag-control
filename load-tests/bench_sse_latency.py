"""SSE Event Propagation Latency Benchmark for FlagOps.

Measures the latency from the moment an environment's ruleset changes
(Admin API flag mutation) to when an SSE subscriber receives the
`ruleset_updated` event over the Server-Sent Events stream.

Target: propagation latency < 2.0 seconds (2,000 ms).
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

from httpx import AsyncClient

BASE = "http://127.0.0.1:8000"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
EVAL_PREFIX = "/eval/v1"
STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"sse-bench-{uuid.uuid4().hex[:10]}@example.com"


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    email = _unique_email()
    await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "SSE Benchmarker"},
    )
    login_res = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return tokens, headers


async def setup_bench_env(client: AsyncClient, admin_headers: dict) -> tuple[dict, dict, dict, str, dict]:
    """Setup org, project, environment, server key, and flag."""
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "SSE Bench Org", "slug": _unique_slug("sse-bench-org")},
        headers=admin_headers,
    )
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "SSE Bench Project", "slug": _unique_slug("sse-bench-proj")},
        headers=admin_headers,
    )
    project = proj_res.json()

    envs_res = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=admin_headers,
    )
    envs = envs_res.json()
    dev_env = next(e for e in envs if e["key"] == "development")

    srv_key_res = await client.post(
        f"/api/v1/environments/{dev_env['id']}/api-keys",
        json={"name": "SSE Bench Key", "scope": "SERVER"},
        headers=admin_headers,
    )
    raw_key = srv_key_res.json()["key"]

    flag_res = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": f"flag-sse-{uuid.uuid4().hex[:6]}",
            "name": "SSE Latency Flag",
            "type": "BOOLEAN",
        },
        headers=admin_headers,
    )
    flag = flag_res.json()

    return org, project, dev_env, raw_key, flag


async def run_sse_benchmark(iterations: int = 10) -> dict:
    """Execute SSE propagation latency benchmark."""
    print("=====================================================================")
    print(f" FlagOps SSE Propagation Latency Benchmark ({iterations} iterations)")
    print("=====================================================================")

    async with AsyncClient(base_url=BASE, timeout=15.0) as client:
        _, admin_headers = await create_and_login_user(client)
        org, project, dev_env, raw_key, flag = await setup_bench_env(client, admin_headers)
        print(f"Created Org: {org['slug']}, Project: {project['slug']}")
        print(f"Target Environment: {dev_env['id']} ({dev_env['name']})")
        print(f"Target Flag: {flag['key']}")

        headers = {"X-FlagOps-Key": raw_key}
        event_queue: asyncio.Queue[tuple[str, str, float]] = asyncio.Queue()
        stop_stream = asyncio.Event()

        async def reader_task():
            try:
                url = f"{EVAL_PREFIX}/stream"
                async with client.stream("GET", url, headers=headers, timeout=60.0) as response:
                    assert response.status_code == 200, f"SSE endpoint status {response.status_code}"
                    cur_event = "message"
                    cur_data = []
                    async for line in response.aiter_lines():
                        if stop_stream.is_set():
                            break
                        line = line.rstrip("\r\n")
                        if line.startswith("event:"):
                            cur_event = line[len("event:") :].strip()
                        elif line.startswith("data:"):
                            cur_data.append(line[len("data:") :].strip())
                        elif line == "" and cur_event != "message":
                            recv_time = time.perf_counter()
                            await event_queue.put((cur_event, "\n".join(cur_data), recv_time))
                            cur_event = "message"
                            cur_data = []
            except Exception as exc:
                if not stop_stream.is_set():
                    print(f"Reader task error: {exc}")

        task = asyncio.create_task(reader_task())

        # Wait for initial heartbeat frame
        print("Connected to SSE stream. Awaiting initial stream frame...")
        ev, data, _ = await asyncio.wait_for(event_queue.get(), timeout=5.0)
        assert ev == "heartbeat", f"Expected heartbeat, got {ev}"
        print("Initial heartbeat frame received. Ready.\n")

        latencies_ms: list[float] = []

        for i in range(1, iterations + 1):
            enabled_state = (i % 2 == 1)
            t0 = time.perf_counter()

            # Mutate flag environment setting
            put_res = await client.put(
                f"/api/v1/flags/{flag['id']}/environments/{dev_env['id']}",
                json={"enabled": enabled_state},
                headers=admin_headers,
            )
            assert put_res.status_code == 200, f"Flag update failed with {put_res.status_code}"

            # Wait for ruleset_updated event on SSE
            ev, data_str, t1 = await asyncio.wait_for(event_queue.get(), timeout=3.0)
            assert ev == "ruleset_updated", f"Expected ruleset_updated, got {ev}"

            latency_ms = (t1 - t0) * 1000.0
            latencies_ms.append(latency_ms)

            payload = json.loads(data_str)
            print(
                f"  [{i:2d}/{iterations}] rulesetVersion: {payload.get('rulesetVersion')} -> received in {latency_ms:6.2f} ms"
            )

            await asyncio.sleep(0.1)

        stop_stream.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    latencies_ms.sort()
    min_ms = latencies_ms[0]
    max_ms = latencies_ms[-1]
    mean_ms = sum(latencies_ms) / len(latencies_ms)

    def get_percentile(p: float) -> float:
        idx = min(int(len(latencies_ms) * (p / 100.0)), len(latencies_ms) - 1)
        return latencies_ms[idx]

    p50_ms = get_percentile(50.0)
    p95_ms = get_percentile(95.0)
    p99_ms = get_percentile(99.0)

    target_ms = 2000.0  # 2.0s
    passed_target = p99_ms < target_ms

    print("\n---------------------------------------------------------------------")
    print("SSE Propagation Latency Results:")
    print(f"  Min:   {min_ms:6.2f} ms")
    print(f"  Mean:  {mean_ms:6.2f} ms")
    print(f"  p50:   {p50_ms:6.2f} ms")
    print(f"  p95:   {p95_ms:6.2f} ms")
    print(f"  p99:   {p99_ms:6.2f} ms  <-- Target: < 2,000.0 ms (2s)")
    print(f"  Max:   {max_ms:6.2f} ms")
    print(f"\nSLA Check (< 2s): {'PASSED' if passed_target else 'FAILED'} (actual: {p99_ms:.2f} ms)")
    print("---------------------------------------------------------------------\n")

    results = {
        "iterations": iterations,
        "latency_ms": {
            "min": min_ms,
            "mean": mean_ms,
            "p50": p50_ms,
            "p95": p95_ms,
            "p99": p99_ms,
            "max": max_ms,
        },
        "target_ms": target_ms,
        "sla_passed": passed_target,
    }

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "bench_sse_latency.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {out_path}")

    return results


if __name__ == "__main__":
    asyncio.run(run_sse_benchmark(10))
