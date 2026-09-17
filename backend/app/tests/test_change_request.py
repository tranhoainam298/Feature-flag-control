"""Integration tests for Change Request (Slice 16).

Verifies:
1. Sửa flag ở production -> không đổi ngay, tạo CR PENDING.
2. Sửa flag ở dev -> đổi ngay, không tạo CR.
3. Người tạo tự duyệt -> 403 SELF_APPROVAL_FORBIDDEN.
4. DEVELOPER duyệt -> 403 FORBIDDEN.
5. Người khác (ADMIN/OWNER) duyệt -> APPLIED, thay đổi có hiệu lực, ruleset_version tăng.
6. Reject -> thay đổi KHÔNG được áp dụng, status REJECTED.
7. Impact simulation trả đúng số lượng context và transition matrix trên dữ liệu dựng sẵn.
8. scheduled_at trong quá khứ -> áp dụng ở lần quét kế tiếp với actor = None.
9. Áp dụng lỗi giữa chừng -> rollback, CR giữ trạng thái APPROVED, ghi log lỗi.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.main import app
from app.models.audit import AuditLog
from app.models.change_request import ChangeRequest
from app.models.enums import ChangeRequestStatus
from app.models.evaluation import EvaluationEvent
from app.services.change_request import change_request_service

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
FLAG_PREFIX = "/api/v1/flags"
CR_PREFIX = "/api/v1/change-requests"

STRONG_PW = "Str0ngP@ss123"


def _unique_email() -> str:
    return f"test-cr-{uuid.uuid4().hex[:10]}@example.com"


async def create_user_and_headers(
    client: AsyncClient, name: str = "User"
) -> tuple[dict[str, Any], dict[str, str]]:
    email = _unique_email()
    await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PW, "full_name": name},
    )
    res = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PW},
    )
    token = res.json()["access_token"]
    user_res = await client.get(f"{AUTH_PREFIX}/me", headers={"Authorization": f"Bearer {token}"})
    return user_res.json(), {"Authorization": f"Bearer {token}"}


async def setup_test_hierarchy(
    client: AsyncClient, owner_headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    org_res = await client.post(
        ORG_PREFIX,
        json={"name": "CR Org", "slug": f"cr-org-{uuid.uuid4().hex[:8]}"},
        headers=owner_headers,
    )
    org = org_res.json()

    proj_res = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "CR Project", "slug": f"cr-proj-{uuid.uuid4().hex[:8]}"},
        headers=owner_headers,
    )
    project = proj_res.json()

    envs_res = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=owner_headers,
    )
    envs = envs_res.json()
    return org, project, envs


@pytest.mark.asyncio
async def test_modify_flag_in_production_creates_pending_cr():
    """1. Sửa flag ở production -> không đổi ngay, tạo CR PENDING."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        _, owner_headers = await create_user_and_headers(client, "Owner")
        _, project, envs = await setup_test_hierarchy(client, owner_headers)

        prod_env = next(e for e in envs if e["is_production"] is True)

        # Create flag
        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": f"prod_flag_{uuid.uuid4().hex[:6]}",
                "name": "Prod Flag",
                "type": "BOOLEAN",
            },
            headers=owner_headers,
        )
        flag = flag_res.json()

        # Update flag setting in production environment
        put_res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            json={"enabled": True},
            headers=owner_headers,
        )
        assert put_res.status_code == 202
        body = put_res.json()
        assert body["change_request_status"] == "PENDING"
        cr_id = body["change_request_id"]

        # Verify live flag setting did NOT change
        get_setting_res = await client.get(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        assert get_setting_res.json()["enabled"] is False

        # Verify Change Request is listed in PENDING
        list_cr_res = await client.get(
            f"/api/v1/environments/{prod_env['id']}/change-requests?status=PENDING",
            headers=owner_headers,
        )
        assert list_cr_res.status_code == 200
        cr_list = list_cr_res.json()
        assert any(c["id"] == cr_id for c in cr_list)


@pytest.mark.asyncio
async def test_modify_flag_in_dev_applies_immediately():
    """2. Sửa flag ở dev -> đổi ngay, không tạo CR."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        _, owner_headers = await create_user_and_headers(client, "Owner")
        _, project, envs = await setup_test_hierarchy(client, owner_headers)

        dev_env = next(e for e in envs if e["is_production"] is False)

        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={"key": f"dev_flag_{uuid.uuid4().hex[:6]}", "name": "Dev Flag", "type": "BOOLEAN"},
            headers=owner_headers,
        )
        flag = flag_res.json()

        # Update flag setting in development
        put_res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}",
            json={"enabled": True},
            headers=owner_headers,
        )
        assert put_res.status_code == 200
        assert put_res.json()["enabled"] is True

        # Verify no change requests were created in dev
        list_cr_res = await client.get(
            f"/api/v1/environments/{dev_env['id']}/change-requests",
            headers=owner_headers,
        )
        assert list_cr_res.status_code == 200
        assert len(list_cr_res.json()) == 0


@pytest.mark.asyncio
async def test_self_approval_forbidden_403():
    """3. Nguyên tắc bốn mắt: người tạo tự duyệt -> 403 SELF_APPROVAL_FORBIDDEN."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        _, owner_headers = await create_user_and_headers(client, "Owner")
        _, project, envs = await setup_test_hierarchy(client, owner_headers)

        prod_env = next(e for e in envs if e["is_production"] is True)

        # Owner creates change request
        cr_res = await client.post(
            f"/api/v1/environments/{prod_env['id']}/change-requests",
            json={
                "title": "Self approval test",
                "payload": {"type": "flag_setting", "setting": {"enabled": True}},
            },
            headers=owner_headers,
        )
        cr = cr_res.json()

        # Owner tries to approve their own CR
        approve_res = await client.post(
            f"{CR_PREFIX}/{cr['id']}/approve",
            headers=owner_headers,
        )
        assert approve_res.status_code == 403
        err = approve_res.json()["error"]
        assert err["code"] == "SELF_APPROVAL_FORBIDDEN"


@pytest.mark.asyncio
async def test_developer_approval_forbidden_403():
    """5. DEVELOPER duyệt -> 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        owner_user, owner_headers = await create_user_and_headers(client, "Owner")
        org, project, envs = await setup_test_hierarchy(client, owner_headers)

        dev_user, dev_headers = await create_user_and_headers(client, "Dev")
        # Add dev to org as DEVELOPER
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": dev_user["id"], "role": "DEVELOPER"},
            headers=owner_headers,
        )

        prod_env = next(e for e in envs if e["is_production"] is True)

        # Owner creates CR
        cr_res = await client.post(
            f"/api/v1/environments/{prod_env['id']}/change-requests",
            json={
                "title": "Dev approval attempt",
                "payload": {"type": "flag_setting", "setting": {"enabled": True}},
            },
            headers=owner_headers,
        )
        cr = cr_res.json()

        # Dev tries to approve
        dev_approve_res = await client.post(
            f"{CR_PREFIX}/{cr['id']}/approve",
            headers=dev_headers,
        )
        assert dev_approve_res.status_code == 403
        assert dev_approve_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_other_user_approves_applies_and_increments_ruleset_version():
    """4. Người khác duyệt -> APPLIED, thay đổi có hiệu lực, ruleset_version tăng."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        owner_user, owner_headers = await create_user_and_headers(client, "Owner")
        org, project, envs = await setup_test_hierarchy(client, owner_headers)

        dev_user, dev_headers = await create_user_and_headers(client, "Dev")
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": dev_user["id"], "role": "DEVELOPER"},
            headers=owner_headers,
        )

        prod_env = next(e for e in envs if e["is_production"] is True)
        init_ruleset_version = prod_env["ruleset_version"]

        # Flag created in project
        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": f"apply_flag_{uuid.uuid4().hex[:6]}",
                "name": "Apply Flag",
                "type": "BOOLEAN",
            },
            headers=owner_headers,
        )
        flag = flag_res.json()

        # Dev creates CR by modifying flag setting in production
        put_res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            json={"enabled": True},
            headers=dev_headers,
        )
        assert put_res.status_code == 202
        cr_id = put_res.json()["change_request_id"]

        # Owner approves the CR created by Dev
        approve_res = await client.post(
            f"{CR_PREFIX}/{cr_id}/approve",
            headers=owner_headers,
        )
        assert approve_res.status_code == 200
        approved_cr = approve_res.json()
        assert approved_cr["status"] == "APPLIED"
        assert approved_cr["reviewed_by"] == owner_user["id"]
        assert approved_cr["applied_at"] is not None

        # Verify flag setting in production IS NOW ENABLED
        setting_res = await client.get(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        assert setting_res.json()["enabled"] is True

        # Verify ruleset_version incremented
        env_check_res = await client.get(
            f"{PROJECT_PREFIX}/{project['id']}/environments",
            headers=owner_headers,
        )
        updated_prod_env = next(e for e in env_check_res.json() if e["id"] == prod_env["id"])
        assert updated_prod_env["ruleset_version"] > init_ruleset_version


@pytest.mark.asyncio
async def test_reject_change_request():
    """6. Reject -> thay đổi KHÔNG được áp dụng."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        owner_user, owner_headers = await create_user_and_headers(client, "Owner")
        org, project, envs = await setup_test_hierarchy(client, owner_headers)

        dev_user, dev_headers = await create_user_and_headers(client, "Dev")
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": dev_user["id"], "role": "DEVELOPER"},
            headers=owner_headers,
        )

        prod_env = next(e for e in envs if e["is_production"] is True)

        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": f"reject_flag_{uuid.uuid4().hex[:6]}",
                "name": "Reject Flag",
                "type": "BOOLEAN",
            },
            headers=owner_headers,
        )
        flag = flag_res.json()

        # Dev creates CR
        put_res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            json={"enabled": True},
            headers=dev_headers,
        )
        cr_id = put_res.json()["change_request_id"]

        # Owner rejects CR
        reject_res = await client.post(
            f"{CR_PREFIX}/{cr_id}/reject",
            headers=owner_headers,
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"

        # Verify flag setting is STILL disabled
        setting_res = await client.get(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        assert setting_res.json()["enabled"] is False


@pytest.mark.asyncio
async def test_impact_simulation_calculation():
    """7. Impact trả đúng số lượng trên dữ liệu dựng sẵn."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        owner_user, owner_headers = await create_user_and_headers(client, "Owner")
        org, project, envs = await setup_test_hierarchy(client, owner_headers)

        prod_env = next(e for e in envs if e["is_production"] is True)

        # Create flag with 2 variations: on and off
        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": f"impact_flag_{uuid.uuid4().hex[:6]}",
                "name": "Impact Flag",
                "type": "BOOLEAN",
                "variations": [
                    {"key": "on", "value": True, "name": "On"},
                    {"key": "off", "value": False, "name": "Off"},
                ],
            },
            headers=owner_headers,
        )
        flag = flag_res.json()
        flag_id = uuid.UUID(flag["id"])
        env_id = uuid.UUID(prod_env["id"])

        # Insert 100 historical evaluation events in DB for this flag/env
        off_var = next(v for v in flag["variations"] if v["key"] == "off")
        off_var_id = uuid.UUID(off_var["id"])

        async with async_session_factory() as db:
            events = [
                EvaluationEvent(
                    environment_id=env_id,
                    flag_id=flag_id,
                    variation_id=off_var_id,
                    reason="DISABLED",
                    context_key_hash=f"hash_{i}",
                    context={"targetingKey": f"user-{i}", "country": "VN"},
                )
                for i in range(100)
            ]
            db.add_all(events)
            await db.commit()

        # Create CR that enables the flag (so it transitions from off -> on)
        cr_res = await client.post(
            f"/api/v1/environments/{prod_env['id']}/change-requests",
            json={
                "title": "Enable impact flag",
                "payload": {
                    "type": "flag_setting",
                    "flag_id": flag["id"],
                    "flag_key": flag["key"],
                    "setting": {"enabled": True},
                },
            },
            headers=owner_headers,
        )
        assert cr_res.status_code == 201
        cr = cr_res.json()

        # Run impact simulation
        impact_res = await client.get(
            f"{CR_PREFIX}/{cr['id']}/impact",
            headers=owner_headers,
        )
        assert impact_res.status_code == 200
        impact = impact_res.json()

        assert impact["total_contexts"] == 100
        assert impact["affected_contexts"] == 100
        assert impact["change_percentage"] == 100.0
        assert len(impact["transitions"]) == 1
        t = impact["transitions"][0]
        assert t["from_variation"] == "off"
        assert t["to_variation"] == "on"
        assert t["count"] == 100
        assert "100" in impact["summary"]


