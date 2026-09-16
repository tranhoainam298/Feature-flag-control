"""Tests for Slice 7 — Evaluation API (Hot Path).

Covers:
- POST /eval/v1/flags/{flag_key}/evaluate (correct value, variant, reason)
- POST /eval/v1/flags/evaluate-all (all environment flags)
- GET  /eval/v1/ruleset (ETag header, 304 Not Modified when version matches)
- Flag update bumps version, changes ETag, returns 200 with new ruleset
- CLIENT key visibility filtering (does not see private flags)
- Environment isolation (dev key cannot read prod ruleset -> 403)
- Revoked key returns 401
- Missing or non-existent key returns 401
- N+1 query prevention: 50 flags ruleset must execute < 5 queries
- POST /eval/v1/events batches events with SHA-256 hashed context_key
- EvaluationTracker batches last_evaluated_at updates
"""

import asyncio
import hashlib
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select

from app.core.database import async_session_factory, engine
from app.main import app
from app.models.enums import ApiKeyScope
from app.models.evaluation import EvaluationEvent
from app.models.flag import (
    Flag,
    FlagEnvironmentSetting,
    IndividualOverride,
    TargetingRule,
    Variation,
)
from app.models.organization import Organization
from app.models.project import Environment, Project
from app.services.eval import eval_tracker, load_ruleset_bundle

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
FLAG_PREFIX = "/api/v1/flags"
EVAL_PREFIX = "/eval/v1"
STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"eval-test-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str = "eval") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    email = _unique_email()
    await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Eval User"},
    )
    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    token = login_resp.json()["access_token"]
    return login_resp.json(), {"Authorization": f"Bearer {token}"}


async def setup_environment_with_keys(
    client: AsyncClient, admin_headers: dict
) -> tuple[dict, dict, list[dict], str, str]:
    """Helper to set up Org, Project, Envs, and both Server and Client API keys."""
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "Eval Org", "slug": _unique_slug("org")},
        headers=admin_headers,
    )
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "Eval Project", "slug": _unique_slug("proj")},
        headers=admin_headers,
    )
    project = proj_res.json()

    envs_res = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=admin_headers,
    )
    envs = envs_res.json()
    dev_env = next(e for e in envs if e["key"] == "development")

    # Create Server API Key
    srv_key_res = await client.post(
        f"/api/v1/environments/{dev_env['id']}/api-keys",
        json={"name": "Server Key", "scope": "SERVER"},
        headers=admin_headers,
    )
    server_key = srv_key_res.json()["key"]

    # Create Client API Key
    cli_key_res = await client.post(
        f"/api/v1/environments/{dev_env['id']}/api-keys",
        json={"name": "Client Key", "scope": "CLIENT"},
        headers=admin_headers,
    )
    client_key = cli_key_res.json()["key"]

    return org, project, envs, server_key, client_key


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
# 1. EVALUATION TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_evaluate_single_flag_returns_correct_value_variant_reason() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, server_key, _ = await setup_environment_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        # Create flag
        flag_key = f"feature_{uuid.uuid4().hex[:6]}"
        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={"key": flag_key, "name": "Feature X", "type": "BOOLEAN"},
            headers=admin_headers,
        )
        flag = flag_res.json()
        var_true = next(v for v in flag["variations"] if v["value"] is True)
        var_false = next(v for v in flag["variations"] if v["value"] is False)

        # Enable in dev
        await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}",
            json={
                "enabled": True,
                "default_variation_id": var_false["id"],
                "off_variation_id": var_false["id"],
            },
            headers=admin_headers,
        )

        # Set Individual Override for user_special -> True
        await client.post(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/overrides",
            json={"context_key": "user_special", "variation_id": var_true["id"]},
            headers=admin_headers,
        )

        # Evaluate 1: user_normal -> default variation (False, DEFAULT)
        res_norm = await client.post(
            f"{EVAL_PREFIX}/flags/{flag_key}/evaluate",
            json={"context": {"targetingKey": "user_normal"}},
            headers={"X-FlagOps-Key": server_key},
        )
        assert res_norm.status_code == 200
        data_norm = res_norm.json()
        assert data_norm["flagKey"] == flag_key
        assert data_norm["value"] is False
        assert data_norm["variant"] == "off"
        assert data_norm["reason"] == "DEFAULT"

        # Evaluate 2: user_special -> override variation (True, TARGETING_MATCH)
        res_spec = await client.post(
            f"{EVAL_PREFIX}/flags/{flag_key}/evaluate",
            json={"context": {"targetingKey": "user_special"}},
            headers={"X-FlagOps-Key": server_key},
        )
        assert res_spec.status_code == 200
        data_spec = res_spec.json()
        assert data_spec["value"] is True
        assert data_spec["variant"] == "on"
        assert data_spec["reason"] == "TARGETING_MATCH"


