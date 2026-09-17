import json
import subprocess
import sys
import time
import uuid

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000"

def run_curl(desc: str, cmd_args: list[str]) -> dict:
    print(f"\n=======================================================")
    print(f"STEP: {desc}")
    full_cmd = ["curl.exe", "-s"] + cmd_args
    print(f"$ {' '.join(full_cmd)}")
    result = subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        data = json.loads(result.stdout)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except Exception:
        print(result.stdout)
        return {"raw": result.stdout}

def main():
    u_id = uuid.uuid4().hex[:6]
    email = f"curl_demo_{u_id}@flagops.io"
    password = "StrongPassword123!"

    # 1. Register & Login
    run_curl("1. Register User", [
        "-X", "POST", f"{BASE}/api/v1/auth/register",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"email": email, "password": password, "full_name": "Curl Demo User"})
    ])

    login_res = run_curl("2. Login to get JWT Token", [
        "-X", "POST", f"{BASE}/api/v1/auth/login",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"email": email, "password": password})
    ])
    token = login_res["access_token"]
    auth_header = f"Authorization: Bearer {token}"

    # 2. Create Org & Project
    org_res = run_curl("3. Create Organization", [
        "-X", "POST", f"{BASE}/api/v1/organizations",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"name": f"Demo Org {u_id}", "slug": f"demo-org-{u_id}"})
    ])
    org_id = org_res["id"]

    proj_res = run_curl("4. Create Project", [
        "-X", "POST", f"{BASE}/api/v1/organizations/{org_id}/projects",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"name": "Billing App", "slug": f"billing-app-{u_id}"})
    ])
    proj_id = proj_res["id"]

    envs = run_curl("5. Get Environments", [
        "-H", auth_header,
        f"{BASE}/api/v1/projects/{proj_id}/environments"
    ])
    dev_env = next(e for e in envs if e["key"] == "development")
    dev_env_id = dev_env["id"]

    # Create SERVER API key for client reads
    key_res = run_curl("6. Create Server API Key", [
        "-X", "POST", f"{BASE}/api/v1/environments/{dev_env_id}/api-keys",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"name": "Server API Key", "scope": "SERVER"})
    ])
    api_key = key_res["key"]

    # 3. Create Namespace
    ns_name = f"billing-service"
    ns_res = run_curl("7. Create Namespace", [
        "-X", "POST", f"{BASE}/api/v1/environments/{dev_env_id}/namespaces",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"name": ns_name, "format": "JSON"})
    ])
    ns_id = ns_res["id"]

    # 4. Sửa nháp (PUT /items)
    run_curl("8. Sửa bản nháp (PUT /items)", [
        "-X", "PUT", f"{BASE}/api/v1/namespaces/{ns_id}/items",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "items": [
                {"key": "database.url", "value": "postgresql://pg:5432/billing", "value_type": "STRING"},
                {"key": "max_connections", "value": "20", "value_type": "INT"},
                {"key": "api.secret", "value": "very-secret-token-xyz", "value_type": "STRING", "is_secret": True}
            ]
        })
    ])

    # 5. Xem pending diff (GET /pending-diff)
    run_curl("9. Xem Diff trước khi publish (GET /pending-diff)", [
        "-H", auth_header,
        f"{BASE}/api/v1/namespaces/{ns_id}/pending-diff"
    ])

    # 6. Publish Release v1 (POST /releases)
    run_curl("10. Publish Release v1 (POST /releases)", [
        "-X", "POST", f"{BASE}/api/v1/namespaces/{ns_id}/releases",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"comment": "Initial release of billing configs"})
    ])

    # 7. Client đọc config qua API key
    run_curl("11. Client SDK đọc config v1 (/eval/v1/config/billing-service)", [
        "-H", f"X-FlagOps-Key: {api_key}",
        f"{BASE}/eval/v1/config/{ns_name}"
    ])

    # 8. Sửa nháp lần 2 (Đổi max_connections, xóa database.url, thêm stripe.mode)
    run_curl("12. Sửa bản nháp lần 2 (Sửa max_conn, xóa db.url, thêm stripe.mode)", [
        "-X", "PUT", f"{BASE}/api/v1/namespaces/{ns_id}/items",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "items": [
                {"key": "max_connections", "value": "50", "value_type": "INT"},
                {"key": "api.secret", "value": "••••••", "value_type": "STRING", "is_secret": True},
                {"key": "stripe.mode", "value": "live", "value_type": "STRING"}
            ]
        })
    ])

    # 9. Xem pending diff giữa v1 và nháp mới
    run_curl("13. Xem Diff giữa Release v1 và bản nháp mới", [
        "-H", auth_header,
        f"{BASE}/api/v1/namespaces/{ns_id}/pending-diff"
    ])

    # 10. Publish Release v2
    run_curl("14. Publish Release v2", [
        "-X", "POST", f"{BASE}/api/v1/namespaces/{ns_id}/releases",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"comment": "Bump max_connections and enable stripe live"})
    ])

    # 11. Client đọc config v2
    run_curl("15. Client SDK đọc config v2", [
        "-H", f"X-FlagOps-Key: {api_key}",
        f"{BASE}/eval/v1/config/{ns_name}"
    ])

    # 12. Rollback về Release v1
    run_curl("16. Rollback về Release v1 (POST /releases/1/rollback)", [
        "-X", "POST", f"{BASE}/api/v1/namespaces/{ns_id}/releases/1/rollback",
        "-H", auth_header,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"comment": "Emergency rollback to v1"})
    ])

    # 13. Xem danh sách Releases (v1, v2, v3 với is_rollback_of=1)
    run_curl("17. Xem lịch sử releases (GET /releases)", [
        "-H", auth_header,
        f"{BASE}/api/v1/namespaces/{ns_id}/releases"
    ])

    # 14. Client đọc config v3 (nội dung quay về đúng v1)
    run_curl("18. Client SDK đọc config sau rollback (v3 mang giá trị v1)", [
        "-H", f"X-FlagOps-Key: {api_key}",
        f"{BASE}/eval/v1/config/{ns_name}"
    ])

if __name__ == "__main__":
    main()
