"""Integration tests for Slice 6 — Segment & Targeting Rule.

Covers:
- Segment CRUD (create, list, get, update, delete, duplicate key conflict 409)
- Targeting Rules atomic PUT overwrite & GET
- Validations:
  - weight sum != 100 -> 422
  - duplicate priority -> 422
  - condition depth > 5 -> 400 CONDITION_DEPTH_EXCEEDED
  - variation belongs to another flag -> 422 INVALID_VARIATION
  - invalid operator -> 422 INVALID_OPERATOR
  - segment from another project -> 422 SEGMENT_PROJECT_MISMATCH
- Transaction rollback on failed PUT
- Ruleset version increment
- Individual Override create, update, delete
- Simulate endpoint with 3 distinct contexts producing 3 distinct results and trace
- Role permissions & Cross-org 404
"""

import uuid
from typing import Any

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
    return f"test-target-{uuid.uuid4().hex[:12]}@example.com"


def _unique_slug(prefix: str = "target") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_and_login_user(client: AsyncClient) -> tuple[dict, dict]:
    email = _unique_email()
    reg_resp = await client.post(
        f"{AUTH_PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Target User"},
    )
    user_data = reg_resp.json()

    login_resp = await client.post(
        f"{AUTH_PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    token_data = login_resp.json()
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    return user_data, headers


async def setup_project_with_flag(
    client: AsyncClient, headers: dict
) -> tuple[dict, dict, dict, dict, list[dict]]:
    """Helper to create Org, Project, Environments, and a Boolean Flag."""
    org_resp = await client.post(
        ORG_PREFIX,
        json={"name": "Target Org", "slug": _unique_slug("org")},
        headers=headers,
    )
    org = org_resp.json()

    proj_resp = await client.post(
        f"{ORG_PREFIX}/{org['id']}/projects",
        json={"name": "Target Project", "slug": _unique_slug("proj")},
        headers=headers,
    )
    project = proj_resp.json()

    env_resp = await client.get(
        f"{PROJECT_PREFIX}/{project['id']}/environments",
        headers=headers,
    )
    environments = env_resp.json()
    dev_env = next(e for e in environments if e["key"] == "development")

    flag_resp = await client.post(
        f"{PROJECT_PREFIX}/{project['id']}/flags",
        json={
            "key": f"feat_{uuid.uuid4().hex[:6]}",
            "name": "Feature Flag",
            "type": "BOOLEAN",
        },
        headers=headers,
    )
    flag = flag_resp.json()
    variations = flag["variations"]

    # Enable flag in dev environment
    var_false = next(v for v in variations if v["value"] is False)
    await client.put(
        f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}",
        json={
            "enabled": True,
            "default_variation_id": var_false["id"],
            "off_variation_id": var_false["id"],
        },
        headers=headers,
    )

    return org, project, dev_env, flag, variations


