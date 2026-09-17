"""Integration tests for Slice 12 — Server-Sent Events (SSE).

Covers:
- Client connects via SSE and receives initial heartbeat frame
- Query parameter authentication (?key=) for browser EventSource compatibility
- Flag mutation on Admin API propagates ruleset_updated event in < 2s (with latency measurement)
- Client disconnect cleans up Redis subscriber and decrements active connection count
- Redis failure resilience (fail-open fallback, server does not crash)
- 100 concurrent SSE connections do not freeze server
"""

import asyncio
import json
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from starlette.requests import Request

from app.api.eval.router import _ruleset_event_stream

BASE = "http://127.0.0.1:8000"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
EVAL_PREFIX = "/eval/v1"
STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"sse-test-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    email = _unique_email()
    reg_res = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "SSE Tester"},
    )
    assert reg_res.status_code == 201, f"Register failed: {reg_res.text}"
    login_res = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return tokens, headers


async def setup_env_with_key(
    client: AsyncClient, admin_headers: dict
) -> tuple[dict, dict, list[dict], str]:
    """Create org, project, environments, and server API key."""
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "SSE Org", "slug": _unique_slug("sse-org")},
        headers=admin_headers,
    )
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "SSE Project", "slug": _unique_slug("sse-proj")},
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
        json={"name": "SSE Server Key", "scope": "SERVER"},
        headers=admin_headers,
    )
    raw_key = srv_key_res.json()["key"]

    return org, project, envs, raw_key


async def create_boolean_flag(
    client: AsyncClient, admin_headers: dict, project_id: str, flag_key: str
) -> dict:
    res = await client.post(
        f"{PROJECT_PREFIX}/{project_id}/flags",
        json={"key": flag_key, "name": f"Flag {flag_key}", "type": "BOOLEAN"},
        headers=admin_headers,
    )
    return res.json()


# ==============================================================================
# 1. CLIENT SSE CONNECTS → RECEIVES HEARTBEAT
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_connect_and_receive_heartbeat() -> None:
    """Client connects to /eval/v1/stream with X-FlagOps-Key and receives initial heartbeat."""
    async with AsyncClient(base_url=BASE, timeout=10.0) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, raw_key = await setup_env_with_key(client, admin_headers)

        headers = {"X-FlagOps-Key": raw_key}
        async with client.stream("GET", f"{EVAL_PREFIX}/stream", headers=headers) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Read first event frame
            lines: list[str] = []
            async for line in response.aiter_lines():
                line = line.rstrip("\r\n")
                if line == "" and lines:
                    break
                if line:
                    lines.append(line)

            assert "event: heartbeat" in lines
            assert "data: {}" in lines


# ==============================================================================
# 2. QUERY PARAM AUTHENTICATION (?key=...)
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_query_param_auth() -> None:
    """EventSource browser clients can authenticate via ?key= query parameter."""
    async with AsyncClient(base_url=BASE, timeout=10.0) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, raw_key = await setup_env_with_key(client, admin_headers)

        # Valid query parameter key
        async with client.stream("GET", f"{EVAL_PREFIX}/stream?key={raw_key}") as response:
            assert response.status_code == 200
            lines: list[str] = []
            async for line in response.aiter_lines():
                line = line.rstrip("\r\n")
                if line == "" and lines:
                    break
                if line:
                    lines.append(line)
            assert "event: heartbeat" in lines

        # Invalid query parameter key -> 401
        res = await client.get(f"{EVAL_PREFIX}/stream?key=invalid_secret_key_12345")
        assert res.status_code == 401


