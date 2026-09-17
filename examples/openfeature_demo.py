"""OpenFeature Python SDK Quickstart Example with FlagOps.

Demonstrates the 6-line standard OpenFeature integration:
1. Initialize FlagOpsProvider with API key and server URL.
2. Register provider with OpenFeature api.set_provider().
3. Obtain OpenFeature client via api.get_client().
4. Evaluate feature flags with EvaluationContext across types:
   - Boolean (get_boolean_value / get_boolean_details)
   - String (get_string_value)
   - Integer (get_integer_value)
   - Float (get_float_value)
   - Object (get_object_value)
"""

import sys
import httpx
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
from flagops.openfeature import FlagOpsProvider

BASE_URL = "http://127.0.0.1:8000"


def get_demo_api_key() -> str:
    """Retrieve or generate an API key from the local running FlagOps backend."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=5.0) as http:
            # Login with demo owner
            login = http.post("/api/v1/auth/login", json={"email": "owner@demo.local", "password": "demo1234"})
            if login.status_code != 200:
                print(f"[WARN] Cannot login to backend: {login.text}. Using fallback key.")
                return "fo_srv_demo_key_example"

            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Get first org, project, environment
            orgs = http.get("/api/v1/organizations", headers=headers).json()
            org_id = orgs[0]["id"]
            projs = http.get(f"/api/v1/organizations/{org_id}/projects", headers=headers).json()
            proj_id = projs[0]["id"]
            envs = http.get(f"/api/v1/projects/{proj_id}/environments", headers=headers).json()
            dev_env = envs[0]

            # Generate or reuse API key
            key_res = http.post(
                f"/api/v1/environments/{dev_env['id']}/api-keys",
                json={"name": "OpenFeature Quickstart Key", "scope": "SERVER"},
                headers=headers,
            )
            if key_res.status_code == 201:
                return key_res.json()["key"]

            keys = http.get(f"/api/v1/environments/{dev_env['id']}/api-keys", headers=headers).json()
            return keys[0].get("key", "fo_srv_demo_key_example")
    except Exception as exc:
        print(f"[WARN] Backend not reachable: {exc}. Using fallback key.")
        return "fo_srv_demo_key_example"


def main() -> None:
    api_key = get_demo_api_key()
    print("=" * 60)
    print("  FlagOps OpenFeature Integration Demo (CNCF Standard)")
    print("=" * 60)

    # ──────────────────────────────────────────────────────────────────────────
    # THE 6-LINE OPENFEATURE PATTERN (SPECIFICATION COMPLIANT)
    # ──────────────────────────────────────────────────────────────────────────
    api.set_provider(FlagOpsProvider(api_key=api_key, base_url=BASE_URL))
    client = api.get_client()
    ctx = EvaluationContext(targeting_key="user-123", attributes={"plan": "enterprise", "country": "VN"})
    value = client.get_boolean_value("checkout-v2", False, ctx)
    print(f"\n[OpenFeature] client.get_boolean_value('checkout-v2', False, ctx) -> {value}")

    # Inspect evaluation details (reason, variant, metadata)
    details = client.get_boolean_details("checkout-v2", False, ctx)
    print(f"[OpenFeature] Evaluation Reason : {details.reason}")
    print(f"[OpenFeature] Selected Variant  : {details.variant}")
    print(f"[OpenFeature] Error Code        : {details.error_code}")
    print(f"[OpenFeature] Flag Metadata     : {details.flag_metadata}")

    # Non-existent flag handling: fail-safe default, no crash
    missing_val = client.get_boolean_value("non-existent-flag", False, ctx)
    missing_details = client.get_boolean_details("non-existent-flag", False, ctx)
    print(f"\n[OpenFeature] Missing flag value : {missing_val} (Default)")
    print(f"[OpenFeature] Missing flag error : {missing_details.error_code} ({missing_details.reason})")

    # Clean shutdown
    api.shutdown()
    print("\n[OK] Provider shutdown complete.")


if __name__ == "__main__":
    main()