@pytest.mark.asyncio
async def test_scheduled_change_applied_by_scheduler():
    """8. scheduled_at trong quá khứ -> áp dụng ở lần quét kế tiếp."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        owner_user, owner_headers = await create_user_and_headers(client, "Owner")
        org, project, envs = await setup_test_hierarchy(client, owner_headers)

        dev_user, dev_headers = await create_user_and_headers(client, "Dev")
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": dev_user["id"], "role": "DEVELOPER"},
            headers=owner_headers,
        )

        prod_env = next(e for e in envs if e["is_production"] is True)

        flag_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": f"sched_flag_{uuid.uuid4().hex[:6]}",
                "name": "Sched Flag",
                "type": "BOOLEAN",
            },
            headers=owner_headers,
        )
        flag = flag_res.json()

        # Schedule for 10 minutes in the future
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        cr_res = await client.post(
            f"/api/v1/environments/{prod_env['id']}/change-requests",
            json={
                "title": "Scheduled Flag Enable",
                "scheduled_at": future_time.isoformat(),
                "payload": {
                    "type": "flag_setting",
                    "flag_id": flag["id"],
                    "flag_key": flag["key"],
                    "setting": {"enabled": True},
                },
            },
            headers=dev_headers,
        )
        cr = cr_res.json()

        # Owner approves -> should become APPROVED (not APPLIED yet because it is in the future)
        approve_res = await client.post(
            f"{CR_PREFIX}/{cr['id']}/approve",
            headers=owner_headers,
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "APPROVED"

        # Now simulate time passing: set scheduled_at to 5 minutes ago in DB
        async with async_session_factory() as db:
            db_cr = await db.scalar(
                select(ChangeRequest).where(ChangeRequest.id == uuid.UUID(cr["id"]))
            )
            db_cr.scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            await db.commit()

        # Trigger scheduler process
        async with async_session_factory() as db:
            applied_count = await change_request_service.process_scheduled_change_requests(db)
            assert applied_count >= 1

        # Verify CR is now APPLIED
        detail_res = await client.get(f"{CR_PREFIX}/{cr['id']}", headers=owner_headers)
        assert detail_res.json()["status"] == "APPLIED"

        # Verify setting is now enabled
        setting_res = await client.get(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        assert setting_res.json()["enabled"] is True

        # Verify audit log has actor_id = None and action = "change_request.applied_by_scheduler"
        async with async_session_factory() as db:
            audit = await db.scalar(
                select(AuditLog).where(
                    AuditLog.entity_id == cr["id"],
                    AuditLog.action == "change_request.applied_by_scheduler",
                )
            )
            assert audit is not None
            assert audit.actor_id is None


@pytest.mark.asyncio
async def test_payload_execution_failure_rollback():
    """9. Áp dụng lỗi giữa chừng -> rollback, CR quay về APPROVED, ghi log lỗi."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        owner_user, owner_headers = await create_user_and_headers(client, "Owner")
        org, project, envs = await setup_test_hierarchy(client, owner_headers)

        dev_user, dev_headers = await create_user_and_headers(client, "Dev")
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": dev_user["id"], "role": "DEVELOPER"},
            headers=owner_headers,
        )

        prod_env = next(e for e in envs if e["is_production"] is True)

        # Non-existent flag id to force an exception during execution
        fake_flag_id = str(uuid.uuid4())
        cr_res = await client.post(
            f"/api/v1/environments/{prod_env['id']}/change-requests",
            json={
                "title": "Failing payload CR",
                "payload": {
                    "type": "flag_setting",
                    "flag_id": fake_flag_id,
                    "setting": {"enabled": True},
                },
            },
            headers=dev_headers,
        )
        cr = cr_res.json()

        # Approve will fail during payload application
        approve_res = await client.post(
            f"{CR_PREFIX}/{cr['id']}/approve",
            headers=owner_headers,
        )
        assert approve_res.status_code == 500
        assert approve_res.json()["error"]["code"] == "PAYLOAD_APPLICATION_FAILED"

        # Check CR in DB is preserved in APPROVED status (not corrupted or APPLIED)
        async with async_session_factory() as db:
            db_cr = await db.scalar(
                select(ChangeRequest).where(ChangeRequest.id == uuid.UUID(cr["id"]))
            )
            assert db_cr.status == ChangeRequestStatus.APPROVED
