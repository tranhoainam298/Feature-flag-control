"""Tests for Slice 4 — Flag Management.

Covers Flag, Variation, FlagEnvironmentSetting, Ruleset Version, and Audit Log.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.main import app
from app.models.audit import AuditLog
from app.models.project import Environment

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
FLAG_PREFIX = "/api/v1/flags"

STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"test-flag-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str = "flag") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
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


async def setup_org_and_project(
    client: AsyncClient, headers: dict
) -> tuple[dict, dict, list[dict]]:
    """Helper to create Org, Project, and return (org, project, environments)."""
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Flag Org", "slug": _unique_slug("org")},
        headers=headers,
    )
    org = org_resp.json()

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "Flag Project", "slug": _unique_slug("proj")},
        headers=headers,
    )
    project = proj_resp.json()

    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=headers,
    )
    envs = env_resp.json()
    return org, project, envs


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c


# ─── 1. TẠO FLAG BOOLEAN TỰ SINH VARIATION (on=true, off=false) ───


@pytest.mark.asyncio
async def test_create_flag_boolean_auto_generates_variations(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    flag_key = "new-checkout-flow"
    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": flag_key,
            "name": "New Checkout Flow",
            "type": "BOOLEAN",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    flag = resp.json()
    assert flag["key"] == flag_key
    assert flag["type"] == "BOOLEAN"

    # Tự động sinh 2 variation: on=true, off=false
    assert len(flag["variations"]) == 2
    var_map = {v["key"]: v["value"] for v in flag["variations"]}
    assert var_map["on"] is True
    assert var_map["off"] is False


# ─── 2. TỰ SINH FLAG_ENVIRONMENT_SETTING CHO MỌI ENV, ENABLED=FALSE ───


@pytest.mark.asyncio
async def test_create_flag_boolean_auto_generates_env_settings(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, envs = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "feature-chat", "name": "Feature Chat", "type": "BOOLEAN"},
        headers=headers,
    )
    flag = resp.json()

    # Kiểm tra cài đặt môi trường cho từng env
    for env in envs:
        setting_resp = await client.get(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{env['id']}",
            headers=headers,
        )
        assert setting_resp.status_code == 200
        setting = setting_resp.json()
        assert setting["enabled"] is False
        assert setting["bucketing_key"] == "userId"
        assert setting["default_variation_id"] is not None
        assert setting["off_variation_id"] is not None


# ─── 3. TẠO FLAG STRING THIẾU VARIATION → 422 ───


@pytest.mark.asyncio
async def test_create_flag_string_missing_variations_422(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    # Không gửi variations
    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "theme-color", "name": "Theme Color", "type": "STRING"},
        headers=headers,
    )
    assert resp.status_code == 422


# ─── 4. TẠO FLAG STRING CHỈ CÓ 1 VARIATION → 422 (PHẢI >= 2) ───


@pytest.mark.asyncio
async def test_create_flag_string_single_variation_422(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    # Chỉ gửi 1 variation
    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "banner-text",
            "name": "Banner Text",
            "type": "STRING",
            "variations": [{"key": "v1", "value": "Welcome"}],
        },
        headers=headers,
    )
    assert resp.status_code == 422


# ─── 5. TẠO FLAG STRING HỢP LỆ VỚI >= 2 VARIATION ───


@pytest.mark.asyncio
async def test_create_flag_string_with_valid_variations(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "app-theme",
            "name": "App Theme",
            "type": "STRING",
            "variations": [
                {"key": "light", "value": "light-mode"},
                {"key": "dark", "value": "dark-mode"},
                {"key": "sepia", "value": "sepia-mode"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    flag = resp.json()
    assert len(flag["variations"]) == 3


# ─── 6. TẠO FLAG NUMBER VỚI VARIATION HỢP LỆ ───


@pytest.mark.asyncio
async def test_create_flag_number_with_valid_variations(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "max-items-limit",
            "name": "Max Items Limit",
            "type": "NUMBER",
            "variations": [
                {"key": "tier1", "value": 10},
                {"key": "tier2", "value": 50.5},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    flag = resp.json()
    assert len(flag["variations"]) == 2


# ─── 7. TẠO FLAG JSON VỚI VARIATION HỢP LỆ ───


@pytest.mark.asyncio
async def test_create_flag_json_with_valid_variations(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "config-payload",
            "name": "Config Payload",
            "type": "JSON",
            "variations": [
                {"key": "conf_a", "value": {"retries": 3, "timeout": 5000}},
                {"key": "conf_b", "value": {"retries": 5, "timeout": 10000}},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    flag = resp.json()
    assert len(flag["variations"]) == 2


# ─── 8. TYPE_MISMATCH: FLAG BOOLEAN NHƯNG VALUE LÀ STRING → 422 ───


@pytest.mark.asyncio
async def test_create_flag_type_mismatch_boolean_422(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "bad-bool",
            "name": "Bad Bool",
            "type": "BOOLEAN",
            "variations": [
                {"key": "on", "value": "true"},  # Chuỗi string thay vì boolean
                {"key": "off", "value": False},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TYPE_MISMATCH"


# ─── 9. TYPE_MISMATCH: FLAG STRING NHƯNG VALUE LÀ INT → 422 ───


@pytest.mark.asyncio
async def test_create_flag_type_mismatch_string_422(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "bad-str",
            "name": "Bad String",
            "type": "STRING",
            "variations": [
                {"key": "v1", "value": "hello"},
                {"key": "v2", "value": 12345},  # Int thay vì string
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TYPE_MISMATCH"


# ─── 10. TYPE_MISMATCH: FLAG NUMBER NHƯNG VALUE LÀ BOOLEAN HOẶC STRING → 422 ───


@pytest.mark.asyncio
async def test_create_flag_type_mismatch_number_422(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "bad-num",
            "name": "Bad Num",
            "type": "NUMBER",
            "variations": [
                {"key": "v1", "value": 10},
                {"key": "v2", "value": "not-a-number"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TYPE_MISMATCH"


# ─── 11. TYPE_MISMATCH: FLAG JSON NHƯNG VALUE LÀ STRING HOẶC NUMBER → 422 ───


@pytest.mark.asyncio
async def test_create_flag_type_mismatch_json_422(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "bad-json",
            "name": "Bad JSON",
            "type": "JSON",
            "variations": [
                {"key": "v1", "value": {"valid": "dict"}},
                {"key": "v2", "value": "just-a-string"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TYPE_MISMATCH"


# ─── 12. TRÙNG LẶP FLAG KEY TRONG CÙNG PROJECT → 409 CONFLICT ───


@pytest.mark.asyncio
async def test_create_flag_duplicate_key_conflict_409(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    resp1 = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "dup-flag", "name": "F1", "type": "BOOLEAN"},
        headers=headers,
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "dup-flag", "name": "F2", "type": "BOOLEAN"},
        headers=headers,
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "CONFLICT"


# ─── 13. SỬA KEY → 400 VỚI CODE FLAG_KEY_IMMUTABLE ───


@pytest.mark.asyncio
async def test_patch_flag_key_immutable_400(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "original-key", "name": "Flag Orig", "type": "BOOLEAN"},
        headers=headers,
    )
    flag_id = flag_resp.json()["id"]

    # Cố tình gửi "key" trong body PATCH
    patch_resp = await client.patch(
        f"{FLAG_PREFIX}/{flag_id}",
        json={"key": "altered-key", "name": "New Name"},
        headers=headers,
    )
    assert patch_resp.status_code == 400
    assert patch_resp.json()["error"]["code"] == "FLAG_KEY_IMMUTABLE"


# ─── 14. SỬA METADATA FLAG HỢP LỆ ───


@pytest.mark.asyncio
async def test_patch_flag_metadata_success(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "patchable-flag", "name": "Before Name", "type": "BOOLEAN"},
        headers=headers,
    )
    flag_id = flag_resp.json()["id"]

    patch_resp = await client.patch(
        f"{FLAG_PREFIX}/{flag_id}",
        json={"name": "After Name", "description": "Updated desc", "tags": ["prod", "v2"]},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["name"] == "After Name"
    assert updated["description"] == "Updated desc"
    assert "prod" in updated["tags"]


# ─── 15. ARCHIVE RỒI RESTORE FLAG ───


@pytest.mark.asyncio
async def test_archive_and_restore_flag(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "archivable-flag", "name": "To Archive", "type": "BOOLEAN"},
        headers=headers,
    )
    flag_id = flag_resp.json()["id"]

    # 1. Archive
    arch_resp = await client.post(f"{FLAG_PREFIX}/{flag_id}/archive", headers=headers)
    assert arch_resp.status_code == 200
    assert arch_resp.json()["archived_at"] is not None

    # Lấy danh sách active flags -> không còn xuất hiện
    active_list = (
        await client.get(f"{PROJECT_PREFIX}/{project['id']}/flags", headers=headers)
    ).json()
    assert not any(f["id"] == flag_id for f in active_list)

    # Lấy danh sách archived flags -> có xuất hiện
    arch_list = (
        await client.get(f"{PROJECT_PREFIX}/{project['id']}/flags?archived=true", headers=headers)
    ).json()
    assert any(f["id"] == flag_id for f in arch_list)

    # 2. Restore
    rest_resp = await client.post(f"{FLAG_PREFIX}/{flag_id}/restore", headers=headers)
    assert rest_resp.status_code == 200
    assert rest_resp.json()["archived_at"] is None

    # Lấy danh sách active flags -> xuất hiện trở lại
    restored_list = (
        await client.get(f"{PROJECT_PREFIX}/{project['id']}/flags", headers=headers)
    ).json()
    assert any(f["id"] == flag_id for f in restored_list)


# ─── 16. BẬT FLAG Ở DEV KHÔNG ẢNH HƯỞNG PROD ───


@pytest.mark.asyncio
async def test_toggle_flag_in_dev_does_not_affect_prod(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, envs = await setup_org_and_project(client, headers)

    dev_env = next(e for e in envs if e["key"] == "development")
    prod_env = next(e for e in envs if e["key"] == "production")

    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "isolated-toggle", "name": "Isolated Toggle", "type": "BOOLEAN"},
        headers=headers,
    )
    flag_id = flag_resp.json()["id"]

    # Bật flag ở Development
    put_dev = await client.put(
        f"{FLAG_PREFIX}/{flag_id}/environments/{dev_env['id']}",
        json={"enabled": True},
        headers=headers,
    )
    assert put_dev.status_code == 200
    assert put_dev.json()["enabled"] is True

    # Kiểm tra Production -> Vẫn là False
    get_prod = await client.get(
        f"{FLAG_PREFIX}/{flag_id}/environments/{prod_env['id']}",
        headers=headers,
    )
    assert get_prod.status_code == 200
    assert get_prod.json()["enabled"] is False


# ─── 17. RULESET_VERSION TĂNG ĐÚNG SAU MỖI LẦN GHI ───


@pytest.mark.asyncio
async def test_ruleset_version_increments_on_every_write(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, envs = await setup_org_and_project(client, headers)
    dev_env = next(e for e in envs if e["key"] == "development")

    async with async_session_factory() as session:
        initial_env = await session.scalar(
            select(Environment).where(Environment.id == uuid.UUID(dev_env["id"]))
        )
        assert initial_env is not None
        v0 = initial_env.ruleset_version

    # Tạo flag mới -> ruleset_version của dev tăng
    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "version-flag", "name": "Version Flag", "type": "BOOLEAN"},
        headers=headers,
    )
    flag_id = flag_resp.json()["id"]

    async with async_session_factory() as session:
        env_after_create = await session.scalar(
            select(Environment).where(Environment.id == uuid.UUID(dev_env["id"]))
        )
        assert env_after_create is not None
        assert env_after_create.ruleset_version == v0 + 1

    # Bật flag trên dev -> ruleset_version của dev tiếp tục tăng
    await client.put(
        f"{FLAG_PREFIX}/{flag_id}/environments/{dev_env['id']}",
        json={"enabled": True},
        headers=headers,
    )

    async with async_session_factory() as session:
        env_after_toggle = await session.scalar(
            select(Environment).where(Environment.id == uuid.UUID(dev_env["id"]))
        )
        assert env_after_toggle is not None
        assert env_after_toggle.ruleset_version == v0 + 2


# ─── 18. AUDIT_LOG ĐƯỢC GHI VỚI BEFORE/AFTER ĐÚNG ───


@pytest.mark.asyncio
async def test_audit_log_recorded_with_before_and_after(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, envs = await setup_org_and_project(client, headers)
    dev_env = envs[0]

    # 1. Tạo flag -> kiểm tra audit_log
    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "audit-test-flag", "name": "Audit Name", "type": "BOOLEAN"},
        headers=headers,
    )
    flag_id = flag_resp.json()["id"]

    async with async_session_factory() as session:
        log_create = await session.scalar(
            select(AuditLog)
            .where(AuditLog.entity_id == flag_id, AuditLog.action == "flag.create")
            .order_by(AuditLog.created_at.desc())
        )
        assert log_create is not None
        assert log_create.after is not None
        assert log_create.after["key"] == "audit-test-flag"

    # 2. Cập nhật flag setting -> kiểm tra audit_log
    await client.put(
        f"{FLAG_PREFIX}/{flag_id}/environments/{dev_env['id']}",
        json={"enabled": True},
        headers=headers,
    )

    async with async_session_factory() as session:
        log_setting = await session.scalar(
            select(AuditLog)
            .where(
                AuditLog.environment_id == uuid.UUID(dev_env["id"]),
                AuditLog.action == "flag_setting.update",
            )
            .order_by(AuditLog.created_at.desc())
        )
        assert log_setting is not None
        assert log_setting.before is not None
        assert log_setting.after is not None
        assert log_setting.before["enabled"] is False
        assert log_setting.after["enabled"] is True


# ─── 19. LỌC FLAG THEO TAG, TYPE, SEARCH ───


@pytest.mark.asyncio
async def test_list_flags_filter_by_tag_and_type_and_search(client: AsyncClient) -> None:
    _, headers = await create_and_login_user(client)
    _, project, _ = await setup_org_and_project(client, headers)

    # Tạo 3 flags khác nhau
    await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "search-alpha",
            "name": "Search Alpha",
            "type": "BOOLEAN",
            "tags": ["tag1", "common"],
        },
        headers=headers,
    )
    await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": "search-beta",
            "name": "Search Beta",
            "type": "STRING",
            "tags": ["tag2", "common"],
            "variations": [{"key": "v1", "value": "A"}, {"key": "v2", "value": "B"}],
        },
        headers=headers,
    )
    await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "gamma-flag", "name": "Gamma Unique", "type": "BOOLEAN", "tags": ["tag1"]},
        headers=headers,
    )

    # Lọc theo tag1 -> Có alpha và gamma
    res_tag = (
        await client.get(f"{PROJECT_PREFIX}/{project['id']}/flags?tag=tag1", headers=headers)
    ).json()
    assert len(res_tag) == 2

    # Lọc theo type STRING -> Chỉ có beta
    res_type = (
        await client.get(f"{PROJECT_PREFIX}/{project['id']}/flags?type=STRING", headers=headers)
    ).json()
    assert len(res_type) == 1
    assert res_type[0]["key"] == "search-beta"

    # Lọc theo search 'alpha' -> Chỉ có alpha
    res_search = (
        await client.get(f"{PROJECT_PREFIX}/{project['id']}/flags?search=alpha", headers=headers)
    ).json()
    assert len(res_search) == 1
    assert res_search[0]["key"] == "search-alpha"


# ─── 20. CÁCH LY CHÉO TENANT: USER ORG A GET FLAG ORG B → 404 (KHÔNG 403) ───


@pytest.mark.asyncio
async def test_cross_org_flag_access_returns_404(client: AsyncClient) -> None:
    _, headers_a = await create_and_login_user(client)
    _, project_a, _ = await setup_org_and_project(client, headers_a)

    flag_a_resp = await client.post(
        f"{PROJECT_PREFIX}/{project_a['id']}/flags",
        json={"key": "secret-flag-a", "name": "Secret A", "type": "BOOLEAN"},
        headers=headers_a,
    )
    flag_a_id = flag_a_resp.json()["id"]

    # User B từ Org B
    _, headers_b = await create_and_login_user(client)

    # User B cố truy cập Flag của Org A -> 404
    get_cross = await client.get(f"{FLAG_PREFIX}/{flag_a_id}", headers=headers_b)
    assert get_cross.status_code == 404
    assert get_cross.json()["error"]["code"] == "FLAG_NOT_FOUND"

    # User B cố sửa Flag của Org A -> 404
    patch_cross = await client.patch(
        f"{FLAG_PREFIX}/{flag_a_id}",
        json={"name": "Hacked"},
        headers=headers_b,
    )
    assert patch_cross.status_code == 404
    assert patch_cross.json()["error"]["code"] == "FLAG_NOT_FOUND"


# ─── 21. ROLE VIEWER KHÔNG ĐƯỢC TẠO/SỬA FLAG HOẶC SETTING → 403 FORBIDDEN ───


@pytest.mark.asyncio
async def test_viewer_role_cannot_modify_flag_or_settings_403(client: AsyncClient) -> None:
    _, owner_headers = await create_and_login_user(client)
    org, project, envs = await setup_org_and_project(client, owner_headers)

    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "viewer-test-flag", "name": "Viewer Test Flag", "type": "BOOLEAN"},
        headers=owner_headers,
    )
    flag_id = flag_resp.json()["id"]

    # Tạo Viewer user trong cùng Org
    viewer_user, viewer_headers = await create_and_login_user(client)
    await client.post(
        f"{ORG_PREFIX}/{org['id']}/members",
        json={"user_id": viewer_user["id"], "role": "VIEWER"},
        headers=owner_headers,
    )

    # Viewer xem Flag -> 200 OK
    view_resp = await client.get(f"{FLAG_PREFIX}/{flag_id}", headers=viewer_headers)
    assert view_resp.status_code == 200

    # Viewer cố tạo Flag mới -> 403 FORBIDDEN
    create_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={"key": "unauth-flag", "name": "Unauth", "type": "BOOLEAN"},
        headers=viewer_headers,
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["error"]["code"] == "FORBIDDEN"

    # Viewer cố bật/tắt Setting -> 403 FORBIDDEN
    put_resp = await client.put(
        f"{FLAG_PREFIX}/{flag_id}/environments/{envs[0]['id']}",
        json={"enabled": True},
        headers=viewer_headers,
    )
    assert put_resp.status_code == 403
    assert put_resp.json()["error"]["code"] == "FORBIDDEN"
