"""Integration tests for Slice 9 — Config Center.

Covers:
1. Sửa item → client GET config vẫn thấy giá trị CŨ (chưa publish)
2. Publish → client thấy giá trị mới
3. Version tăng tuần tự 1, 2, 3
4. Diff 4 trường hợp (added, removed, changed, unchanged) cả pending lẫn giữa 2 releases
5. Rollback tạo v4, v1/v2/v3 vẫn còn nguyên, giá trị quay về đúng v1
6. Secret: lưu mã hóa (đọc DB thấy ciphertext), API trả masked, reveal cần quyền ADMIN
7. Schema sai → 400 CONFIG_VALIDATION_FAILED và KHÔNG có release mới được tạo
8. Developer publish thành công
9. ETag / 304 Not Modified cho client evaluation
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.crypto import MASKED_SECRET, decrypt_secret
from app.core.database import async_session_factory
from app.main import app
from app.models.audit import AuditLog
from app.models.config import ConfigItem

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
CONFIG_PREFIX = "/api/v1"
EVAL_PREFIX = "/eval/v1"
STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"config-test-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str = "cfg") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient, email: str | None = None) -> tuple[dict, dict]:
    user_email = email or _unique_email()
    reg_res = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": user_email, "password": STRONG_PASSWORD, "full_name": "Config Tester"},
    )
    user_data = reg_res.json()
    login_res = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": user_email, "password": STRONG_PASSWORD},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return user_data, headers


async def setup_env_with_keys(
    client: AsyncClient, admin_headers: dict
) -> tuple[dict, dict, list[dict], str, str]:
    """Create org, project, environments, server and client API keys."""
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "Config Org", "slug": _unique_slug("corg")},
        headers=admin_headers,
    )
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "Config Project", "slug": _unique_slug("cproj")},
        headers=admin_headers,
    )
    project = proj_res.json()

    envs_res = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=admin_headers,
    )
    envs = envs_res.json()
    dev_env = next(e for e in envs if e["key"] == "development")

    # Create SERVER api key
    srv_res = await client.post(
        f"/api/v1/environments/{dev_env['id']}/api-keys",
        json={"name": "Server Key", "scope": "SERVER"},
        headers=admin_headers,
    )
    srv_key = srv_res.json()["key"]

    # Create CLIENT api key
    cli_res = await client.post(
        f"/api/v1/environments/{dev_env['id']}/api-keys",
        json={"name": "Client Key", "scope": "CLIENT"},
        headers=admin_headers,
    )
    cli_key = cli_res.json()["key"]

    return org, project, envs, srv_key, cli_key


# ==============================================================================
# 1. DRAFT CHANGES INVISIBLE TO CLIENT UNTIL PUBLISH & 2. VERSION INCREMENTS
# ==============================================================================


@pytest.mark.asyncio
async def test_draft_changes_invisible_to_client_until_publish() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, project, envs, srv_key, _ = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        # 1. Create namespace
        ns_name = f"app_{uuid.uuid4().hex[:6]}"
        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": ns_name, "format": "JSON"},
            headers=admin_headers,
        )
        assert ns_res.status_code == 201
        ns_id = ns_res.json()["id"]

        # 2. Add draft item and publish v1
        put_res = await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={"items": [{"key": "db.pool", "value": "10", "value_type": "INT"}]},
            headers=admin_headers,
        )
        assert put_res.status_code == 200

        pub1_res = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            json={"comment": "First release"},
            headers=admin_headers,
        )
        assert pub1_res.status_code == 201
        assert pub1_res.json()["version"] == 1

        # Client reads config -> gets 10
        eval_headers = {"X-FlagOps-Key": srv_key}
        res1 = await client.get(f"{EVAL_PREFIX}/config/{ns_name}", headers=eval_headers)
        assert res1.status_code == 200
        assert res1.json()["version"] == 1
        assert res1.json()["configs"]["db.pool"] == "10"

        # 3. Update draft item to 50 (WITHOUT publishing)
        put2_res = await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={"items": [{"key": "db.pool", "value": "50", "value_type": "INT"}]},
            headers=admin_headers,
        )
        assert put2_res.status_code == 200

        # Client STILL sees old value 10!
        res_still_old = await client.get(f"{EVAL_PREFIX}/config/{ns_name}", headers=eval_headers)
        assert res_still_old.status_code == 200
        assert res_still_old.json()["version"] == 1
        assert res_still_old.json()["configs"]["db.pool"] == "10"

        # 4. Publish v2
        pub2_res = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            json={"comment": "Second release"},
            headers=admin_headers,
        )
        assert pub2_res.status_code == 201
        assert pub2_res.json()["version"] == 2

        # Client now sees new value 50 and version 2!
        res_new = await client.get(f"{EVAL_PREFIX}/config/{ns_name}", headers=eval_headers)
        assert res_new.status_code == 200
        assert res_new.json()["version"] == 2
        assert res_new.json()["configs"]["db.pool"] == "50"


@pytest.mark.asyncio
async def test_version_increments_1_2_3() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, _, _ = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": f"seq_{uuid.uuid4().hex[:6]}", "format": "JSON"},
            headers=admin_headers,
        )
        ns_id = ns_res.json()["id"]

        for expected_version in (1, 2, 3):
            await client.put(
                f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
                json={"items": [{"key": "v_key", "value": str(expected_version)}]},
                headers=admin_headers,
            )
            rel_res = await client.post(
                f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
                headers=admin_headers,
            )
            assert rel_res.status_code == 201
            assert rel_res.json()["version"] == expected_version


# ==============================================================================
# 3. DIFF 4 CASES (ADDED, REMOVED, CHANGED, UNCHANGED)
# ==============================================================================


@pytest.mark.asyncio
async def test_diff_four_cases() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, _, _ = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": f"diff_{uuid.uuid4().hex[:6]}", "format": "JSON"},
            headers=admin_headers,
        )
        ns_id = ns_res.json()["id"]

        # 1. Base release v1 with keep_me, del_me, change_me
        await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={
                "items": [
                    {"key": "keep_me", "value": "same"},
                    {"key": "del_me", "value": "old_delete"},
                    {"key": "change_me", "value": "old_change"},
                ]
            },
            headers=admin_headers,
        )
        pub1 = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )
        assert pub1.status_code == 201

        # 2. Update draft to keep_me, change_me (modified), add_me (new). del_me removed.
        await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={
                "items": [
                    {"key": "keep_me", "value": "same"},
                    {"key": "change_me", "value": "new_change"},
                    {"key": "add_me", "value": "brand_new"},
                ]
            },
            headers=admin_headers,
        )

        # Check pending-diff
        pdiff_res = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/pending-diff",
            headers=admin_headers,
        )
        assert pdiff_res.status_code == 200
        diff = pdiff_res.json()
        assert diff["added"] == {"add_me": "brand_new"}
        assert diff["removed"] == {"del_me": "old_delete"}
        assert diff["changed"] == {"change_me": {"old": "old_change", "new": "new_change"}}
        assert diff["unchanged"] == {"keep_me": "same"}

        # 3. Publish v2 and check release-to-release diff
        pub2 = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )
        assert pub2.status_code == 201

        r_diff_res = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases/1/diff/2",
            headers=admin_headers,
        )
        assert r_diff_res.status_code == 200
        r_diff = r_diff_res.json()
        assert r_diff["added"] == {"add_me": "brand_new"}
        assert r_diff["removed"] == {"del_me": "old_delete"}
        assert r_diff["changed"] == {"change_me": {"old": "old_change", "new": "new_change"}}
        assert r_diff["unchanged"] == {"keep_me": "same"}


# ==============================================================================
# 4. ROLLBACK CREATES V4, PRESERVES V1/V2/V3, RECOVERS VALUE
# ==============================================================================


@pytest.mark.asyncio
async def test_rollback_creates_new_release_and_preserves_history() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, srv_key, _ = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        ns_name = f"rb_{uuid.uuid4().hex[:6]}"
        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": ns_name, "format": "JSON"},
            headers=admin_headers,
        )
        ns_id = ns_res.json()["id"]

        # Create v1, v2, v3
        for v in (1, 2, 3):
            await client.put(
                f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
                json={"items": [{"key": "feature_param", "value": f"value_v{v}"}]},
                headers=admin_headers,
            )
            await client.post(
                f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
                headers=admin_headers,
            )

        # Rollback to v1
        rb_res = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases/1/rollback",
            headers=admin_headers,
        )
        assert rb_res.status_code == 200
        rb_data = rb_res.json()
        assert rb_data["version"] == 4, f"Rollback must create version 4, got {rb_data['version']}"
        assert rb_data["is_rollback_of"] is not None

        # Verify all releases v1, v2, v3, v4 are preserved intact
        list_res = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )
        assert list_res.status_code == 200
        versions = [r["version"] for r in list_res.json()]
        assert versions == [4, 3, 2, 1], f"Expected [4, 3, 2, 1], got {versions}"

        # Client now gets exact value from v1!
        eval_headers = {"X-FlagOps-Key": srv_key}
        eval_res = await client.get(f"{EVAL_PREFIX}/config/{ns_name}", headers=eval_headers)
        assert eval_res.status_code == 200
        assert eval_res.json()["version"] == 4
        assert eval_res.json()["configs"]["feature_param"] == "value_v1"


# ==============================================================================
# 5. SECRET ENCRYPTION, MASKING & REVEAL PERMISSIONS
# ==============================================================================


@pytest.mark.asyncio
async def test_secret_encryption_and_reveal_permissions() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        org, _, envs, srv_key, cli_key = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        ns_name = f"sec_{uuid.uuid4().hex[:6]}"
        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": ns_name, "format": "JSON"},
            headers=admin_headers,
        )
        ns_id = ns_res.json()["id"]

        raw_secret = "P@ssw0rd_Very_Secret_42!"
        await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={
                "items": [
                    {
                        "key": "db.password",
                        "value": raw_secret,
                        "value_type": "STRING",
                        "is_secret": True,
                    }
                ]
            },
            headers=admin_headers,
        )

        # 1. Verify direct DB read shows ciphertext, NOT raw plaintext
        async with async_session_factory() as session:
            db_item = await session.scalar(
                select(ConfigItem).where(
                    ConfigItem.namespace_id == uuid.UUID(ns_id),
                    ConfigItem.key == "db.password",
                )
            )
            assert db_item is not None
            assert db_item.value != raw_secret, "DB must store encrypted ciphertext, not plaintext!"
            assert decrypt_secret(db_item.value) == raw_secret

        # 2. GET draft without reveal returns masked "••••••"
        get_masked = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            headers=admin_headers,
        )
        assert get_masked.status_code == 200
        assert get_masked.json()[0]["value"] == MASKED_SECRET

        # 3. GET draft with reveal=True as ADMIN returns plaintext & logs audit
        get_reveal = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items?reveal=true",
            headers=admin_headers,
        )
        assert get_reveal.status_code == 200
        assert get_reveal.json()[0]["value"] == raw_secret

        # Check audit log
        async with async_session_factory() as session:
            audit = await session.scalar(
                select(AuditLog)
                .where(AuditLog.action == "config.secret_revealed")
                .order_by(AuditLog.created_at.desc())
            )
            assert audit is not None
            assert audit.after is not None
            assert "db.password" in audit.after["revealed_keys"]

        # 4. Create a non-admin user (VIEWER) and verify 403 on reveal
        viewer_user, viewer_headers = await create_and_login_user(client)
        # Add to org as VIEWER
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": viewer_user["id"], "role": "VIEWER"},
            headers=admin_headers,
        )
        forbidden_res = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items?reveal=true",
            headers=viewer_headers,
        )
        assert forbidden_res.status_code == 403

        # 5. Publish release
        await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )

        # 6. Client endpoint evaluation: SERVER key gets plaintext, CLIENT key gets mask
        srv_eval = await client.get(
            f"{EVAL_PREFIX}/config/{ns_name}",
            headers={"X-FlagOps-Key": srv_key},
        )
        assert srv_eval.status_code == 200
        assert srv_eval.json()["configs"]["db.password"] == raw_secret

        cli_eval = await client.get(
            f"{EVAL_PREFIX}/config/{ns_name}",
            headers={"X-FlagOps-Key": cli_key},
        )
        assert cli_eval.status_code == 200
        assert cli_eval.json()["configs"]["db.password"] == MASKED_SECRET


# ==============================================================================
# 6. JSON SCHEMA VALIDATION PREVENTS RELEASE CREATION ON FAILURE
# ==============================================================================


@pytest.mark.asyncio
async def test_schema_validation_prevents_release_on_failure() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        _, _, envs, _, _ = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": f"schema_{uuid.uuid4().hex[:6]}", "format": "JSON"},
            headers=admin_headers,
        )
        ns_id = ns_res.json()["id"]

        # Item with schema: must be integer >= 10. We give value = 5 (INVALID)
        schema = {"type": "integer", "minimum": 10}
        await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={
                "items": [
                    {
                        "key": "server.port",
                        "value": "5",
                        "value_type": "INT",
                        "json_schema": schema,
                    }
                ]
            },
            headers=admin_headers,
        )

        # Publish should fail with 400 CONFIG_VALIDATION_FAILED
        pub_fail = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )
        assert pub_fail.status_code == 400
        err = pub_fail.json()["error"]
        assert err["code"] == "CONFIG_VALIDATION_FAILED"
        assert "server.port" in err["details"]["errors"]

        # Verify NO release was created!
        list_rels = await client.get(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )
        assert len(list_rels.json()) == 0

        # Fix value to 8080 (>= 10, VALID)
        await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={
                "items": [
                    {
                        "key": "server.port",
                        "value": "8080",
                        "value_type": "INT",
                        "json_schema": schema,
                    }
                ]
            },
            headers=admin_headers,
        )

        # Publish now succeeds
        pub_ok = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=admin_headers,
        )
        assert pub_ok.status_code == 201
        assert pub_ok.json()["version"] == 1


# ==============================================================================
# 7. DEVELOPER CAN PUBLISH & 8. ETAG / 304 NOT MODIFIED
# ==============================================================================


@pytest.mark.asyncio
async def test_developer_publish_and_etag_304() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, admin_headers = await create_and_login_user(client)
        org, _, envs, srv_key, _ = await setup_env_with_keys(client, admin_headers)
        dev_env = next(e for e in envs if e["key"] == "development")

        # Create developer user
        dev_user, dev_headers = await create_and_login_user(client)
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": dev_user["id"], "role": "DEVELOPER"},
            headers=admin_headers,
        )

        ns_name = f"devpub_{uuid.uuid4().hex[:6]}"
        ns_res = await client.post(
            f"{CONFIG_PREFIX}/environments/{dev_env['id']}/namespaces",
            json={"name": ns_name, "format": "JSON"},
            headers=dev_headers,
        )
        assert ns_res.status_code == 201
        ns_id = ns_res.json()["id"]

        # Developer can update items and publish
        await client.put(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/items",
            json={"items": [{"key": "timeout", "value": "3000"}]},
            headers=dev_headers,
        )
        pub_res = await client.post(
            f"{CONFIG_PREFIX}/namespaces/{ns_id}/releases",
            headers=dev_headers,
        )
        assert pub_res.status_code == 201
        assert pub_res.json()["version"] == 1

        # Test ETag / 304 Not Modified
        eval_headers = {"X-FlagOps-Key": srv_key}
        res = await client.get(f"{EVAL_PREFIX}/config/{ns_name}", headers=eval_headers)
        assert res.status_code == 200
        assert "ETag" in res.headers
        etag = res.headers["ETag"]

        # Call again with If-None-Match
        res_304 = await client.get(
            f"{EVAL_PREFIX}/config/{ns_name}",
            headers={"X-FlagOps-Key": srv_key, "If-None-Match": etag},
        )
        assert res_304.status_code == 304