# ==============================================================================
# SEGMENT CRUD TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_segment_crud_lifecycle() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, _, _, _ = await setup_project_with_flag(client, headers)
        p_id = project["id"]

        # 1. Create segment
        seg_payload = {
            "name": "Beta Testers",
            "key": "beta_testers",
            "description": "Internal beta user segment",
            "rules": {
                "operator": "AND",
                "conditions": [
                    {"attribute": "email", "operator": "ENDS_WITH", "value": "@beta.com"}
                ],
            },
        }
        res_create = await client.post(
            f"{PROJECT_PREFIX}/{p_id}/segments",
            json=seg_payload,
            headers=headers,
        )
        assert res_create.status_code == 201
        seg_data = res_create.json()
        assert seg_data["name"] == "Beta Testers"
        assert seg_data["key"] == "beta_testers"
        assert seg_data["project_id"] == p_id
        segment_id = seg_data["id"]

        # 2. Duplicate key conflict -> 409
        res_dup = await client.post(
            f"{PROJECT_PREFIX}/{p_id}/segments",
            json=seg_payload,
            headers=headers,
        )
        assert res_dup.status_code == 409
        assert res_dup.json()["error"]["code"] == "SEGMENT_KEY_EXISTS"

        # 3. List segments
        res_list = await client.get(f"{PROJECT_PREFIX}/{p_id}/segments", headers=headers)
        assert res_list.status_code == 200
        segments = res_list.json()
        assert any(s["id"] == segment_id for s in segments)

        # 4. Get segment by ID
        res_get = await client.get(
            f"{PROJECT_PREFIX}/{p_id}/segments/{segment_id}", headers=headers
        )
        assert res_get.status_code == 200
        assert res_get.json()["id"] == segment_id

        # 5. Update segment
        res_patch = await client.patch(
            f"{PROJECT_PREFIX}/{p_id}/segments/{segment_id}",
            json={"name": "Beta VIPs", "description": "Updated description"},
            headers=headers,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["name"] == "Beta VIPs"
        assert res_patch.json()["description"] == "Updated description"

        # 6. Delete segment
        res_del = await client.delete(
            f"{PROJECT_PREFIX}/{p_id}/segments/{segment_id}", headers=headers
        )
        assert res_del.status_code == 204

        # 7. Get after delete -> 404
        res_after = await client.get(
            f"{PROJECT_PREFIX}/{p_id}/segments/{segment_id}", headers=headers
        )
        assert res_after.status_code == 404


# ==============================================================================
# TARGETING RULES: PUT (ATOMIC OVERWRITE) & GET
# ==============================================================================


@pytest.mark.asyncio
async def test_put_and_get_targeting_rules() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        p_id = project["id"]
        f_id = flag["id"]
        e_id = dev_env["id"]

        var_true = next(v for v in variations if v["value"] is True)

        # Create a segment to reference
        seg_res = await client.post(
            f"{PROJECT_PREFIX}/{p_id}/segments",
            json={
                "name": "Internal Staff",
                "key": "internal_staff",
                "rules": {
                    "operator": "AND",
                    "conditions": [
                        {"attribute": "email", "operator": "ENDS_WITH", "value": "@company.com"}
                    ],
                },
            },
            headers=headers,
        )
        seg = seg_res.json()

        # PUT targeting rules
        rules_payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Rule 1: Internal staff segment",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [
                            {
                                "attribute": "",
                                "operator": "IS_ONE_OF_SEGMENT",
                                "value": seg["id"],
                            }
                        ],
                    },
                    "distribution": [{"variation_id": var_true["id"], "weight": 100.0}],
                },
                {
                    "priority": 2,
                    "description": "Rule 2: Direct attribute condition",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "country", "operator": "EQ", "value": "VN"}],
                    },
                    "distribution": [{"variation_id": var_true["id"], "weight": 100.0}],
                },
            ]
        }

        put_res = await client.put(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/rules",
            json=rules_payload,
            headers=headers,
        )
        assert put_res.status_code == 200
        saved_rules = put_res.json()
        assert len(saved_rules) == 2
        assert saved_rules[0]["priority"] == 1
        assert saved_rules[1]["priority"] == 2

        # GET targeting rules
        get_res = await client.get(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/rules",
            headers=headers,
        )
        assert get_res.status_code == 200
        assert len(get_res.json()) == 2

        # Overwrite with only 1 rule
        overwrite_payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "New Single Rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "tier", "operator": "EQ", "value": "gold"}],
                    },
                    "distribution": [{"variation_id": var_true["id"], "weight": 100.0}],
                }
            ]
        }
        res_ov = await client.put(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/rules",
            json=overwrite_payload,
            headers=headers,
        )
        assert res_ov.status_code == 200
        new_saved = res_ov.json()
        assert len(new_saved) == 1
        assert new_saved[0]["description"] == "New Single Rule"

        # Verify previous 2 rules are replaced
        get_after = await client.get(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/rules",
            headers=headers,
        )
        assert len(get_after.json()) == 1


# ==============================================================================
# VALIDATION TESTS (400 / 422)
# ==============================================================================


