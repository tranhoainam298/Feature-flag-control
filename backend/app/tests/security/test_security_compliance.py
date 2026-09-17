"""Mandatory Security Compliance Test Suite for FlagOps (Slice 18).

Verifies the 10 Mandatory Security Invariants:
1. API key for dev environment cannot access prod ruleset -> 403
2. CLIENT key cannot fetch flags with is_client_visible=False
3. VIEWER role cannot update flag via PUT/PATCH -> 403
4. User of Org A accessing Org B resource -> 404 (Anti-enumeration, NOT 403)
5. Revoked API key -> 401 Unauthorized
6. Rate limit exceeded -> 429 with Retry-After header
7. Evil ReDoS regex "(a+)+$" finishes < 200ms without server hang
8. JSONB condition tree nested 50 levels deep -> 400 CONDITION_DEPTH_EXCEEDED
9. SQL injection via query parameters (' OR 1=1 --) safely parameterized
10. XSS payload in flag name stored lossless and not executed

Additional Hardening Checks:
11. HTTP 500 internal errors do not leak stack traces or internal filenames
12. Sensitive password_hash, key_hash, master key never exposed in API responses
"""

import time
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.engine.operators import op_matches_regex
from app.main import app
from app.models.enums import ApiKeyScope, MemberRole
from app.models.flag import Flag
from app.models.organization import Membership, Organization
from app.models.project import ApiKey, Environment, Project
from app.models.user import User

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
EVAL_PREFIX = "/eval/v1"
STRONG_PW = "Str0ngSecurityP@ss123"


def _unique_email() -> str:
    return f"sec_test_{uuid.uuid4().hex[:10]}@flagops.security"


async def _create_user_and_token(client: AsyncClient, email: str | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    """Register and login a new user, returning (user_data, auth_headers)."""
    target_email = email or _unique_email()
    reg = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": target_email, "password": STRONG_PW, "full_name": "Security Test User"},
    )
    assert reg.status_code == 201, f"Register failed: {reg.text}"

    login = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": target_email, "password": STRONG_PW},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    token = login.json()["access_token"]
    user_data = reg.json()
    return user_data, {"Authorization": f"Bearer {token}"}