# ==============================================================================
# 3. FLAG MUTATION ON ADMIN API → CLIENT SSE RECEIVES EVENT IN < 2 SECONDS
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_flag_mutation_propagation_latency() -> None:
    """Admin flag mutation triggers ruleset_updated event on SSE stream in < 2 seconds."""
    async with AsyncClient(base_url=BASE, timeout=10.0) as client:
        _, admin_headers = await create_and_login_user(client)
        org, project, envs, raw_key = await setup_env_with_key(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        flag = await create_boolean_flag(client, admin_headers, project["id"], "sse-latency-flag")

        # Establish SSE stream in background task
        headers = {"X-FlagOps-Key": raw_key}
        event_queue: asyncio.Queue[tuple[str, str, float]] = asyncio.Queue()
        stop_stream = asyncio.Event()

        async def reader_task():
            try:
                url = f"{EVAL_PREFIX}/stream"
                async with client.stream("GET", url, headers=headers) as response:
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
            except Exception:
                pass

        task = asyncio.create_task(reader_task())

        # Wait for initial heartbeat
        ev, data, _ = await asyncio.wait_for(event_queue.get(), timeout=5.0)
        assert ev == "heartbeat"

        # Now mutate flag via Admin API and record exact timestamp
        start_time = time.perf_counter()
        put_res = await client.put(
            f"/api/v1/flags/{flag['id']}/environments/{dev_env['id']}",
            json={"enabled": True},
            headers=admin_headers,
        )
        assert put_res.status_code == 200

        # Wait for ruleset_updated event
        ev, data, recv_time = await asyncio.wait_for(event_queue.get(), timeout=3.0)
        latency = recv_time - start_time
        latency_ms = latency * 1000.0

        print(f"\n[MEASURED LATENCY] Flag mutation to SSE propagation: {latency_ms:.2f} ms")

        assert ev == "ruleset_updated"
        payload = json.loads(data)
        assert payload["environmentId"] == dev_env["id"]
        assert payload["rulesetVersion"] >= 1
        assert latency < 2.0, f"SSE propagation latency ({latency:.4f}s) exceeded 2.0s limit"

        stop_stream.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ==============================================================================
# 4. CLIENT DISCONNECT → SERVER CLEANS UP SUBSCRIBER (ACTIVE CONNECTIONS → 0)
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_client_disconnect_cleanup() -> None:
    """Closing client connection decrements active connection count and closes Redis pubsub."""
    async with AsyncClient(base_url=BASE, timeout=10.0) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, raw_key = await setup_env_with_key(client, admin_headers)

        # Ensure previous connections have settled
        baseline = 0
        for _ in range(10):
            metric_res = await client.get(
                f"{EVAL_PREFIX}/stream/connections",
                headers={"X-FlagOps-Key": raw_key},
            )
            baseline = metric_res.json()["active_connections"]
            if baseline == 0:
                break
            await asyncio.sleep(0.1)

        headers = {"X-FlagOps-Key": raw_key}
        connected = asyncio.Event()
        stop_stream = asyncio.Event()

        async def stream_worker():
            try:
                async with AsyncClient(base_url=BASE, timeout=10.0) as stream_client:
                    async with stream_client.stream(
                        "GET", f"{EVAL_PREFIX}/stream", headers=headers
                    ) as response:
                        assert response.status_code == 200
                        async for line in response.aiter_lines():
                            if "event: heartbeat" in line:
                                connected.set()
                            if stop_stream.is_set():
                                break
            except (asyncio.CancelledError, Exception):
                pass

        task = asyncio.create_task(stream_worker())
        await asyncio.wait_for(connected.wait(), timeout=5.0)

        # Inside connection: metric should reflect baseline + 1
        async with AsyncClient(base_url=BASE, timeout=5.0) as check_client:
            mid_res = await check_client.get(
                f"{EVAL_PREFIX}/stream/connections",
                headers={"X-FlagOps-Key": raw_key},
            )
            assert mid_res.json()["active_connections"] == baseline + 1

        # Signal stop and disconnect
        stop_stream.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0.4)

        # After disconnect: metric must return to baseline
        async with AsyncClient(base_url=BASE, timeout=5.0) as check_client:
            final_res = await check_client.get(
                f"{EVAL_PREFIX}/stream/connections",
                headers={"X-FlagOps-Key": raw_key},
            )
            assert final_res.json()["active_connections"] == baseline


# ==============================================================================
# 5. REDIS FAILURE RESILIENCE (FAIL-OPEN FALLBACK)
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_redis_failure_does_not_crash_server() -> None:
    """When Redis is down or disabled, SSE generator yields heartbeat fallback without crashing."""
    mock_request = MagicMock(spec=Request)
    mock_request.is_disconnected = None
    env_id = uuid.uuid4()

    with patch("app.api.eval.router.get_redis_pool", return_value=None):
        gen = _ruleset_event_stream(env_id, request=mock_request, heartbeat_interval=0.1)
        # First event is heartbeat
        first_event = await gen.__anext__()
        assert first_event.event == "heartbeat"
        assert first_event.data == "{}"
        await gen.aclose()


# ==============================================================================
# 6. 100 CONCURRENT SSE CONNECTIONS DO NOT FREEZE SERVER
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_100_concurrent_connections() -> None:
    """100 simultaneous SSE connections do not freeze or crash server."""
    import httpx

    limits = httpx.Limits(max_connections=250, max_keepalive_connections=200)
    worker_timeout = httpx.Timeout(connect=15.0, read=None, write=10.0, pool=None)
    async with AsyncClient(base_url=BASE, timeout=worker_timeout, limits=limits) as stream_client:
        async with AsyncClient(base_url=BASE, timeout=10.0) as check_client:
            _, admin_headers = await create_and_login_user(check_client)
            _, _, envs, raw_key = await setup_env_with_key(check_client, admin_headers)

            metric_res = await check_client.get(
                f"{EVAL_PREFIX}/stream/connections",
                headers={"X-FlagOps-Key": raw_key},
            )
            baseline = metric_res.json()["active_connections"]

            num_connections = 100
            headers = {"X-FlagOps-Key": raw_key}
            connected_events = [asyncio.Event() for _ in range(num_connections)]

            async def worker(idx: int):
                try:
                    async with stream_client.stream(
                        "GET",
                        f"{EVAL_PREFIX}/stream",
                        headers=headers,
                        timeout=worker_timeout,
                    ) as resp:
                        assert resp.status_code == 200
                        async for line in resp.aiter_lines():
                            if "event: heartbeat" in line:
                                connected_events[idx].set()
                except (asyncio.CancelledError, httpx.HTTPError):
                    pass

            tasks = [asyncio.create_task(worker(i)) for i in range(num_connections)]

            # Wait for all 100 workers to connect and receive initial heartbeat
            await asyncio.wait_for(
                asyncio.gather(*[e.wait() for e in connected_events]),
                timeout=15.0,
            )

            # Check that server is fully responsive and metric reflects 100 connections
            metric_active = await check_client.get(
                f"{EVAL_PREFIX}/stream/connections",
                headers={"X-FlagOps-Key": raw_key},
            )
            assert metric_active.json()["active_connections"] >= baseline + num_connections

            # Test server responsiveness under load
            ping_res = await check_client.get("/health")
            assert ping_res.status_code == 200

            # Disconnect all 100 connections
            for t in tasks:
                t.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.5)

            # Verify active connections returned to baseline
            metric_after = await check_client.get(
                f"{EVAL_PREFIX}/stream/connections",
                headers={"X-FlagOps-Key": raw_key},
            )
            assert metric_after.json()["active_connections"] == baseline
