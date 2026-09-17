"""Integration tests for Slice 8 — Redis cache, Pub/Sub, and rate limiting.

Covers:
- Cache miss → DB query → cache populated → second call uses cache (no DB)
- Flag mutation invalidates cache, next call returns fresh data
- Pub/Sub: publish on invalidation → subscriber receives message
- Rate limit exceeded → 429 with Retry-After header
- Redis down → eval API still returns 200 (fail-open), log warning
- REDIS_ENABLED=false → evaluation endpoints still pass
"""

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event

from app.core.config import settings
from app.core.database import engine
from app.core.redis import get_redis_pool
from app.main import app
from app.services import ruleset_cache

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
EVAL_PREFIX = "/eval/v1"
STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"redis-test-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    email = _unique_email()
    await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Redis Tester"},
    )
    login_res = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return tokens, headers


async def setup_env_with_key(
    client: AsyncClient, admin_headers: dict
) -> tuple[dict, dict, list[dict], str]:
    """Create org, project, environments, and server API key."""
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "Redis Org", "slug": _unique_slug("rorg")},
        headers=admin_headers,
    )
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "Redis Project", "slug": _unique_slug("rproj")},
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
        json={"name": "Redis Server Key", "scope": "SERVER"},
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


class QueryCounter:
    """Context manager to count SQL statements executed on the engine."""

    def __init__(self) -> None:
        self.count = 0
        self._engine = engine.sync_engine

    def __enter__(self) -> "QueryCounter":
        self.count = 0
        event.listen(self._engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, *args: Any) -> None:
        event.remove(self._engine, "before_cursor_execute", self._callback)

    def _callback(self, *args: Any, **kwargs: Any) -> None:
        self.count += 1


# ==============================================================================
# 1. CACHE MISS → DB → CACHE HIT (SECOND CALL SKIPS DB)
# ==============================================================================