@pytest.mark.asyncio
async def test_put_rules_validation_distribution_weight_not_100() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, _, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        # Sum of weights = 80 != 100
        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Bad weight rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 80.0}],
                }
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "INVALID_DISTRIBUTION_WEIGHT"


@pytest.mark.asyncio
async def test_put_rules_validation_duplicate_priority() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, _, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        # Duplicate priority = 1
        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Rule A",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                },
                {
                    "priority": 1,
                    "description": "Rule B",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "b", "operator": "EQ", "value": 2}],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                },
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "DUPLICATE_PRIORITY"


@pytest.mark.asyncio
async def test_put_rules_validation_condition_depth_exceeded() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, _, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        # Build 6 levels deep condition tree (depth 1 to 6)
        curr: dict[str, Any] = {"attribute": "leaf", "operator": "EQ", "value": "val"}
        for _ in range(6):
            curr = {"operator": "AND", "children": [curr]}

        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Too deep rule",
                    "conditions": curr,
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                }
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "CONDITION_DEPTH_EXCEEDED"


@pytest.mark.asyncio
async def test_put_rules_validation_variation_from_other_flag() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, dev_env, flag_a, _ = await setup_project_with_flag(client, headers)

        # Create Flag B
        flag_b_res = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/flags",
            json={
                "key": f"flag_b_{uuid.uuid4().hex[:6]}",
                "name": "Flag B",
                "type": "BOOLEAN",
            },
            headers=headers,
        )
        flag_b = flag_b_res.json()
        flag_b_var_id = flag_b["variations"][0]["id"]

        # Try to use flag_b variation in flag_a rules
        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Cross flag variation rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                    },
                    "distribution": [{"variation_id": flag_b_var_id, "weight": 100.0}],
                }
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag_a['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "INVALID_VARIATION"


@pytest.mark.asyncio
async def test_put_rules_validation_invalid_operator() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, _, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Invalid operator rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [
                            {"attribute": "status", "operator": "MAGIC_MATCH", "value": "vip"}
                        ],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                }
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "INVALID_OPERATOR"


@pytest.mark.asyncio
async def test_put_rules_validation_segment_project_mismatch() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        org, project_a, dev_env, flag_a, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        # Create Project B and Segment in Project B
        proj_b_res = await client.post(
            f"{ORG_PREFIX}/{org['id']}/projects",
            json={"name": "Project B", "slug": _unique_slug("proj-b")},
            headers=headers,
        )
        project_b = proj_b_res.json()

        seg_b_res = await client.post(
            f"{PROJECT_PREFIX}/{project_b['id']}/segments",
            json={
                "name": "Project B Segment",
                "key": "seg_b",
                "rules": {
                    "operator": "AND",
                    "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                },
            },
            headers=headers,
        )
        seg_b = seg_b_res.json()

        # Rule in Flag A referencing Segment B
        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Mismatch segment rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [
                            {
                                "attribute": "",
                                "operator": "IS_ONE_OF_SEGMENT",
                                "value": seg_b["id"],
                            }
                        ],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                }
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag_a['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "SEGMENT_PROJECT_MISMATCH"


# ==============================================================================
# ATOMIC TRANSACTION ROLLBACK TEST
# ==============================================================================


@pytest.mark.asyncio
async def test_put_rules_transaction_rollback_on_failure() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, _, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        # 1. Save valid rule first
        valid_payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Initial stable rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                }
            ]
        }
        put_valid = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=valid_payload,
            headers=headers,
        )
        assert put_valid.status_code == 200

        # 2. Try to PUT an invalid payload (e.g. invalid weight)
        invalid_payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Corrupted rule attempt",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "a", "operator": "EQ", "value": 1}],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 50.0}],
                }
            ]
        }
        put_invalid = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=invalid_payload,
            headers=headers,
        )
        assert put_invalid.status_code == 422

        # 3. Verify original rule was NOT deleted or corrupted
        get_res = await client.get(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            headers=headers,
        )
        assert get_res.status_code == 200
        current_rules = get_res.json()
        assert len(current_rules) == 1
        assert current_rules[0]["description"] == "Initial stable rule"


