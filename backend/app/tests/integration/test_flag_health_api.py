"""Integration tests for Flag Health & Lifecycle API (Slice 14)."""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
AUTH_PREFIX = "/api/v1/auth"
ORG_PREFIX = "/api/v1/organizations"
PROJECT_PREFIX = "/api/v1/projects"
FLAG_PREFIX = "/api/v1/flags"

STRONG_PASSWORD = "Str0ngP@ss1"


def _unique_email() -> str:
    return f"test-health-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str = "health") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    email = _unique_email()
    reg_resp = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Health User"},
    )
    user_data = reg_resp.json()

    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    token_data = login_resp.json()
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    return user_data, headers


async def setup_org_and_project(client: AsyncClient, headers: dict) -> tuple[dict, dict, list[dict]]:
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Health Org", "slug": _unique_slug("org")},
        headers=headers,
    )
    org = org_resp.json()

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "Health Project", "slug": _unique_slug("proj")},
        headers=headers,
    )
    project = proj_resp.json()

    envs_resp = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=headers,
    )
    envs = envs_resp.json()
    return org, project, envs


@pytest.mark.asyncio
async def test_list_flag_health_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, _ = await setup_org_and_project(client, headers)

        resp = await client.get(
            f"/api/v1/projects/{project['id']}/flag-health",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["summary"]["total"] == 0
        assert data["summary"]["draft_count"] == 0
        assert data["summary"]["avg_score"] == 0.0


@pytest.mark.asyncio
async def test_list_flag_health_with_flags_and_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, envs = await setup_org_and_project(client, headers)

        # Create a boolean flag (starts in DRAFT)
        flag_resp = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": "test-feature-flag",
                "name": "Test Feature Flag",
                "type": "BOOLEAN",
                "is_temporary": True,
            },
            headers=headers,
        )
        assert flag_resp.status_code == 201
        flag = flag_resp.json()

        # Check list endpoint
        list_resp = await client.get(
            f"/api/v1/projects/{project['id']}/flag-health",
            headers=headers,
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["summary"]["total"] == 1
        assert data["summary"]["draft_count"] == 1
        assert len(data["items"]) == 1

        item = data["items"][0]
        assert item["flag_id"] == flag["id"]
        assert item["flag_key"] == "test-feature-flag"
        assert item["state"] == "DRAFT"
        assert 0 <= item["score"] <= 100
        assert item["is_temporary"] is True

        # Check single flag health endpoint
        single_resp = await client.get(
            f"/api/v1/projects/{project['id']}/flags/{flag['id']}/health",
            headers=headers,
        )
        assert single_resp.status_code == 200
        single_data = single_resp.json()
        assert single_data["flag_id"] == flag["id"]
        assert single_data["state"] == "DRAFT"
        assert isinstance(single_data["recommendations"], list)

        # Enable flag in an environment to transition to ACTIVE
        dev_env = next((e for e in envs if e.get("is_production") is False), envs[0])
        toggle_resp = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}",
            json={"enabled": True},
            headers=headers,
        )
        assert toggle_resp.status_code == 200

        # Verify state transitioned to ACTIVE
        active_resp = await client.get(
            f"/api/v1/projects/{project['id']}/flags/{flag['id']}/health",
            headers=headers,
        )
        assert active_resp.status_code == 200
        assert active_resp.json()["state"] == "ACTIVE"


@pytest.mark.asyncio
async def test_archive_flag_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, _ = await setup_org_and_project(client, headers)

        flag_resp = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": "archive-me-flag",
                "name": "Archive Me Flag",
                "type": "BOOLEAN",
            },
            headers=headers,
        )
        flag = flag_resp.json()

        # Archive the flag
        archive_resp = await client.post(
            f"/api/v1/projects/{project['id']}/flags/{flag['id']}/archive",
            headers=headers,
        )
        assert archive_resp.status_code == 200
        archived_data = archive_resp.json()
        assert archived_data["state"] == "ARCHIVED"

        # Archiving again returns 409
        second_resp = await client.post(
            f"/api/v1/projects/{project['id']}/flags/{flag['id']}/archive",
            headers=headers,
        )
        assert second_resp.status_code == 409

        # Filter by state=ARCHIVED
        filter_resp = await client.get(
            f"/api/v1/projects/{project['id']}/flag-health?state=ARCHIVED",
            headers=headers,
        )
        assert filter_resp.status_code == 200
        items = filter_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["flag_id"] == flag["id"]
