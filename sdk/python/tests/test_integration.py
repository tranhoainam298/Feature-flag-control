"""Integration test connecting real FlagOpsClient to running FlagOps backend."""

import uuid
import httpx
import pytest

from flagops.client import FlagOpsClient

BACKEND_URL = "http://localhost:8000"


def _is_backend_alive() -> bool:
    try:
        res = httpx.get(f"{BACKEND_URL}/health", timeout=2.0)
        return res.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _is_backend_alive(), reason="FlagOps backend server is not running on localhost:8000")
def test_sdk_integration_with_live_server():
    """End-to-end integration test with live Docker FlagOps backend."""
    u_id = uuid.uuid4().hex[:6]
    email = f"sdk_test_{u_id}@flagops.io"
    password = "StrongPassword123!"

    # 1. Register & login to create an environment & API key
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as http:
        http.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "SDK Tester"})
        login_res = http.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = login_res.json()["access_token"]
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Create org, project, get dev env
        org_res = http.post("/api/v1/organizations", json={"name": f"Org {u_id}", "slug": f"org-{u_id}"}, headers=auth_hdr)
        org_id = org_res.json()["id"]

        proj_res = http.post(f"/api/v1/organizations/{org_id}/projects", json={"name": "SDK Project", "slug": f"proj-{u_id}"}, headers=auth_hdr)
        proj_id = proj_res.json()["id"]

        envs = http.get(f"/api/v1/projects/{proj_id}/environments", headers=auth_hdr).json()
        dev_env = next(e for e in envs if e["key"] == "development")

        # Create SERVER API key
        key_res = http.post(
            f"/api/v1/environments/{dev_env['id']}/api-keys",
            json={"name": "SDK Key", "scope": "SERVER"},
            headers=auth_hdr,
        )
        api_key = key_res.json()["key"]

        # Create a boolean flag and enable it
        flag_key = f"sdk-flag-{u_id}"
        flag_res = http.post(
            f"/api/v1/projects/{proj_id}/flags",
            json={"key": flag_key, "name": "SDK Test Flag", "type": "BOOLEAN"},
            headers=auth_hdr,
        )
        flag_id = flag_res.json()["id"]

        # Turn ON flag in development
        http.put(
            f"/api/v1/flags/{flag_id}/environments/{dev_env['id']}",
            json={"enabled": True},
            headers=auth_hdr,
        )

        # Create a namespace & config item and publish release
        ns_name = f"sdk-cfg-{u_id}"
        ns_res = http.post(
            f"/api/v1/environments/{dev_env['id']}/namespaces",
            json={"name": ns_name, "format": "JSON"},
            headers=auth_hdr,
        )
        ns_id = ns_res.json()["id"]

        http.put(
            f"/api/v1/namespaces/{ns_id}/items",
            json={"items": [{"key": "app.title", "value": "FlagOps Live", "value_type": "STRING"}]},
            headers=auth_hdr,
        )
        http.post(f"/api/v1/namespaces/{ns_id}/releases", json={"comment": "Initial"}, headers=auth_hdr)

    # 2. Test FlagOpsClient in in_process mode
    with FlagOpsClient(api_key=api_key, base_url=BACKEND_URL, mode="in_process", timeout=3.0) as client:
        # Flag was enabled -> must evaluate to True
        is_on = client.is_enabled(flag_key, default=False)
        assert is_on is True

        # Non-existent flag -> returns default False
        missing_on = client.is_enabled("non-existent-key", default=False)
        assert missing_on is False

        # Read config namespace
        configs = client.get_config(ns_name)
        assert configs.get("app.title") == "FlagOps Live"