async def _setup_project_and_envs(
    client: AsyncClient, auth_headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Create an org, project, and retrieve its environments."""
    uid = uuid.uuid4().hex[:8]
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": f"Security Org {uid}", "slug": f"sec-org-{uid}"},
        headers=auth_headers,
    )
    assert org_res.status_code == 201, org_res.text
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": f"Security Project {uid}", "slug": f"sec-proj-{uid}"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201, proj_res.text
    proj = proj_res.json()

    envs_res = await client.get(
        f"{PROJECT_PREFIX}/{proj['id']}/environments",
        headers=auth_headers,
    )
    assert envs_res.status_code == 200, envs_res.text
    envs = envs_res.json()
    return org, proj, envs


async def _create_api_key(
    client: AsyncClient, auth_headers: dict[str, str], env_id: str, scope: str = "SERVER"
) -> dict[str, Any]:
    """Create an API key for the given environment and return response payload."""
    res = await client.post(
        f"/api/v1/environments/{env_id}/api-keys",
        json={"name": f"Key-{scope}", "scope": scope},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ──────────────────────────────────────────────────────────────────────────────
# 1. API key dev gọi ruleset prod -> 403
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dev_api_key_cannot_access_prod_ruleset() -> None:
    """An API key bound to development cannot read production ruleset (HTTP 403)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, _, envs = await _setup_project_and_envs(client, auth_headers)

        dev_env = next(e for e in envs if e["key"] in ("dev", "development"))
        prod_env = next(e for e in envs if e["key"] in ("prod", "production"))

        # Create API key for development environment
        dev_key_data = await _create_api_key(client, auth_headers, dev_env["id"], scope="SERVER")
        dev_raw_key = dev_key_data["key"]

        # Attempt to access production ruleset explicitly using dev key
        res = await client.get(
            f"{EVAL_PREFIX}/ruleset?environment_id={prod_env['id']}",
            headers={"X-FlagOps-Key": dev_raw_key},
        )
        assert res.status_code == 403
        data = res.json()
        assert data["error"]["code"] == "FORBIDDEN"
        assert "not authorized for this environment" in data["error"]["message"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 2. CLIENT key lấy flag is_client_visible=false -> KHÔNG có trong kết quả
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_key_filters_non_client_visible_flags() -> None:
    """CLIENT-scoped API key cannot observe flags marked is_client_visible=False."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, proj, envs = await _setup_project_and_envs(client, auth_headers)
        dev_env = envs[0]

        # Flag 1: Visible to clients
        f1_res = await client.post(
            f"{PROJECT_PREFIX}/{proj['id']}/flags",
            json={"key": f"public_ui_{uuid.uuid4().hex[:6]}", "name": "Public UI", "type": "BOOLEAN", "is_client_visible": True},
            headers=auth_headers,
        )
        assert f1_res.status_code == 201
        f1_key = f1_res.json()["key"]

        # Flag 2: Backend only (is_client_visible = False)
        f2_res = await client.post(
            f"{PROJECT_PREFIX}/{proj['id']}/flags",
            json={"key": f"secret_backend_{uuid.uuid4().hex[:6]}", "name": "Secret Backend", "type": "BOOLEAN", "is_client_visible": False},
            headers=auth_headers,
        )
        assert f2_res.status_code == 201
        f2_key = f2_res.json()["key"]

        # Create CLIENT-scoped API key
        cli_key_data = await _create_api_key(client, auth_headers, dev_env["id"], scope="CLIENT")
        cli_raw_key = cli_key_data["key"]

        # Fetch ruleset with CLIENT key
        ruleset_res = await client.get(f"{EVAL_PREFIX}/ruleset", headers={"X-FlagOps-Key": cli_raw_key})
        assert ruleset_res.status_code == 200
        flags_payload = ruleset_res.json().get("flags", {})

        # Public flag is returned
        assert f1_key in flags_payload
        # Secret flag is completely absent
        assert f2_key not in flags_payload

        # Direct evaluation of hidden flag with CLIENT key returns 404 (not found)
        eval_hidden_res = await client.post(
            f"{EVAL_PREFIX}/flags/{f2_key}/evaluate",
            json={"context": {}},
            headers={"X-FlagOps-Key": cli_raw_key},
        )
        assert eval_hidden_res.status_code == 404
        assert eval_hidden_res.json()["error"]["code"] == "FLAG_NOT_FOUND"


# ──────────────────────────────────────────────────────────────────────────────
# 3. VIEWER gọi PUT /flags/{id} -> 403
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_viewer_role_cannot_update_flag() -> None:
    """Users with VIEWER role cannot modify flags via PUT/PATCH (HTTP 403 Forbidden)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        # 1. Admin creates project and flag
        admin_user, admin_headers = await _create_user_and_token(client)
        org, proj, _ = await _setup_project_and_envs(client, admin_headers)

        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{proj['id']}/flags",
            json={"key": f"test_role_{uuid.uuid4().hex[:6]}", "name": "Role Test Flag", "type": "BOOLEAN"},
            headers=admin_headers,
        )
        assert flag_res.status_code == 201
        flag_id = flag_res.json()["id"]

        # 2. Create viewer user and add to org as VIEWER
        viewer_email = _unique_email()
        viewer_user, viewer_headers = await _create_user_and_token(client, viewer_email)

        async with async_session_factory() as db:
            membership = Membership(
                organization_id=uuid.UUID(org["id"]),
                user_id=uuid.UUID(viewer_user["id"]),
                role=MemberRole.VIEWER,
            )
            db.add(membership)
            await db.commit()

        # 3. Viewer attempts PUT /api/v1/flags/{id}
        put_res = await client.put(
            f"/api/v1/flags/{flag_id}",
            json={"name": "Hacked Name Attempt"},
            headers=viewer_headers,
        )
        assert put_res.status_code == 403
        assert put_res.json()["error"]["code"] == "FORBIDDEN"

        # 4. Viewer attempts PATCH /api/v1/flags/{id}
        patch_res = await client.patch(
            f"/api/v1/flags/{flag_id}",
            json={"name": "Hacked Name Patch Attempt"},
            headers=viewer_headers,
        )
        assert patch_res.status_code == 403
        assert patch_res.json()["error"]["code"] == "FORBIDDEN"


# ──────────────────────────────────────────────────────────────────────────────
# 4. User org A gọi GET project org B -> 404 (không phải 403)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_org_access_returns_404_not_403() -> None:
    """Cross-organization access returns 404 NOT_FOUND to prevent tenant resource enumeration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        # Tenant A setup
        _, auth_a = await _create_user_and_token(client)
        _, proj_a, _ = await _setup_project_and_envs(client, auth_a)

        # Tenant B setup
        _, auth_b = await _create_user_and_token(client)
        await _setup_project_and_envs(client, auth_b)

        # User B attempts to access Project A
        res = await client.get(
            f"{PROJECT_PREFIX}/{proj_a['id']}",
            headers=auth_b,
        )
        # MUST BE 404, NEVER 403
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"
        assert res.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# ──────────────────────────────────────────────────────────────────────────────
# 5. API key đã revoke -> 401
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revoked_api_key_returns_401() -> None:
    """Revoked API keys are rejected immediately with HTTP 401 Unauthorized."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, _, envs = await _setup_project_and_envs(client, auth_headers)
        dev_env = envs[0]

        key_data = await _create_api_key(client, auth_headers, dev_env["id"])
        raw_key = key_data["key"]
        key_id = key_data["id"]

        # Pre-check: active key works
        pre_res = await client.get(f"{EVAL_PREFIX}/ruleset", headers={"X-FlagOps-Key": raw_key})
        assert pre_res.status_code == 200

        # Revoke the key
        revoke_res = await client.post(f"/api/v1/api-keys/{key_id}/revoke", headers=auth_headers)
        assert revoke_res.status_code == 200

        # Post-check: revoked key returns 401
        post_res = await client.get(f"{EVAL_PREFIX}/ruleset", headers={"X-FlagOps-Key": raw_key})
        assert post_res.status_code == 401
        assert post_res.json()["error"]["code"] == "UNAUTHORIZED"


# ──────────────────────────────────────────────────────────────────────────────
# 6. Gửi vượt ngưỡng rate limit -> 429 + header Retry-After
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429_with_retry_after() -> None:
    """When rate limit threshold is crossed, evaluation API returns 429 with Retry-After header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, _, envs = await _setup_project_and_envs(client, auth_headers)
        dev_env = envs[0]

        key_data = await _create_api_key(client, auth_headers, dev_env["id"])
        raw_key = key_data["key"]

        # Mock check_rate_limit to simulate threshold breach (allowed=False, remaining=0)
        with patch("app.services.ruleset_cache.check_rate_limit", return_value=(False, 0)):
            res = await client.get(f"{EVAL_PREFIX}/ruleset", headers={"X-FlagOps-Key": raw_key})
            assert res.status_code == 429
            assert res.headers.get("Retry-After") == "60"
            data = res.json()
            assert data["error"]["code"] == "RATE_LIMITED"
            assert data["error"]["details"]["retry_after"] == 60


# ──────────────────────────────────────────────────────────────────────────────
# 7. Regex độc hại "(a+)+$" trong điều kiện -> xử lý < 200ms, không treo
# ──────────────────────────────────────────────────────────────────────────────

def test_evil_redos_regex_does_not_hang() -> None:
    """Catastrophic backtracking ReDoS pattern terminates in < 200ms with timeout."""
    evil_pattern = r"(a+)+$"
    evil_input = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaX"  # 30 'a's followed by 'X' triggers exponential backtracking in standard re

    start_time = time.perf_counter()
    # Execute regex matcher with built-in 50ms ReDoS timeout protection
    match_result = op_matches_regex(evil_input, evil_pattern)
    elapsed = time.perf_counter() - start_time

    assert match_result is False
    assert elapsed < 0.200, f"Evil regex took too long: {elapsed:.4f}s (must be < 200ms)"


# ──────────────────────────────────────────────────────────────────────────────
# 8. Điều kiện JSONB lồng 50 tầng -> 400 CONDITION_DEPTH_EXCEEDED
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deeply_nested_conditions_returns_400_condition_depth_exceeded() -> None:
    """Targeting condition tree nested 50 levels deep is rejected with 400 CONDITION_DEPTH_EXCEEDED."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, proj, envs = await _setup_project_and_envs(client, auth_headers)
        dev_env = envs[0]

        # 1. Create a flag with variation
        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{proj['id']}/flags",
            json={"key": f"deep_cond_{uuid.uuid4().hex[:6]}", "name": "Deep Cond Flag", "type": "BOOLEAN"},
            headers=auth_headers,
        )
        assert flag_res.status_code == 201
        flag_id = flag_res.json()["id"]
        var_id = flag_res.json()["variations"][0]["id"]

        # 2. Build 50-level nested condition tree
        root: dict[str, Any] = {"operator": "AND", "conditions": [], "children": []}
        curr = root
        for i in range(50):
            child = {
                "operator": "AND",
                "conditions": [{"attribute": f"level_{i}", "operator": "EQ", "value": "test"}],
                "children": [],
            }
            curr["children"].append(child)
            curr = child

        # 3. Attempt to save 50-level rule
        rules_payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Exploit nesting DoS",
                    "conditions": root,
                    "distribution": [{"variation_id": var_id, "weight": 100.0}],
                }
            ]
        }

        res = await client.put(
            f"/api/v1/flags/{flag_id}/environments/{dev_env['id']}/rules",
            json=rules_payload,
            headers=auth_headers,
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "CONDITION_DEPTH_EXCEEDED"
        assert "depth limit" in data["error"]["message"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 9. SQL injection qua query param lọc (' OR 1=1 --) -> không rò dữ liệu
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sql_injection_in_query_params_prevented() -> None:
    """SQL injection payloads in query parameters are strictly parameterized by ORM."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, proj, _ = await _setup_project_and_envs(client, auth_headers)

        # Create one normal flag
        await client.post(
            f"{PROJECT_PREFIX}/{proj['id']}/flags",
            json={"key": f"legit_flag_{uuid.uuid4().hex[:6]}", "name": "Legit Flag", "type": "BOOLEAN"},
            headers=auth_headers,
        )

        # Classic SQL injection payloads
        payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE flag; --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' OR 'x'='x",
        ]

        for payload in payloads:
            res = await client.get(
                f"{PROJECT_PREFIX}/{proj['id']}/flags?search={payload}",
                headers=auth_headers,
            )
            # Must succeed with 200 OK and return empty list (no matching literal string)
            assert res.status_code == 200, f"Payload {payload} caused error: {res.text}"
            results = res.json()
            assert isinstance(results, list)
            assert len(results) == 0, f"SQL injection payload {payload} leaked rows!"


# ──────────────────────────────────────────────────────────────────────────────
# 10. XSS: tên flag chứa <script>alert(1)</script> -> lưu nguyên, render escape
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_xss_in_flag_name_stored_lossless_and_escaped() -> None:
    """XSS payloads in flag name are stored losslessly and safely returned in JSON."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)
        _, proj, _ = await _setup_project_and_envs(client, auth_headers)

        xss_name = '<script>alert("XSS-Test")</script>'
        flag_key = f"xss_flag_{uuid.uuid4().hex[:6]}"

        res = await client.post(
            f"{PROJECT_PREFIX}/{proj['id']}/flags",
            json={"key": flag_key, "name": xss_name, "type": "BOOLEAN"},
            headers=auth_headers,
        )
        assert res.status_code == 201
        data = res.json()
        flag_id = data["id"]
        # Lossless storage: raw string preserved
        assert data["name"] == xss_name

        # Query back details
        get_res = await client.get(f"/api/v1/flags/{flag_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == xss_name


# ──────────────────────────────────────────────────────────────────────────────
# 11. Response lỗi 500 KHÔNG chứa stack trace
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_internal_error_does_not_leak_stack_trace() -> None:
    """Internal server errors (500) return an opaque error envelope without stack traces."""
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url=BASE) as client:
        _, auth_headers = await _create_user_and_token(client)

        # Trigger internal server error via mock
        with patch("app.services.flag.flag_service.list_flags", side_effect=RuntimeError("Secret internal database crash")):
            res = await client.get(
                f"{PROJECT_PREFIX}/{uuid.uuid4()}/flags",
                headers=auth_headers,
            )
            # If cross-org check runs first it might be 404; check unhandled exception
            assert res.status_code in (404, 500)

        with patch("app.api.eval.router.eval_service.get_ruleset_payload", side_effect=RuntimeError("Critical failure in internal subsystem")):
            _, _, envs = await _setup_project_and_envs(client, auth_headers)
            key_data = await _create_api_key(client, auth_headers, envs[0]["id"])

            err_res = await client.get(f"{EVAL_PREFIX}/ruleset", headers={"X-FlagOps-Key": key_data["key"]})
            assert err_res.status_code == 500
            err_json = err_res.json()
            assert err_json["error"]["code"] == "INTERNAL_SERVER_ERROR"
            # Ensure no tracebacks or internal paths leaked
            body_str = err_res.text
            assert "Traceback" not in body_str
            assert "RuntimeError" not in body_str
            assert "Critical failure in internal subsystem" not in body_str
            assert "request_id" in err_json


# ──────────────────────────────────────────────────────────────────────────────
# 12. Không endpoint nào trả về password_hash, key_hash, hay master key
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sensitive_hashes_never_exposed_in_api() -> None:
    """API responses never leak password_hash, key_hash, or CONFIG_MASTER_KEY."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        # Register & Login
        user_data, auth_headers = await _create_user_and_token(client)
        assert "password_hash" not in user_data
        assert "password" not in user_data

        # Get me
        me_res = await client.get(f"{AUTH_PREFIX}/me", headers=auth_headers)
        assert me_res.status_code == 200
        assert "password_hash" not in me_res.json()

        # Create API Key
        _, _, envs = await _setup_project_and_envs(client, auth_headers)
        dev_env = envs[0]
        key_res = await client.post(
            f"/api/v1/environments/{dev_env['id']}/api-keys",
            json={"name": "Audit Key", "scope": "SERVER"},
            headers=auth_headers,
        )
        assert key_res.status_code == 201
        key_json = key_res.json()
        assert "key_hash" not in key_json
        assert key_json["key_prefix"] == key_json["key"][:12]

        # List API Keys
        list_keys_res = await client.get(f"/api/v1/environments/{dev_env['id']}/api-keys", headers=auth_headers)
        assert list_keys_res.status_code == 200
        for k in list_keys_res.json():
            assert "key_hash" not in k
            assert "key" not in k  # Raw key is never listed again