# ==============================================================================
# RULESET VERSION INCREMENT TEST
# ==============================================================================


@pytest.mark.asyncio
async def test_ruleset_version_increments_after_put_rules() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = variations[0]["id"]

        # Get initial version
        env_res = await client.get(
            f"{PROJECT_PREFIX}/{project['id']}/environments",
            headers=headers,
        )
        env_0 = next(e for e in env_res.json() if e["id"] == dev_env["id"])
        initial_ver = env_0["ruleset_version"]

        # PUT rules
        payload = {
            "rules": [
                {
                    "priority": 1,
                    "description": "Version test rule",
                    "conditions": {
                        "operator": "AND",
                        "conditions": [{"attribute": "v", "operator": "EQ", "value": 1}],
                    },
                    "distribution": [{"variation_id": v_true, "weight": 100.0}],
                }
            ]
        }
        res = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 200

        # Check version increased
        env_res1 = await client.get(
            f"{PROJECT_PREFIX}/{project['id']}/environments",
            headers=headers,
        )
        env_1 = next(e for e in env_res1.json() if e["id"] == dev_env["id"])
        assert env_1["ruleset_version"] > initial_ver


# ==============================================================================
# INDIVIDUAL OVERRIDES TEST
# ==============================================================================


@pytest.mark.asyncio
async def test_individual_override_lifecycle() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, _, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = next(v for v in variations if v["value"] is True)["id"]
        v_false = next(v for v in variations if v["value"] is False)["id"]

        # 1. Create override for "user-123" -> True
        ov_res = await client.post(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/overrides",
            json={"context_key": "user-123", "variation_id": v_true},
            headers=headers,
        )
        assert ov_res.status_code == 201
        override = ov_res.json()
        assert override["context_key"] == "user-123"
        assert override["variation_id"] == v_true
        override_id = override["id"]

        # 2. Update override for "user-123" -> False (upsert behavior)
        ov_res2 = await client.post(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/overrides",
            json={"context_key": "user-123", "variation_id": v_false},
            headers=headers,
        )
        assert ov_res2.status_code == 201
        assert ov_res2.json()["variation_id"] == v_false

        # 3. Delete override
        del_res = await client.delete(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/overrides/{override_id}",
            headers=headers,
        )
        assert del_res.status_code == 204


# ==============================================================================
# SIMULATE ENDPOINT TEST (3 CONTEXTS -> 3 RESULTS WITH TRACE)
# ==============================================================================


@pytest.mark.asyncio
async def test_simulate_endpoint_three_distinct_contexts_and_trace() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, headers = await create_and_login_user(client)
        _, project, dev_env, flag, variations = await setup_project_with_flag(client, headers)
        v_true = next(v for v in variations if v["value"] is True)
        v_false = next(v for v in variations if v["value"] is False)

        f_id = flag["id"]
        e_id = dev_env["id"]

        # 1. Setup Individual Override: user "alice" -> True
        await client.post(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/overrides",
            json={"context_key": "alice", "variation_id": v_true["id"]},
            headers=headers,
        )

        # 2. Setup Targeting Rule: Priority 1: email ends with "@beta.com" -> True
        await client.put(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/rules",
            json={
                "rules": [
                    {
                        "priority": 1,
                        "description": "Beta testers match",
                        "conditions": {
                            "operator": "AND",
                            "conditions": [
                                {
                                    "attribute": "email",
                                    "operator": "ENDS_WITH",
                                    "value": "@beta.com",
                                }
                            ],
                        },
                        "distribution": [{"variation_id": v_true["id"], "weight": 100.0}],
                    }
                ]
            },
            headers=headers,
        )

        # --- Context 1: Alice (Triggers Individual Override) ---
        sim1 = await client.post(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/simulate",
            json={"context": {"targetingKey": "alice", "email": "alice@gmail.com"}},
            headers=headers,
        )
        assert sim1.status_code == 200
        res1 = sim1.json()
        assert res1["value"] is True
        assert res1["variant"] == v_true["key"]
        assert len(res1["trace"]) > 0
        assert any(
            t["matched"] is True and "override" in t["description"].lower() for t in res1["trace"]
        )

        # --- Context 2: Bob (Triggers Rule 1) ---
        sim2 = await client.post(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/simulate",
            json={"context": {"targetingKey": "bob", "email": "bob@beta.com"}},
            headers=headers,
        )
        assert sim2.status_code == 200
        res2 = sim2.json()
        assert res2["value"] is True
        assert res2["variant"] == v_true["key"]
        assert res2["matched_rule_description"] == "Beta testers match"
        assert any(t["matched"] is True and t["rule_id"] is not None for t in res2["trace"])

        # --- Context 3: Charlie (Fallthrough to Default Variation) ---
        sim3 = await client.post(
            f"{FLAG_PREFIX}/{f_id}/environments/{e_id}/simulate",
            json={"context": {"targetingKey": "charlie", "email": "charlie@gmail.com"}},
            headers=headers,
        )
        assert sim3.status_code == 200
        res3 = sim3.json()
        assert res3["value"] is False
        assert res3["variant"] == v_false["key"]
        assert res3["reason"] == "DEFAULT"
        assert any(
            t["reason"] == "DEFAULT_FALLBACK" or "default" in t["description"].lower()
            for t in res3["trace"]
        )