@pytest.mark.asyncio
async def test_evaluate_all_returns_all_environment_flags() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, server_key, _ = await setup_environment_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        keys = [f"batch_f_{i}_{uuid.uuid4().hex[:4]}" for i in range(3)]
        for k in keys:
            f_res = await client.post(
                f"{PROJECT_PREFIX}/{project['id']}/flags",
                json={"key": k, "name": f"Flag {k}", "type": "BOOLEAN"},
                headers=admin_headers,
            )
            flag = f_res.json()
            await client.put(
                f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}",
                json={"enabled": True},
                headers=admin_headers,
            )

        res_all = await client.post(
            f"{EVAL_PREFIX}/flags/evaluate-all",
            json={"context": {"targetingKey": "global_user"}},
            headers={"X-FlagOps-Key": server_key},
        )
        assert res_all.status_code == 200
        flags = res_all.json()["flags"]
        for k in keys:
            assert k in flags
            assert "value" in flags[k]
            assert "variant" in flags[k]
            assert "reason" in flags[k]


# ==============================================================================
# 2. ETAG & 304 NOT MODIFIED TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_ruleset_etag_header_and_304_not_modified() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, _, server_key, _ = await setup_environment_with_keys(client, admin_headers)

        # 1. First fetch -> 200 OK + ETag header
        res1 = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": server_key},
        )
        assert res1.status_code == 200
        assert "etag" in res1.headers
        etag1 = res1.headers["etag"]
        assert len(etag1) > 0
        data1 = res1.json()
        assert "rulesetVersion" in data1
        assert "flags" in data1

        # 2. Second fetch with If-None-Match -> 304 Not Modified
        res2 = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": server_key, "If-None-Match": etag1},
        )
        assert res2.status_code == 304
        assert len(res2.content) == 0  # Body MUST be empty on 304
        assert res2.headers.get("etag") == etag1


@pytest.mark.asyncio
async def test_flag_change_bumps_version_and_invalidates_etag() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, server_key, _ = await setup_environment_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        # Create flag
        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={"key": f"f_{uuid.uuid4().hex[:6]}", "name": "Dynamic Flag", "type": "BOOLEAN"},
            headers=admin_headers,
        )
        flag = flag_res.json()

        # Initial ruleset fetch -> ETag 1
        res1 = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": server_key},
        )
        assert res1.status_code == 200
        etag1 = res1.headers["etag"]

        # Modify flag setting -> bumps ruleset_version
        await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}",
            json={"enabled": True},
            headers=admin_headers,
        )

        # Fetch with previous If-None-Match -> 200 OK because version changed!
        res2 = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": server_key, "If-None-Match": etag1},
        )
        assert res2.status_code == 200
        etag2 = res2.headers["etag"]
        assert etag2 != etag1


# ==============================================================================
# 3. CLIENT KEY & ENVIRONMENT ISOLATION TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_client_key_does_not_see_private_flag() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, server_key, client_key = await setup_environment_with_keys(
            client, admin_headers
        )

        # Flag 1: Private (is_client_visible = False)
        priv_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={"key": f"priv_{uuid.uuid4().hex[:6]}", "name": "Private Flag", "type": "BOOLEAN"},
            headers=admin_headers,
        )
        flag_priv = priv_res.json()

        # Flag 2: Public (is_client_visible = True)
        pub_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={"key": f"pub_{uuid.uuid4().hex[:6]}", "name": "Public Flag", "type": "BOOLEAN"},
            headers=admin_headers,
        )
        flag_pub = pub_res.json()
        await client.patch(
            f"{FLAG_PREFIX}/{flag_pub['id']}",
            json={"is_client_visible": True},
            headers=admin_headers,
        )

        # 1. Server key ruleset sees BOTH flags
        res_srv = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": server_key},
        )
        assert res_srv.status_code == 200
        srv_flags = res_srv.json()["flags"]
        assert flag_priv["key"] in srv_flags
        assert flag_pub["key"] in srv_flags

        # 2. Client key ruleset ONLY sees public flag
        res_cli = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": client_key},
        )
        assert res_cli.status_code == 200
        cli_flags = res_cli.json()["flags"]
        assert flag_pub["key"] in cli_flags
        assert flag_priv["key"] not in cli_flags

        # 3. Client evaluate private flag -> 404
        res_eval_priv = await client.post(
            f"{EVAL_PREFIX}/flags/{flag_priv['key']}/evaluate",
            json={"context": {"targetingKey": "user1"}},
            headers={"X-FlagOps-Key": client_key},
        )
        assert res_eval_priv.status_code == 404
        assert res_eval_priv.json()["error"]["code"] == "FLAG_NOT_FOUND"

        # 4. Client evaluate public flag -> 200
        res_eval_pub = await client.post(
            f"{EVAL_PREFIX}/flags/{flag_pub['key']}/evaluate",
            json={"context": {"targetingKey": "user1"}},
            headers={"X-FlagOps-Key": client_key},
        )
        assert res_eval_pub.status_code == 200


