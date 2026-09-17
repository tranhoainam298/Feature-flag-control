"""Hot Paths EXPLAIN ANALYZE & Query Count Benchmark for FlagOps.

Executes EXPLAIN (ANALYZE, BUFFERS) directly on PostgreSQL for the 3 hottest paths:
1. Ruleset Bundle Queries (Flags + Variations, Settings + Targeting Rules, Overrides, Segments)
2. API Key Authentication Lookup by key_hash
3. Config Release Snapshot Read (ConfigRelease + JSONB items)

Also checks:
- N+1 Query Detector: Consolidated query counts for load_ruleset_bundle
- Database connection pool configuration
"""

import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from app.core.database import async_session_factory, engine
from app.models import (
    ApiKey,
    ApiKeyScope,
    ConfigFormat,
    ConfigItem,
    ConfigNamespace,
    ConfigRelease,
    ConfigValueType,
    Environment,
    Flag,
    FlagEnvironmentSetting,
    FlagType,
    IndividualOverride,
    MemberRole,
    Membership,
    Organization,
    Project,
    Segment,
    TargetingRule,
    User,
    Variation,
)
from app.services.eval import load_ruleset_bundle


async def setup_rich_sample_data(session) -> dict:
    """Ensure database has realistic records for EXPLAIN ANALYZE."""
    slug_sfx = uuid.uuid4().hex[:6]
    user = User(
        email=f"explain_{slug_sfx}@example.com",
        password_hash="argon2_fake",
        full_name="Explain Tester",
    )
    session.add(user)
    await session.flush()

    org = Organization(name=f"Explain Org {slug_sfx}", slug=f"explain-org-{slug_sfx}")
    session.add(org)
    await session.flush()

    membership = Membership(organization_id=org.id, user_id=user.id, role=MemberRole.OWNER)
    session.add(membership)

    project = Project(name="Explain Project", slug=f"explain-proj-{slug_sfx}", organization_id=org.id)
    session.add(project)
    await session.flush()

    env = Environment(
        name="Production",
        key=f"prod_{slug_sfx}",
        project_id=project.id,
        is_production=True,
        ruleset_version=5,
    )
    session.add(env)
    await session.flush()

    raw_key = f"fo_srv_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    api_key = ApiKey(
        name="Explain Server Key",
        key_prefix=raw_key[:10],
        key_hash=key_hash,
        scope=ApiKeyScope.SERVER,
        environment_id=env.id,
    )
    session.add(api_key)

    # Add 5 flags with variations, settings, rules, overrides
    for i in range(5):
        flag = Flag(
            project_id=project.id,
            key=f"feature-flag-{i}-{slug_sfx}",
            name=f"Feature Flag {i}",
            type=FlagType.BOOLEAN,
        )
        session.add(flag)
        await session.flush()

        v_true = Variation(flag_id=flag.id, key="true", value=True)
        v_false = Variation(flag_id=flag.id, key="false", value=False)
        session.add_all([v_true, v_false])
        await session.flush()

        setting = FlagEnvironmentSetting(
            flag_id=flag.id,
            environment_id=env.id,
            enabled=True,
            default_variation_id=v_true.id,
            off_variation_id=v_false.id,
        )
        session.add(setting)
        await session.flush()

        rule = TargetingRule(
            flag_environment_setting_id=setting.id,
            priority=1,
            conditions=[{"attribute": "country", "operator": "EQ", "value": "VN"}],
            distribution=[{"variation_id": str(v_true.id), "weight": 100.0}],
        )
        session.add(rule)

        override = IndividualOverride(
            flag_environment_setting_id=setting.id,
            context_key=f"user_vip_{i}",
            variation_id=v_true.id,
        )
        session.add(override)

    # Segment
    segment = Segment(
        project_id=project.id,
        key=f"beta-users-{slug_sfx}",
        name="Beta Testers",
        conditions={"rules": [{"attribute": "is_beta", "operator": "EQ", "value": True}]},
    )
    session.add(segment)

    # Config namespace and releases
    ns = ConfigNamespace(
        environment_id=env.id,
        name=f"billing-config-{slug_sfx}",
        format=ConfigFormat.JSON,
    )
    session.add(ns)
    await session.flush()

    rel = ConfigRelease(
        namespace_id=ns.id,
        version=1,
        snapshot={
            "stripe_public_key": "pk_test_12345",
            "max_charge_amount": 50000,
            "enable_instant_payout": True,
        },
        comment="Initial release",
        released_by=user.id,
    )
    session.add(rel)
    await session.flush()
    ns.current_release_id = rel.id

    await session.commit()

    return {
        "project_id": project.id,
        "env_id": env.id,
        "api_key_hash": key_hash,
        "namespace_id": ns.id,
        "release_id": rel.id,
        "env": env,
    }