@pytest.mark.asyncio
async def test_viewer_role_cannot_modify_targeting_or_segments() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        owner_data, owner_headers = await create_and_login_user(client)
        org, project, dev_env, flag, variations = await setup_project_with_flag(
            client, owner_headers
        )

        viewer_user, viewer_headers = await create_and_login_user(client)
        await client.post(
            f"{ORG_PREFIX}/{org['id']}/members",
            json={"user_id": viewer_user["id"], "role": "VIEWER"},
            headers=owner_headers,
        )

        # Viewer CAN view segments and simulate
        seg_list = await client.get(
            f"{PROJECT_PREFIX}/{project['id']}/segments", headers=viewer_headers
        )
        assert seg_list.status_code == 200

        sim_res = await client.post(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/simulate",
            json={"context": {"targetingKey": "viewer_test"}},
            headers=viewer_headers,
        )
        assert sim_res.status_code == 200

        # Viewer CANNOT create segment -> 403
        seg_create = await client.post(
            f"{PROJECT_PREFIX}/{project['id']}/segments",
            json={
                "name": "Unauthorized Seg",
                "key": "unauth_seg",
                "rules": {"conditions": [{"attribute": "a", "operator": "EQ", "value": 1}]},
            },
            headers=viewer_headers,
        )
        assert seg_create.status_code == 403

        # Viewer CANNOT PUT rules -> 403
        rules_put = await client.put(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/rules",
            json={"rules": []},
            headers=viewer_headers,
        )
        assert rules_put.status_code == 403

        # Viewer CANNOT create override -> 403
        ov_res = await client.post(
            f"{FLAG_PREFIX}/{flag['id']}/environments/{dev_env['id']}/overrides",
            json={"context_key": "any", "variation_id": variations[0]["id"]},
            headers=viewer_headers,
        )
        assert ov_res.status_code == 403


@pytest.mark.asyncio
async def test_cross_org_targeting_and_segment_access_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        _, org_a_headers = await create_and_login_user(client)
        _, proj_a, dev_env_a, flag_a, _ = await setup_project_with_flag(client, org_a_headers)

        # Create Org B user
        _, org_b_headers = await create_and_login_user(client)
        _, proj_b, _, _, _ = await setup_project_with_flag(client, org_b_headers)

        # Org B tries to access Org A's segments -> 404
        res_seg = await client.get(
            f"{PROJECT_PREFIX}/{proj_a['id']}/segments",
            headers=org_b_headers,
        )
        assert res_seg.status_code == 404

        # Org B tries to access Org A's flag rules -> 404
        res_rules = await client.get(
            f"{FLAG_PREFIX}/{flag_a['id']}/environments/{dev_env_a['id']}/rules",
            headers=org_b_headers,
        )
        assert res_rules.status_code == 404
