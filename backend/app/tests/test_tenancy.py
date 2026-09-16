"""Tests for Slice 3 — Tenancy & CRUD: Organization, Membership, Project, Environment, API Key."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import async_session_factory
from app.main import app
from app.services.tenancy import tenancy_service

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
ENV_PREFIX = "/api/v1/environments"
APIKEY_PREFIX = "/api/v1/api-keys"

STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"test-tenancy-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str = "org") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    """Helper to register and login a user, returning user info and auth headers."""
    email = _unique_email()
    reg_resp = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Test User"},
    )
    user_data = reg_resp.json()

    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    token_data = login_resp.json()
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    return user_data, headers


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c


# ─── 1. TẠO ORG → TỰ ĐỘNG CÓ PROJECT RỖNG ───


@pytest.mark.asyncio
async def test_create_org_has_empty_projects(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    slug = _unique_slug("org")

    # Tạo org
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org Empty Projects", "slug": slug},
        headers=headers,
    )
    assert org_resp.status_code == 201
    org = org_resp.json()
    assert org["slug"] == slug

    # Lấy danh sách project của org vừa tạo -> Phải là list rỗng
    proj_resp = await client.get(
        f"{ORG_PREFIX}/{org['id']}/projects",
        headers=headers,
    )
    assert proj_resp.status_code == 200
    projects = proj_resp.json()
    assert isinstance(projects, list)
    assert len(projects) == 0


# ─── 2. TẠO PROJECT → TỰ ĐỘNG SINH 3 ENVIRONMENT (dev, staging, prod) ───


@pytest.mark.asyncio
async def test_create_project_auto_generates_three_environments(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    org_slug = _unique_slug("org")
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org Proj Env", "slug": org_slug},
        headers=headers,
    )
    org = org_resp.json()

    # Tạo project
    proj_slug = _unique_slug("proj")
    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "My Project", "slug": proj_slug, "default_stale_days": 30},
        headers=headers,
    )
    assert proj_resp.status_code == 201
    proj = proj_resp.json()
    assert proj["slug"] == proj_slug
    assert proj["organization_id"] == org["id"]

    # Kiểm tra 3 environments tự động sinh
    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{proj['id']}/environments",
        headers=headers,
    )
    assert env_resp.status_code == 200
    envs = env_resp.json()
    assert len(envs) == 3

    keys = {e["key"]: e for e in envs}
    assert "development" in keys
    assert "staging" in keys
    assert "production" in keys

    # Quy tắc: production có is_production = True, 2 env còn lại False
    assert keys["development"]["is_production"] is False
    assert keys["staging"]["is_production"] is False
    assert keys["production"]["is_production"] is True

    # ruleset_version ban đầu mặc định bằng 0
    assert all(e["ruleset_version"] == 0 for e in envs)


# ─── 3. TẠO API KEY → RESPONSE CÓ RAW KEY ───


@pytest.mark.asyncio
async def test_create_apikey_returns_raw_key(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    org_slug = _unique_slug("org")
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org Key", "slug": org_slug},
        headers=headers,
    )
    org_id = org_resp.json()["id"]

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects",
        json={"name": "Key Project", "slug": _unique_slug("proj")},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{proj_id}/environments",
        headers=headers,
    )
    envs = env_resp.json()
    dev_env = next(e for e in envs if e["key"] == "development")

    # Tạo server key
    key_resp = await client.post(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        json={"name": "Server SDK Key", "scope": "SERVER"},
        headers=headers,
    )
    assert key_resp.status_code == 201
    data = key_resp.json()

    # Phải có raw key bắt đầu bằng fo_srv_
    assert "key" in data
    assert data["key"].startswith("fo_srv_")
    assert len(data["key_prefix"]) == 12
    assert data["key"].startswith(data["key_prefix"])
    assert data["scope"] == "SERVER"

    # Tạo client key
    cli_resp = await client.post(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        json={"name": "Client SDK Key", "scope": "CLIENT"},
        headers=headers,
    )
    assert cli_resp.status_code == 201
    cli_data = cli_resp.json()
    assert cli_data["key"].startswith("fo_cli_")
    assert len(cli_data["key_prefix"]) == 12
    assert cli_data["key"].startswith(cli_data["key_prefix"])
    assert cli_data["scope"] == "CLIENT"


# ─── 4. GET API KEY LIST → KHÔNG CÓ RAW KEY, CHỈ CÓ PREFIX ───


@pytest.mark.asyncio
async def test_get_apikey_list_does_not_contain_raw_key(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org List Keys", "slug": _unique_slug("org")},
        headers=headers,
    )
    org_id = org_resp.json()["id"]

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects",
        json={"name": "List Key Project", "slug": _unique_slug("proj")},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{proj_id}/environments",
        headers=headers,
    )
    dev_env = env_resp.json()[0]

    # Tạo 2 key
    await client.post(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        json={"name": "Key 1", "scope": "SERVER"},
        headers=headers,
    )
    await client.post(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        json={"name": "Key 2", "scope": "CLIENT"},
        headers=headers,
    )

    # GET danh sách key
    list_resp = await client.get(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        headers=headers,
    )
    assert list_resp.status_code == 200
    keys = list_resp.json()
    assert len(keys) >= 2

    for k in keys:
        # CHỈ có key_prefix, TUYỆT ĐỐI KHÔNG có raw key hoặc key_hash
        assert "key_prefix" in k
        assert len(k["key_prefix"]) == 12
        assert "key" not in k
        assert "key_hash" not in k


# ─── 5. REVOKE KEY → GỌI LẠI BẰNG KEY ĐÓ PHẢI 401 ───


@pytest.mark.asyncio
async def test_revoke_apikey_returns_401_on_verification(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org Revoke Key", "slug": _unique_slug("org")},
        headers=headers,
    )
    org_id = org_resp.json()["id"]

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects",
        json={"name": "Revoke Project", "slug": _unique_slug("proj")},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{proj_id}/environments",
        headers=headers,
    )
    dev_env = env_resp.json()[0]

    create_resp = await client.post(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        json={"name": "Temp Key", "scope": "SERVER"},
        headers=headers,
    )
    key_data = create_resp.json()
    raw_key = key_data["key"]
    key_id = key_data["id"]

    # Xác thực key trước khi revoke -> Hợp lệ
    async with async_session_factory() as session:
        verified_key = await tenancy_service.verify_api_key(session, raw_key)
        assert verified_key.id == uuid.UUID(key_id)

    # Thu hồi key (revoke)
    revoke_resp = await client.post(
        f"{APIKEY_PREFIX}/{key_id}/revoke",
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    revoked_data = revoke_resp.json()
    assert revoked_data["revoked_at"] is not None

    # Xác thực lại bằng key vừa revoke -> Phải ném 401 UNAUTHORIZED
    async with async_session_factory() as session:
        with pytest.raises(Exception) as exc_info:
            await tenancy_service.verify_api_key(session, raw_key)
        assert getattr(exc_info.value, "status_code", None) == 401
        assert getattr(exc_info.value, "code", "") == "UNAUTHORIZED"


# ─── 6. CÁCH LY DỮ LIỆU: USER ORG A GET PROJECT ORG B → 404 (KHÔNG 403) ───


@pytest.mark.asyncio
async def test_user_org_a_get_project_org_b_returns_404(client: AsyncClient) -> None:
    # User A tạo Org A và Project A
    _, headers_a = await create_and_login_user(client)
    org_a_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org A", "slug": _unique_slug("org-a")},
        headers=headers_a,
    )
    org_a_id = org_a_resp.json()["id"]

    proj_a_resp = await client.post(
        f"{ORG_PREFIX}/{org_a_id}/projects",
        json={"name": "Project A", "slug": _unique_slug("proj-a")},
        headers=headers_a,
    )
    proj_a = proj_a_resp.json()

    # User B tạo Org B và Project B
    _, headers_b = await create_and_login_user(client)
    org_b_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org B", "slug": _unique_slug("org-b")},
        headers=headers_b,
    )
    org_b_id = org_b_resp.json()["id"]

    proj_b_resp = await client.post(
        f"{ORG_PREFIX}/{org_b_id}/projects",
        json={"name": "Project B", "slug": _unique_slug("proj-b")},
        headers=headers_b,
    )
    proj_b = proj_b_resp.json()

    # User A cố truy cập Project B của Org B -> PHẢI TRẢ 404 (KHÔNG PHẢI 403)
    resp_a_on_b = await client.get(
        f"{PROJECT_PREFIX}/{proj_b['id']}",
        headers=headers_a,
    )
    assert resp_a_on_b.status_code == 404
    assert resp_a_on_b.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    # User B cố truy cập Project A của Org A -> PHẢI TRẢ 404 (KHÔNG PHẢI 403)
    resp_b_on_a = await client.get(
        f"{PROJECT_PREFIX}/{proj_a['id']}",
        headers=headers_b,
    )
    assert resp_b_on_a.status_code == 404
    assert resp_b_on_a.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    # User A cố truy cập Org B trực tiếp -> 404
    resp_a_on_org_b = await client.get(
        f"{ORG_PREFIX}/{org_b_id}",
        headers=headers_a,
    )
    assert resp_a_on_org_b.status_code == 404
    assert resp_a_on_org_b.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


# ─── 7. VIEWER TẠO API KEY → 403 FORBIDDEN ───


@pytest.mark.asyncio
async def test_viewer_create_apikey_returns_403(client: AsyncClient) -> None:
    # Owner user tạo Org và Project
    _, owner_headers = await create_and_login_user(client)
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Org RBAC Test", "slug": _unique_slug("org-rbac")},
        headers=owner_headers,
    )
    org_id = org_resp.json()["id"]

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects",
        json={"name": "RBAC Project", "slug": _unique_slug("proj-rbac")},
        headers=owner_headers,
    )
    proj_id = proj_resp.json()["id"]

    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{proj_id}/environments",
        headers=owner_headers,
    )
    dev_env = env_resp.json()[0]

    # Tạo Viewer user
    viewer_user, viewer_headers = await create_and_login_user(client)

    # Owner thêm Viewer user vào Org với role VIEWER
    add_member_resp = await client.post(
        f"{ORG_PREFIX}/{org_id}/members",
        json={"user_id": viewer_user["id"], "role": "VIEWER"},
        headers=owner_headers,
    )
    assert add_member_resp.status_code == 201

    # Viewer xem project và environment -> 200 OK (có quyền xem)
    view_proj = await client.get(f"{PROJECT_PREFIX}/{proj_id}", headers=viewer_headers)
    assert view_proj.status_code == 200

    view_envs = await client.get(f"{PROJECT_PREFIX}/{proj_id}/environments", headers=viewer_headers)
    assert view_envs.status_code == 200

    # Viewer cố tạo API Key -> PHẢI TRẢ 403 FORBIDDEN
    create_key_resp = await client.post(
        f"{ENV_PREFIX}/{dev_env['id']}/api-keys",
        json={"name": "Unauthorized Key", "scope": "SERVER"},
        headers=viewer_headers,
    )
    assert create_key_resp.status_code == 403
    assert create_key_resp.json()["error"]["code"] == "FORBIDDEN"


# ─── 8. CRUD ENVIRONMENT VÀ ERROR CASES ───


@pytest.mark.asyncio
async def test_environment_crud_and_cross_org_isolation(client: AsyncClient) -> None:
    _, headers_a = await create_and_login_user(client)
    org_a = (
        await client.post(
            ORG_PREFIX, json={"name": "Env Org A", "slug": _unique_slug("org")}, headers=headers_a
        )
    ).json()
    proj_a = (
        await client.post(
            f"{ORG_PREFIX}/{org_a['id']}/projects",
            json={"name": "P A", "slug": _unique_slug("p")},
            headers=headers_a,
        )
    ).json()

    # Thêm môi trường mới vào Project A
    new_env_resp = await client.post(
        f"{PROJECT_PREFIX}/{proj_a['id']}/environments",
        json={"name": "QA Testing", "key": "qa-test", "is_production": False},
        headers=headers_a,
    )
    assert new_env_resp.status_code == 201
    new_env = new_env_resp.json()
    assert new_env["key"] == "qa-test"

    # User B cố truy cập Environment của User A -> 404
    _, headers_b = await create_and_login_user(client)
    env_cross_resp = await client.get(
        f"{ENV_PREFIX}/{new_env['id']}",
        headers=headers_b,
    )
    assert env_cross_resp.status_code == 404
    assert env_cross_resp.json()["error"]["code"] == "ENVIRONMENT_NOT_FOUND"


# ─── 9. CONFLICT VÀ IMMUTABILITY ───


@pytest.mark.asyncio
async def test_duplicate_org_and_project_slug_conflict_409(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    slug = _unique_slug("org-conflict")

    # Tạo org lần 1
    resp1 = await client.post(ORG_PREFIX, json={"name": "Org 1", "slug": slug}, headers=headers)
    assert resp1.status_code == 201
    org_id = resp1.json()["id"]

    # Tạo org lần 2 trùng slug -> 409
    resp2 = await client.post(ORG_PREFIX, json={"name": "Org 2", "slug": slug}, headers=headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "CONFLICT"

    # Tạo project lần 1
    proj_slug = "unique-proj-slug"
    p_resp1 = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects", json={"name": "P1", "slug": proj_slug}, headers=headers
    )
    assert p_resp1.status_code == 201

    # Tạo project lần 2 cùng org trùng slug -> 409
    p_resp2 = await client.post(
        f"{ORG_PREFIX}/{org_id}/projects", json={"name": "P2", "slug": proj_slug}, headers=headers
    )
    assert p_resp2.status_code == 409
    assert p_resp2.json()["error"]["code"] == "CONFLICT"
