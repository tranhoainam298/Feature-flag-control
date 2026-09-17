"""Demonstration script for Slice 16 — Change Request with 2 Accounts.

Demonstrates:
1. Dev logs in (dev@demo.local)
2. Dev attempts to modify a flag in the Production environment
3. Backend intercepts and creates a ChangeRequest in PENDING status (flag remains unchanged)
4. Dev attempts to self-approve -> 403 SELF_APPROVAL_FORBIDDEN
5. Owner logs in (owner@demo.local)
6. Owner simulates impact -> engine runs on historical contexts and outputs transition summary
7. Owner approves Change Request -> status becomes APPLIED, live flag setting updates,
   and ruleset_version increments
"""

import asyncio
import sys

import httpx

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        print("=================================================================")
        print("[DEMO SLICE 16] CHANGE REQUEST & FOUR-EYES APPROVAL")
        print("=================================================================")

        # Step 1: Login as Dev
        print("\n[1] Đăng nhập tài khoản Developer (dev@demo.local)...")
        dev_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "dev@demo.local", "password": "demo1234"},
        )
        assert dev_res.status_code == 200, f"Dev login failed: {dev_res.text}"
        dev_token = dev_res.json()["access_token"]
        dev_headers = {"Authorization": f"Bearer {dev_token}"}
        print("    -> Dev đăng nhập thành công.")

        # Step 2: Login as Owner
        print("\n[2] Đăng nhập tài khoản Owner (owner@demo.local)...")
        owner_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@demo.local", "password": "demo1234"},
        )
        assert owner_res.status_code == 200, f"Owner login failed: {owner_res.text}"
        owner_token = owner_res.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        print("    -> Owner đăng nhập thành công.")

        # Find demo project & prod environment
        orgs_res = await client.get("/api/v1/organizations", headers=owner_headers)
        demo_org = orgs_res.json()[0]
        projs_res = await client.get(
            f"/api/v1/organizations/{demo_org['id']}/projects", headers=owner_headers
        )
        demo_proj = projs_res.json()[0]
        envs_res = await client.get(
            f"/api/v1/projects/{demo_proj['id']}/environments", headers=owner_headers
        )
        prod_env = next(e for e in envs_res.json() if e.get("is_production") is True)
        print(
            f"    -> Project: {demo_proj['name']} | "
            f"Production Environment: {prod_env['name']} (ID: {prod_env['id']})"
        )

        # Get or create a flag in this project
        flags_res = await client.get(
            f"/api/v1/projects/{demo_proj['id']}/flags", headers=owner_headers
        )
        flags = flags_res.json()
        if not flags:
            new_flag = await client.post(
                f"/api/v1/projects/{demo_proj['id']}/flags",
                json={"key": "checkout-redesign", "name": "Checkout Redesign", "type": "BOOLEAN"},
                headers=owner_headers,
            )
            flag = new_flag.json()
        else:
            flag = flags[0]
        print(f"    -> Target Flag: '{flag['name']}' (key: {flag['key']})")

        # Check current setting in prod
        initial_setting = await client.get(
            f"/api/v1/flags/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        curr_enabled = initial_setting.json()["enabled"]
        target_enabled = not curr_enabled
        print(f"    -> Giá trị hiện tại ở Production: enabled = {curr_enabled}")

        # Step 3: Developer modifies flag in Production -> Intercepted as CR
        print(
            f"\n[3] Developer cố gắng sửa cờ '{flag['key']}' "
            f"thành enabled = {target_enabled} trên Production..."
        )
        put_res = await client.put(
            f"/api/v1/flags/{flag['id']}/environments/{prod_env['id']}",
            json={"enabled": target_enabled},
            headers=dev_headers,
        )
        print(f"    -> Response status: {put_res.status_code}")
        body = put_res.json()
        cr_id = body.get("change_request_id")
        print(f"    -> Hệ thống chặn trực tiếp, tạo Change Request: ID = {cr_id}")
        print(f"    -> Trạng thái Change Request: {body.get('change_request_status')}")

        # Verify live flag setting remains unchanged
        verify_setting = await client.get(
            f"/api/v1/flags/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        assert verify_setting.json()["enabled"] == curr_enabled
        print(
            f"    -> Kiểm tra cờ thực tế: vẫn giữ nguyên enabled = "
            f"{verify_setting.json()['enabled']} (An toàn!)"
        )

        # Step 4: Developer attempts self-approval
        print("\n[4] Developer cố gắng tự duyệt Change Request của chính mình (Vi phạm bốn mắt)...")
        self_approve_res = await client.post(
            f"/api/v1/change-requests/{cr_id}/approve",
            headers=dev_headers,
        )
        print(f"    -> Response status: {self_approve_res.status_code}")
        err = self_approve_res.json()["error"]
        print(f"    -> Bị từ chối: mã lỗi '{err['code']}' — \"{err['message']}\"")
        assert self_approve_res.status_code == 403
        assert err["code"] == "SELF_APPROVAL_FORBIDDEN"

        # Step 5: Owner runs Impact Simulation
        print("\n[5] Owner xem Change Request và chạy Mô phỏng tác động (/impact)...")
        impact_res = await client.get(
            f"/api/v1/change-requests/{cr_id}/impact",
            headers=owner_headers,
        )
        assert impact_res.status_code == 200
        impact = impact_res.json()
        print(f"    -> Kết quả mô phỏng: {impact['summary']}")
        print(
            f"    -> Tổng context phân tích: {impact['total_contexts']} | "
            f"Tỉ lệ thay đổi: {impact['change_percentage']}%"
        )
        for t in impact["transitions"]:
            print(
                f"       * Chuyển dịch: {t['from_variation']} -> {t['to_variation']} "
                f"({t['count']} users)"
            )

        # Step 6: Owner approves Change Request
        print("\n[6] Owner tiến hành phê duyệt Change Request...")
        approve_res = await client.post(
            f"/api/v1/change-requests/{cr_id}/approve",
            headers=owner_headers,
        )
        assert approve_res.status_code == 200
        approved_body = approve_res.json()
        print(f"    -> Phê duyệt thành công: Trạng thái mới = '{approved_body['status']}'")
        print(f"    -> Người duyệt (reviewed_by): {approved_body['reviewed_by']}")
        print(f"    -> Thời điểm áp dụng (applied_at): {approved_body['applied_at']}")

        # Step 7: Verify final flag setting in Production
        final_setting = await client.get(
            f"/api/v1/flags/{flag['id']}/environments/{prod_env['id']}",
            headers=owner_headers,
        )
        print("\n[7] Kiểm tra giá trị cờ thực tế trên Production sau khi duyệt:")
        print(f"    -> enabled = {final_setting.json()['enabled']} (Đã đổi thành công!)")
        assert final_setting.json()["enabled"] == target_enabled

        print("\n=================================================================")
        print("[SUCCESS] TOAN BO QUY TRINH KIEM SOAT THAY DOI SLICE 16 HOAN THANH XUAT SAC!")
        print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())