async def run_explain(session, sql_query: str, params: dict) -> dict:
    """Execute EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)."""
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql_query}"
    res = await session.execute(text(explain_sql), params)
    rows = res.fetchall()
    plan_json = rows[0][0]
    if isinstance(plan_json, list) and plan_json:
        plan_data = plan_json[0]
    else:
        plan_data = plan_json

    plan_node = plan_data.get("Plan", {})
    planning_time = plan_data.get("Planning Time", 0.0)
    exec_time = plan_data.get("Execution Time", 0.0)
    node_type = plan_node.get("Node Type", "Unknown")
    total_cost = plan_node.get("Total Cost", 0.0)
    actual_rows = plan_node.get("Actual Rows", 0)
    shared_hit = plan_node.get("Shared Hit Blocks", 0)
    shared_read = plan_node.get("Shared Read Blocks", 0)

    return {
        "node_type": node_type,
        "planning_time_ms": planning_time,
        "execution_time_ms": exec_time,
        "total_cost": total_cost,
        "actual_rows": actual_rows,
        "shared_hit_blocks": shared_hit,
        "shared_read_blocks": shared_read,
        "raw_plan": plan_data,
    }


async def main():
    print("=====================================================================")
    print(" FlagOps Hot Paths EXPLAIN ANALYZE & Query Optimization Report")
    print("=====================================================================\n")

    async with async_session_factory() as session:
        data = await setup_rich_sample_data(session)
        project_id = str(data["project_id"])
        env_id = str(data["env_id"])
        key_hash = str(data["api_key_hash"])
        ns_id = str(data["namespace_id"])
        rel_id = str(data["release_id"])
        env = data["env"]

        results = {}

        # ------------------------------------------------------------------
        # HOT PATH 1: Ruleset Bundle Queries
        # ------------------------------------------------------------------
        print("--- Hot Path 1: Ruleset Bundle (load_ruleset_bundle) ---")

        q1_flags = """
            SELECT f.id, f.key, f.type, v.id AS var_id, v.key AS var_key, v.value
            FROM flag f
            LEFT JOIN variation v ON v.flag_id = f.id
            WHERE f.project_id = :project_id AND f.archived_at IS NULL
        """
        p1_flags = await run_explain(session, q1_flags, {"project_id": project_id})
        print(f"1.1 Flags + Variations Join:")
        print(f"    Node Type:      {p1_flags['node_type']}")
        print(f"    Execution Time: {p1_flags['execution_time_ms']:.3f} ms")
        print(f"    Shared Hit:     {p1_flags['shared_hit_blocks']} blocks")

        q1_settings = """
            SELECT s.id, s.flag_id, s.enabled, s.default_variation_id, tr.id AS rule_id, tr.priority, tr.conditions
            FROM flag_environment_setting s
            LEFT JOIN targeting_rule tr ON tr.flag_environment_setting_id = s.id
            WHERE s.environment_id = :env_id
            ORDER BY tr.priority ASC
        """
        p1_settings = await run_explain(session, q1_settings, {"env_id": env_id})
        print(f"1.2 Settings + Targeting Rules Join:")
        print(f"    Node Type:      {p1_settings['node_type']}")
        print(f"    Execution Time: {p1_settings['execution_time_ms']:.3f} ms")
        print(f"    Shared Hit:     {p1_settings['shared_hit_blocks']} blocks")

        q1_overrides = """
            SELECT io.id, io.context_key, io.variation_id, io.flag_environment_setting_id
            FROM individual_override io
            JOIN flag_environment_setting fes ON fes.id = io.flag_environment_setting_id
            WHERE fes.environment_id = :env_id
        """
        p1_overrides = await run_explain(session, q1_overrides, {"env_id": env_id})
        print(f"1.3 Individual Overrides Query:")
        print(f"    Node Type:      {p1_overrides['node_type']}")
        print(f"    Execution Time: {p1_overrides['execution_time_ms']:.3f} ms")

        q1_segments = """
            SELECT id, key, conditions FROM segment WHERE project_id = :project_id
        """
        p1_segments = await run_explain(session, q1_segments, {"project_id": project_id})
        print(f"1.4 Segments Query:")
        print(f"    Node Type:      {p1_segments['node_type']}")
        print(f"    Execution Time: {p1_segments['execution_time_ms']:.3f} ms")

        q1_ruleset_ver = """
            SELECT ruleset_version FROM environment WHERE id = :env_id
        """
        p1_ver = await run_explain(session, q1_ruleset_ver, {"env_id": env_id})
        print(f"1.5 Environment ruleset_version Lookup (ETag / 304 Fast Path):")
        print(f"    Node Type:      {p1_ver['node_type']}")
        print(f"    Execution Time: {p1_ver['execution_time_ms']:.3f} ms")

        # ------------------------------------------------------------------
        # HOT PATH 2: API Key Lookup by key_hash
        # ------------------------------------------------------------------
        print("\n--- Hot Path 2: ApiKey Lookup by key_hash ---")
        q2_apikey = """
            SELECT ak.id, ak.key_prefix, ak.scope, ak.environment_id, ak.revoked_at, e.project_id
            FROM api_key ak
            JOIN environment e ON e.id = ak.environment_id
            WHERE ak.key_hash = :key_hash AND ak.revoked_at IS NULL
        """
        p2_apikey = await run_explain(session, q2_apikey, {"key_hash": key_hash})
        print(f"2.1 ApiKey Index Lookup:")
        print(f"    Node Type:      {p2_apikey['node_type']}")
        print(f"    Execution Time: {p2_apikey['execution_time_ms']:.3f} ms")
        print(f"    Shared Hit:     {p2_apikey['shared_hit_blocks']} blocks")

        # ------------------------------------------------------------------
        # HOT PATH 3: Config Release Snapshot Read
        # ------------------------------------------------------------------
        print("\n--- Hot Path 3: Config Release Snapshot Read ---")
        q3_rel = """
            SELECT id, namespace_id, version, snapshot, created_at
            FROM config_release
            WHERE id = :rel_id
        """
        p3_rel = await run_explain(session, q3_rel, {"rel_id": rel_id})
        print(f"3.1 ConfigRelease by ID (Direct Snapshot Read):")
        print(f"    Node Type:      {p3_rel['node_type']}")
        print(f"    Execution Time: {p3_rel['execution_time_ms']:.3f} ms")

        q3_latest = """
            SELECT id, namespace_id, version, snapshot, created_at
            FROM config_release
            WHERE namespace_id = :ns_id
            ORDER BY version DESC
            LIMIT 1
        """
        p3_latest = await run_explain(session, q3_latest, {"ns_id": ns_id})
        print(f"3.2 Latest ConfigRelease by Namespace:")
        print(f"    Node Type:      {p3_latest['node_type']}")
        print(f"    Execution Time: {p3_latest['execution_time_ms']:.3f} ms")

        # ------------------------------------------------------------------
        # N+1 Query Detector Check on load_ruleset_bundle
        # ------------------------------------------------------------------
        print("\n--- N+1 Query Verification: load_ruleset_bundle ---")
        query_counter = 0

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_counter
            query_counter += 1

        from sqlalchemy import event
        sync_engine = engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", count_queries)

        query_counter = 0
        t0 = time.perf_counter()
        ruleset, s_map, f_map = await load_ruleset_bundle(session, env, ApiKeyScope.SERVER)
        elapsed_bundle = (time.perf_counter() - t0) * 1000.0

        event.remove(sync_engine, "before_cursor_execute", count_queries)

        print(f"Flags Loaded:               {len(f_map)}")
        print(f"Total SQL Queries Emitted:  {query_counter} queries")
        print(f"Elapsed Bundle Load Time:   {elapsed_bundle:.2f} ms")
        is_consolidated = (query_counter == 4)
        print(f"Zero N+1 Check (Query count == 4): {'PASSED' if is_consolidated else 'FAILED'}")

        # ------------------------------------------------------------------
        # Connection Pool Configuration
        # ------------------------------------------------------------------
        print("\n--- Connection Pool Configuration ---")
        pool = engine.pool
        pool_status = {
            "pool_class": pool.__class__.__name__,
            "pool_size": getattr(pool, "size", lambda: None)(),
            "max_overflow": getattr(pool, "_max_overflow", None),
            "checked_in_connections": getattr(pool, "checkedin", lambda: None)(),
            "checked_out_connections": getattr(pool, "checkedout", lambda: None)(),
            "pool_pre_ping": engine.pool._pre_ping if hasattr(engine.pool, "_pre_ping") else True,
        }
        for k, v in pool_status.items():
            print(f"  {k:28s}: {v}")

        results = {
            "explain_analyze": {
                "ruleset_flags_variations": p1_flags,
                "ruleset_settings_rules": p1_settings,
                "ruleset_overrides": p1_overrides,
                "ruleset_segments": p1_segments,
                "ruleset_version_etag": p1_ver,
                "api_key_lookup": p2_apikey,
                "config_release_by_id": p3_rel,
                "config_release_latest": p3_latest,
            },
            "n_plus_1_verification": {
                "flags_loaded": len(f_map),
                "queries_executed": query_counter,
                "expected_queries": 4,
                "zero_n_plus_1_passed": is_consolidated,
                "bundle_load_ms": elapsed_bundle,
            },
            "connection_pool": pool_status,
        }

        out_dir = BASE_DIR / "load-tests" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "explain_hot_paths.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nSaved EXPLAIN ANALYZE results to {out_file}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