@pytest.mark.asyncio
async def test_dev_key_accessing_prod_ruleset_returns_403() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, dev_server_key, _ = await setup_environment_with_keys(client, admin_headers)
        prod_env = next(e for e in envs if e["key"] == "production")

        # Dev API key attempting to fetch Prod environment ruleset -> 403
        res = await client.get(
            f"{EVAL_PREFIX}/ruleset?environment_id={prod_env['id']}",
            headers={"X-FlagOps-Key": dev_server_key},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_revoked_or_invalid_api_key_returns_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, server_key, _ = await setup_environment_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        # 1. Missing header -> 401
        res_missing = await client.get(f"{EVAL_PREFIX}/ruleset")
        assert res_missing.status_code == 401

        # 2. Fake key -> 401
        res_fake = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": "fo_srv_completely_fake_key_12345"},
        )
        assert res_fake.status_code == 401

        # 3. Revoke key
        keys_list = await client.get(
            f"/api/v1/environments/{dev_env['id']}/api-keys",
            headers=admin_headers,
        )
        key_id = keys_list.json()[0]["id"]
        revoke_res = await client.post(
            f"/api/v1/api-keys/{key_id}/revoke",
            headers=admin_headers,
        )
        assert revoke_res.status_code == 200

        # 4. Revoked key -> 401
        res_revoked = await client.get(
            f"{EVAL_PREFIX}/ruleset",
            headers={"X-FlagOps-Key": server_key},
        )
        assert res_revoked.status_code == 401
        assert res_revoked.json()["error"]["code"] == "UNAUTHORIZED"


# ==============================================================================
# 4. N+1 QUERY PREVENTION TEST (50 FLAGS < 5 QUERIES)
# ==============================================================================


@pytest.mark.asyncio
async def test_n_plus_one_ruleset_50_flags_under_5_queries() -> None:
    async with async_session_factory() as db:
        # Create org, project, and environment directly
        org = Organization(id=uuid.uuid4(), name="N1 Org", slug=f"n1-org-{uuid.uuid4().hex[:6]}")
        db.add(org)
        await db.commit()

        proj = Project(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="N1 Proj",
            slug=f"n1-proj-{uuid.uuid4().hex[:6]}",
        )
        db.add(proj)
        await db.commit()

        env = Environment(
            id=uuid.uuid4(),
            project_id=proj.id,
            name="N+1 Dev",
            key=f"nplusone_dev_{uuid.uuid4().hex[:6]}",
            is_production=False,
            ruleset_version=1,
        )
        db.add(env)
        await db.commit()

        # Create 50 flags with variations
        flags_data = []
        for i in range(50):
            flag = Flag(
                id=uuid.uuid4(),
                project_id=proj.id,
                key=f"bench_flag_{i}",
                name=f"Bench Flag {i}",
                type="BOOLEAN",
            )
            v_on = Variation(id=uuid.uuid4(), flag_id=flag.id, key="on", value=True)
            v_off = Variation(id=uuid.uuid4(), flag_id=flag.id, key="off", value=False)
            flag.variations = [v_on, v_off]
            db.add(flag)
            flags_data.append((flag, v_on, v_off))
        await db.commit()

        # Create 50 settings
        for i, (flag, v_on, v_off) in enumerate(flags_data):
            setting = FlagEnvironmentSetting(
                id=uuid.uuid4(),
                flag_id=flag.id,
                environment_id=env.id,
                enabled=True,
                default_variation_id=v_on.id,
                off_variation_id=v_off.id,
                bucketing_key="userId",
            )
            rule = TargetingRule(
                id=uuid.uuid4(),
                flag_environment_setting_id=setting.id,
                priority=1,
                description=f"Rule for {i}",
                conditions={
                    "operator": "AND",
                    "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                },
                distribution=[{"variation_id": str(v_on.id), "weight": 100.0}],
            )
            override = IndividualOverride(
                id=uuid.uuid4(),
                flag_environment_setting_id=setting.id,
                context_key="alice",
                variation_id=v_on.id,
            )
            setting.targeting_rules = [rule]
            setting.individual_overrides = [override]
            db.add(setting)

        await db.commit()

        # Measure queries during ruleset bundle load
        with QueryCounter() as qc:
            ruleset, _, _ = await load_ruleset_bundle(db, env, ApiKeyScope.SERVER)

        assert len(ruleset.flags) == 50
        # MUST be < 5 queries (zero N+1)
        assert qc.count < 5, f"Expected < 5 queries for 50 flags, got {qc.count}"


# ==============================================================================
# 5. EVALUATION EVENTS BATCH INGESTION (SHA-256 HASHED CONTEXT KEYS)
# ==============================================================================


@pytest.mark.asyncio
async def test_post_evaluation_events_hashes_context_key_and_persists() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, server_key, _ = await setup_environment_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        f_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={"key": f"evt_f_{uuid.uuid4().hex[:6]}", "name": "Event Flag", "type": "BOOLEAN"},
            headers=admin_headers,
        )
        flag = f_res.json()
        var_id = flag["variations"][0]["id"]
        raw_user_id = "user_confidential_123456"

        # Ingest events batch
        payload = {
            "events": [
                {
                    "flag_id": flag["id"],
                    "variation_id": var_id,
                    "reason": "TARGETING_MATCH",
                    "context_key": raw_user_id,
                }
            ]
        }
        res = await client.post(
            f"{EVAL_PREFIX}/events",
            json=payload,
            headers={"X-FlagOps-Key": server_key},
        )
        assert res.status_code == 202
        assert res.json()["status"] == "accepted"
        assert res.json()["count"] == 1

        # Check in database
        async with async_session_factory() as db:
            env_uuid = uuid.UUID(dev_env["id"])
            event_rec = await db.scalar(
                select(EvaluationEvent).where(EvaluationEvent.environment_id == env_uuid)
            )
            assert event_rec is not None
            expected_hash = hashlib.sha256(raw_user_id.encode("utf-8")).hexdigest()
            # Verify SHA-256 hash
            assert event_rec.context_key_hash == expected_hash
            # Verify raw user ID is NOT stored
            assert not hasattr(event_rec, "context_key")