@pytest.mark.asyncio
async def test_cache_miss_then_hit() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, raw_key = await setup_env_with_key(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        flag_key = f"cf_{uuid.uuid4().hex[:6]}"
        await create_boolean_flag(client, admin_headers, project["id"], flag_key)

        eval_headers = {"X-FlagOps-Key": raw_key}

        # First call: cache miss, must load bundle from DB
        with QueryCounter() as qc_miss:
            res1 = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
        assert res1.status_code == 200
        payload1 = res1.json()
        assert "flags" in payload1
        assert flag_key in payload1["flags"]
        queries_on_miss = qc_miss.count

        # Verify cache is now populated in Redis
        pool = get_redis_pool()
        if pool is not None:
            cached = await pool.get(f"ruleset:{dev_env['id']}")
            assert cached is not None, "Cache should be populated after first fetch"

            # Second call: cache hit, skips DB query for ruleset bundle
            with QueryCounter() as qc_hit:
                res2 = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
            assert res2.status_code == 200
            assert res2.json()["rulesetVersion"] == payload1["rulesetVersion"]
            queries_on_hit = qc_hit.count

            # Query count on hit must be strictly less than on miss (no load_ruleset_bundle queries)
            assert queries_on_hit < queries_on_miss, (
                f"Cache hit queries ({queries_on_hit}) should be less than miss ({queries_on_miss})"
            )


# ==============================================================================
# 2. FLAG CHANGE INVALIDATES CACHE
# ==============================================================================


@pytest.mark.asyncio
async def test_flag_change_invalidates_cache() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, raw_key = await setup_env_with_key(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        flag_key = f"inv_{uuid.uuid4().hex[:6]}"
        await create_boolean_flag(client, admin_headers, project["id"], flag_key)

        eval_headers = {"X-FlagOps-Key": raw_key}

        # Populate cache
        res1 = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
        assert res1.status_code == 200
        v1 = res1.json()["rulesetVersion"]
        assert res1.json()["flags"][flag_key]["enabled"] is False

        # Find flag id and mutate environment setting (enable flag: False -> True)
        flag_res = await client.get(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            headers=admin_headers,
        )
        flag = next(f for f in flag_res.json() if f["key"] == flag_key)
        put_setting_res = await client.put(
            f"/api/v1/flags/{flag['id']}/environments/{dev_env['id']}",
            json={"enabled": True},
            headers=admin_headers,
        )
        assert put_setting_res.status_code == 200
        assert put_setting_res.json()["enabled"] is True

        # Verify cache key is deleted from Redis
        pool = get_redis_pool()
        if pool is not None:
            cached = await pool.get(f"ruleset:{dev_env['id']}")
            assert cached is None, "Cache should be invalidated after flag mutation"

        # Next fetch returns new version AND fresh data reflecting the change
        res2 = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
        assert res2.status_code == 200
        payload2 = res2.json()
        v2 = payload2["rulesetVersion"]
        assert v2 > v1, f"Version should have incremented: {v2} > {v1}"
        assert payload2["flags"][flag_key]["enabled"] is True, (
            "Fresh fetch should reflect enabled flag"
        )


# ==============================================================================
# 3. PUB/SUB: PUBLISH ON INVALIDATION → SUBSCRIBER RECEIVES MESSAGE
# ==============================================================================


@pytest.mark.asyncio
async def test_pubsub_subscriber_receives_message() -> None:
    pool = get_redis_pool()
    if pool is None:
        pytest.skip("Redis disabled")

    env_id = uuid.uuid4()
    channel = f"flagops:ruleset:{env_id}"

    pubsub = pool.pubsub()
    await pubsub.subscribe(channel)
    # Consume the subscription confirmation message
    await pubsub.get_message(timeout=1)

    # Publish via invalidation
    await ruleset_cache.invalidate(env_id)

    # Wait briefly for message propagation
    msg = await pubsub.get_message(timeout=2)
    assert str(env_id) in msg["data"]

    await pubsub.unsubscribe(channel)
    await pubsub.aclose()


# ==============================================================================
# 4. RATE LIMIT EXCEEDED → 429 WITH RETRY-AFTER
# ==============================================================================


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429() -> None:
    if get_redis_pool() is None:
        pytest.skip("Redis disabled")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, raw_key = await setup_env_with_key(client, admin_headers)

        await create_boolean_flag(
            client, admin_headers, project["id"], f"rl_{uuid.uuid4().hex[:6]}"
        )

        eval_headers = {"X-FlagOps-Key": raw_key}

        # Set a very low rate limit for this test
        original_limit = settings.EVAL_RATE_LIMIT_PER_MINUTE
        settings.EVAL_RATE_LIMIT_PER_MINUTE = 3

        try:
            # Make requests up to the limit
            for _ in range(3):
                res = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
                assert res.status_code in (200, 304)

            # Next request should be rate-limited
            res_limited = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
            assert res_limited.status_code == 429
            assert res_limited.json()["error"]["code"] == "RATE_LIMITED"
            assert "Retry-After" in res_limited.headers
            assert "X-RateLimit-Remaining" in res_limited.headers
        finally:
            settings.EVAL_RATE_LIMIT_PER_MINUTE = original_limit


# ==============================================================================
# 5. REDIS DOWN → API STILL RETURNS 200 (FAIL-OPEN)
# ==============================================================================


@pytest.mark.asyncio
async def test_redis_down_api_still_returns_200() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, raw_key = await setup_env_with_key(client, admin_headers)

        await create_boolean_flag(
            client, admin_headers, project["id"], f"rd_{uuid.uuid4().hex[:6]}"
        )

        eval_headers = {"X-FlagOps-Key": raw_key}

        # Mock Redis pool to raise ConnectionError on every call
        import app.services.ruleset_cache as rc_module

        mock_pool = type(
            "BrokenPool",
            (),
            {
                "get": staticmethod(lambda *a, **kw: _raise_conn_error()),
                "set": staticmethod(lambda *a, **kw: _raise_conn_error()),
                "delete": staticmethod(lambda *a, **kw: _raise_conn_error()),
                "publish": staticmethod(lambda *a, **kw: _raise_conn_error()),
                "incr": staticmethod(lambda *a, **kw: _raise_conn_error()),
                "expire": staticmethod(lambda *a, **kw: _raise_conn_error()),
            },
        )()

        with patch.object(rc_module, "get_redis_pool", return_value=mock_pool):
            res = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
            # Must still work — falls through to PostgreSQL
            assert res.status_code == 200
            assert "flags" in res.json()


async def _raise_conn_error() -> None:
    raise RedisConnectionError("Simulated Redis outage")


# ==============================================================================
# 6. REDIS_ENABLED=false → EVALUATION ENDPOINTS STILL PASS
# ==============================================================================


@pytest.mark.asyncio
async def test_redis_disabled_evaluation_passes() -> None:
    original = settings.REDIS_ENABLED
    settings.REDIS_ENABLED = False

    # Force pool to None
    import app.core.redis as redis_mod

    old_pool = redis_mod._pool
    redis_mod._pool = None

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            _, admin_headers = await create_and_login_user(client)
            _, project, envs, raw_key = await setup_env_with_key(client, admin_headers)

            await create_boolean_flag(
                client, admin_headers, project["id"], f"dis_{uuid.uuid4().hex[:6]}"
            )

            eval_headers = {"X-FlagOps-Key": raw_key}

            # Ruleset endpoint works
            res = await client.get(f"{EVAL_PREFIX}/ruleset", headers=eval_headers)
            assert res.status_code == 200
            assert "flags" in res.json()

            # Evaluate single flag works
            flag_key = list(res.json()["flags"].keys())[0]
            res2 = await client.post(
                f"{EVAL_PREFIX}/flags/{flag_key}/evaluate",
                json={"context": {"userId": "user1"}},
                headers=eval_headers,
            )
            assert res2.status_code == 200
    finally:
        settings.REDIS_ENABLED = original
        redis_mod._pool = old_pool
