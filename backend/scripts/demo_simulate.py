"""Demo script to execute real curl requests against the simulate endpoint."""

import json
import subprocess
import uuid

import httpx

API_URL = "http://localhost:8000"


def run_curl(url: str, token: str, payload: dict) -> dict:
    cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        url,
        "-H",
        "Content-Type: application/json",
        "-H",
        f"Authorization: Bearer {token}",
        "-d",
        json.dumps(payload),
    ]
    print(f"\n$ {' '.join(cmd[:6])} -d '{json.dumps(payload)}'")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    try:
        return json.loads(result.stdout)
    except Exception:
        print("Raw output:", result.stdout)
        raise


def main():
    email = f"demo_{uuid.uuid4().hex[:6]}@flagops.dev"
    password = "Str0ngP@ssword123"

    print("1. Registering demo user...")
    with httpx.Client(base_url=API_URL) as client:
        r = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Demo Admin"},
        )
        r.raise_for_status()

        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        login_res.raise_for_status()
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("2. Creating Organization and Project...")
        org_slug = f"demo-org-{uuid.uuid4().hex[:6]}"
        org_res = client.post(
            "/api/v1/organizations",
            json={"name": "Demo Corp", "slug": org_slug},
            headers=headers,
        )
        org_res.raise_for_status()
        org_id = org_res.json()["id"]

        proj_slug = f"demo-proj-{uuid.uuid4().hex[:6]}"
        proj_res = client.post(
            f"/api/v1/organizations/{org_id}/projects",
            json={"name": "E-Commerce", "slug": proj_slug},
            headers=headers,
        )
        proj_res.raise_for_status()
        proj_id = proj_res.json()["id"]

        env_res = client.get(f"/api/v1/projects/{proj_id}/environments", headers=headers)
        envs = env_res.json()
        dev_env = next(e for e in envs if e["key"] == "development")
        env_id = dev_env["id"]

        print("3. Creating Flag 'checkout_v2'...")
        flag_key = f"checkout_v2_{uuid.uuid4().hex[:4]}"
        flag_res = client.post(
            f"/api/v1/projects/{proj_id}/flags",
            json={"key": flag_key, "name": "New Checkout Flow", "type": "BOOLEAN"},
            headers=headers,
        )
        flag_res.raise_for_status()
        flag = flag_res.json()
        flag_id = flag["id"]
        var_true = next(v for v in flag["variations"] if v["value"] is True)
        var_false = next(v for v in flag["variations"] if v["value"] is False)

        # Enable in dev
        client.put(
            f"/api/v1/flags/{flag_id}/environments/{env_id}",
            json={
                "enabled": True,
                "default_variation_id": var_false["id"],
                "off_variation_id": var_false["id"],
            },
            headers=headers,
        )

        print("4. Creating Segment 'beta_testers'...")
        seg_res = client.post(
            f"/api/v1/projects/{proj_id}/segments",
            json={
                "name": "Beta Testers",
                "key": f"beta_{uuid.uuid4().hex[:4]}",
                "conditions": {
                    "operator": "AND",
                    "conditions": [
                        {"attribute": "email", "operator": "ENDS_WITH", "value": "@flagops.dev"}
                    ],
                },
            },
            headers=headers,
        )
        seg_res.raise_for_status()
        segment = seg_res.json()

        print("5. Setting Targeting Rules (Priority 1: Beta Testers -> On)...")
        rules_res = client.put(
            f"/api/v1/flags/{flag_id}/environments/{env_id}/rules",
            json={
                "rules": [
                    {
                        "priority": 1,
                        "description": "Beta Testers Segment receives New Checkout",
                        "conditions": {
                            "operator": "AND",
                            "conditions": [
                                {
                                    "attribute": "",
                                    "operator": "IS_ONE_OF_SEGMENT",
                                    "value": segment["id"],
                                }
                            ],
                        },
                        "distribution": [{"variation_id": var_true["id"], "weight": 100.0}],
                    }
                ]
            },
            headers=headers,
        )
        rules_res.raise_for_status()

        print("6. Setting Individual Override ('vip_ceo' -> On)...")
        ov_res = client.post(
            f"/api/v1/flags/{flag_id}/environments/{env_id}/overrides",
            json={"context_key": "vip_ceo", "variation_id": var_true["id"]},
            headers=headers,
        )
        ov_res.raise_for_status()

    # 7. Execute real CURL calls to simulate endpoint
    simulate_url = f"{API_URL}/api/v1/flags/{flag_id}/environments/{env_id}/simulate"
    print("\n" + "=" * 80)
    print("DEMO: REAL CURL CALLS TO /simulate ENDPOINT")
    print("=" * 80)

    # Call A: Individual Override
    print("\n--- CONTEXT 1: Individual Override (targetingKey='vip_ceo') ---")
    res_a = run_curl(
        simulate_url,
        token,
        {"context": {"targetingKey": "vip_ceo", "email": "ceo@external.com"}},
    )
    print(json.dumps(res_a, indent=2))

    # Call B: Segment Targeting Rule match
    print("\n--- CONTEXT 2: Targeting Rule Match (email='engineer@flagops.dev') ---")
    res_b = run_curl(
        simulate_url,
        token,
        {"context": {"targetingKey": "alice", "email": "engineer@flagops.dev"}},
    )
    print(json.dumps(res_b, indent=2))

    # Call C: Default Fallback
    print("\n--- CONTEXT 3: Default Fallback (email='visitor@gmail.com') ---")
    res_c = run_curl(
        simulate_url,
        token,
        {"context": {"targetingKey": "bob", "email": "visitor@gmail.com"}},
    )
    print(json.dumps(res_c, indent=2))


if __name__ == "__main__":
    main()