# ==============================================================================
# 6. EVALUATION TRACKER BATCH UPDATES
# ==============================================================================


@pytest.mark.asyncio
async def test_evaluation_tracker_batches_last_evaluated_at() -> None:
    async with async_session_factory() as db:
        slug = f"tr-org-{uuid.uuid4().hex[:6]}"
        org = Organization(id=uuid.uuid4(), name="Tracker Org", slug=slug)
        db.add(org)
        await db.commit()

        proj = Project(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Tracker Proj",
            slug=f"tr-proj-{uuid.uuid4().hex[:6]}",
        )
        db.add(proj)
        await db.commit()

        env = Environment(
            id=uuid.uuid4(),
            project_id=proj.id,
            name="Tracker Dev",
            key=f"tr_dev_{uuid.uuid4().hex[:6]}",
            is_production=False,
            ruleset_version=1,
        )
        db.add(env)
        await db.commit()

        flag = Flag(
            id=uuid.uuid4(),
            project_id=proj.id,
            key=f"tracker_flag_{uuid.uuid4().hex[:6]}",
            name="Tracker Flag",
            type="BOOLEAN",
        )
        db.add(flag)
        setting = FlagEnvironmentSetting(
            id=uuid.uuid4(),
            flag_id=flag.id,
            environment_id=env.id,
            enabled=True,
            last_evaluated_at=None,
        )
        db.add(setting)
        await db.commit()

        # Record in tracker
        await eval_tracker.record(setting.id)

        # Setting in DB is NOT updated yet (buffered)
        refreshed = await db.scalar(
            select(FlagEnvironmentSetting).where(FlagEnvironmentSetting.id == setting.id)
        )
        assert refreshed is not None
        assert refreshed.last_evaluated_at is None

        # Flush batch
        flushed_count = await eval_tracker.flush(db)
        assert flushed_count >= 1

        # Now DB has timestamp
        await db.refresh(refreshed)
        assert refreshed.last_evaluated_at is not None


# ==============================================================================
# 7. SSE STREAM
# ==============================================================================


@pytest.mark.asyncio
async def test_stream_emits_ruleset_updated_event() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, _, _ = await setup_environment_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        async with async_session_factory() as db:
            env_uuid = uuid.UUID(dev_env["id"])
            version = await db.scalar(
                select(Environment.ruleset_version).where(Environment.id == env_uuid)
            )

        from app.api.eval.router import _ruleset_event_stream

        stream = _ruleset_event_stream(env_uuid, poll_interval=0.05, heartbeat_interval=0.05)
        try:
            frame = await asyncio.wait_for(anext(stream), timeout=5)
        finally:
            await stream.aclose()

        assert frame.startswith("event: ruleset_updated")
        assert f'"rulesetVersion": {version}' in frame
