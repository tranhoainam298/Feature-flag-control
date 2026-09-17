"""FlagOps Database Seed Script.

Idempotent seed script to initialize production-ready enterprise organization,
users, projects, environments, API keys, segments, flags, variations, targeting
rules, config namespaces, config items, releases, and audit logs.

Usage:
    python -m app.seed [--reset]
"""

import argparse
import asyncio
import hashlib
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.config import (
    ConfigFormat,
    ConfigItem,
    ConfigNamespace,
    ConfigRelease,
    ConfigValueType,
)
from app.models.enums import ApiKeyScope, FlagType, MemberRole, ToggleKind
from app.models.flag import Flag, FlagEnvironmentSetting, Segment, TargetingRule, Variation
from app.models.organization import Membership, Organization
from app.models.project import ApiKey, Environment, Project
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("flagops.seed")

# Deterministic API keys for demo and integration tests
DEMO_API_KEYS = {
    "dev": {
        "server": "fo_srv_dev_secret_key_demo_12345678",
        "client": "fo_cli_dev_client_key_demo_12345678",
    },
    "staging": {
        "server": "fo_srv_staging_secret_key_demo_123456",
        "client": "fo_cli_staging_client_key_demo_123456",
    },
    "prod": {
        "server": "fo_srv_prod_secret_key_demo_12345678",
        "client": "fo_cli_prod_client_key_demo_12345678",
    },
}

SEED_PASSWORD = "FlagOps@Secure2026!"

SEED_USERS = [
    {
        "email": "security.admin@flagops.internal",
        "full_name": "Security Administrator",
        "role": MemberRole.OWNER,
    },
    {
        "email": "lead.engineer@flagops.internal",
        "full_name": "Lead Infrastructure Engineer",
        "role": MemberRole.ADMIN,
    },
    {
        "email": "platform.dev@flagops.internal",
        "full_name": "Platform Core Developer",
        "role": MemberRole.DEVELOPER,
    },
    {
        "email": "compliance.auditor@flagops.internal",
        "full_name": "Compliance & Security Auditor",
        "role": MemberRole.VIEWER,
    },
]

DEMO_USERS = SEED_USERS


async def clean_seed_data(session: AsyncSession) -> None:
    """Clean existing seed data from the database."""
    logger.info("Cleaning existing seed data (--reset requested)...")

    # 1. Find organizations to clean
    org_slugs = ["global-core-infrastructure", "demo-org"]
    for slug in org_slugs:
        org = await session.scalar(select(Organization).where(Organization.slug == slug))
        if org:
            await session.execute(delete(AuditLog).where(AuditLog.organization_id == org.id))
            await session.delete(org)
            await session.flush()

    # 2. Delete users
    user_emails = [u["email"] for u in SEED_USERS] + [
        "owner@demo.local",
        "dev@demo.local",
        "viewer@demo.local",
    ]
    users_to_clean = (await session.scalars(select(User).where(User.email.in_(user_emails)))).all()
    user_ids = [u.id for u in users_to_clean]
    if user_ids:
        await session.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        for u in users_to_clean:
            await session.delete(u)
        await session.flush()

    await session.commit()
    logger.info("Seed data cleaned successfully.")


async def run_seed(reset: bool = False) -> dict[str, Any]:
    """Execute the database seed with full idempotency."""
    async with async_session_factory() as session:
        if reset:
            await clean_seed_data(session)

        # 1. Organization
        org = await session.scalar(
            select(Organization).where(Organization.slug == "global-core-infrastructure")
        )
        if not org:
            org = Organization(name="Global Core Infrastructure", slug="global-core-infrastructure")
            session.add(org)
            await session.flush()
            logger.info(
                "Created organization: Global Core Infrastructure (global-core-infrastructure)"
            )
        else:
            logger.info("Organization global-core-infrastructure already exists, keeping existing.")

        # 2. Users & Memberships
        users: dict[str, User] = {}
        for u_data in SEED_USERS:
            user = await session.scalar(select(User).where(User.email == u_data["email"]))
            if not user:
                user = User(
                    email=u_data["email"],
                    password_hash=hash_password(SEED_PASSWORD),
                    full_name=u_data["full_name"],
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                logger.info(f"Created user: {user.email}")
            users[u_data["email"]] = user

            # Membership
            membership = await session.scalar(
                select(Membership).where(
                    Membership.organization_id == org.id, Membership.user_id == user.id
                )
            )
            if not membership:
                membership = Membership(
                    organization_id=org.id,
                    user_id=user.id,
                    role=u_data["role"],
                )
                session.add(membership)
                await session.flush()

        admin_user = users["security.admin@flagops.internal"]

        # 3. Project
        project = await session.scalar(
            select(Project).where(
                Project.organization_id == org.id, Project.slug == "production-platform-gateway"
            )
        )
        if not project:
            project = Project(
                organization_id=org.id,
                name="Production Platform Gateway",
                slug="production-platform-gateway",
                default_stale_days=30,
            )
            session.add(project)
            await session.flush()
            logger.info(
                "Created project: Production Platform Gateway (production-platform-gateway)"
            )

        # 4. Environments (dev, staging, prod)
        envs: dict[str, Environment] = {}
        env_configs = [
            {"name": "Development", "key": "dev", "is_production": False},
            {"name": "Staging", "key": "staging", "is_production": False},
            {"name": "Production", "key": "prod", "is_production": True},
        ]
        for ec in env_configs:
            env = await session.scalar(
                select(Environment).where(
                    Environment.project_id == project.id, Environment.key == ec["key"]
                )
            )
            if not env:
                env = Environment(
                    project_id=project.id,
                    name=ec["name"],
                    key=ec["key"],
                    is_production=ec["is_production"],
                    ruleset_version=1,
                )
                session.add(env)
                await session.flush()
                logger.info(f"Created environment: {env.name} ({env.key})")
            envs[str(ec["key"])] = env

        # 5. API Keys (2 per environment = 6 total)
        for env_key, keys in DEMO_API_KEYS.items():
            env = envs[env_key]
            # Server key
            srv_raw = keys["server"]
            srv_hash = hashlib.sha256(srv_raw.encode()).hexdigest()
            srv_key = await session.scalar(select(ApiKey).where(ApiKey.key_hash == srv_hash))
            if not srv_key:
                srv_key = ApiKey(
                    environment_id=env.id,
                    name=f"{env.name} Server Key",
                    key_hash=srv_hash,
                    key_prefix=srv_raw[:12],
                    scope=ApiKeyScope.SERVER,
                )
                session.add(srv_key)

            # Client key
            cli_raw = keys["client"]
            cli_hash = hashlib.sha256(cli_raw.encode()).hexdigest()
            cli_key = await session.scalar(select(ApiKey).where(ApiKey.key_hash == cli_hash))
            if not cli_key:
                cli_key = ApiKey(
                    environment_id=env.id,
                    name=f"{env.name} Client Key",
                    key_hash=cli_hash,
                    key_prefix=cli_raw[:12],
                    scope=ApiKeyScope.CLIENT,
                )
                session.add(cli_key)
        await session.flush()
        logger.info("Created / verified 6 deterministic API keys.")

        # 6. Segments
        segments: dict[str, Segment] = {}
        segment_configs = [
            {
                "key": "vn-premium",
                "name": "Vietnam Premium Users",
                "description": "Users in Vietnam with a Premium subscription plan",
                "conditions": {
                    "operator": "AND",
                    "conditions": [
                        {"attribute": "country", "operator": "IN", "value": ["VN"]},
                        {"attribute": "plan", "operator": "EQ", "value": "premium"},
                    ],
                },
            },
            {
                "key": "early-adopters",
                "name": "Early Adopters",
                "description": "Beta testers or users registered before 2026",
                "conditions": {
                    "operator": "OR",
                    "conditions": [
                        {"attribute": "beta_tester", "operator": "EQ", "value": True},
                        {"attribute": "signup_date", "operator": "LTE", "value": "2026-01-01"},
                    ],
                },
            },
        ]
        for sc in segment_configs:
            seg = await session.scalar(
                select(Segment).where(Segment.project_id == project.id, Segment.key == sc["key"])
            )
            if not seg:
                seg = Segment(
                    project_id=project.id,
                    key=sc["key"],
                    name=sc["name"],
                    description=sc["description"],
                    conditions=sc["conditions"],
                )
                session.add(seg)
                await session.flush()
                logger.info(f"Created segment: {seg.name} ({seg.key})")
            segments[str(sc["key"])] = seg

        # 7. Flags & Variations
        async def get_or_create_flag(
            key: str,
            name: str,
            flag_type: FlagType,
            toggle_kind: ToggleKind,
            variations_data: list[dict[str, Any]],
            description: str | None = None,
            is_client_visible: bool = False,
        ) -> tuple[Flag, dict[str, Variation]]:
            f = await session.scalar(
                select(Flag).where(Flag.project_id == project.id, Flag.key == key)
            )
            if not f:
                f = Flag(
                    project_id=project.id,
                    key=key,
                    name=name,
                    description=description,
                    type=flag_type,
                    toggle_kind=toggle_kind,
                    is_temporary=True,
                    is_client_visible=is_client_visible,
                    created_by=admin_user.id,
                )
                session.add(f)
                await session.flush()
                logger.info(f"Created flag: {f.name} ({f.key})")

            var_map: dict[str, Variation] = {}
            for vd in variations_data:
                v = await session.scalar(
                    select(Variation).where(Variation.flag_id == f.id, Variation.key == vd["key"])
                )
                if not v:
                    v = Variation(
                        flag_id=f.id,
                        key=vd["key"],
                        value=vd["value"],
                        name=vd.get("name"),
                        description=vd.get("description"),
                    )
                    session.add(v)
                    await session.flush()
                var_map[vd["key"]] = v
            return f, var_map

        # Flag 1: checkout-instant-pay (Boolean, Release)
        flag_instant, vars_instant = await get_or_create_flag(
            key="checkout-instant-pay",
            name="Checkout Instant Pay Flow",
            flag_type=FlagType.BOOLEAN,
            toggle_kind=ToggleKind.RELEASE,
            variations_data=[
                {"key": "true", "value": True, "name": "Instant Pay Enabled"},
                {"key": "false", "value": False, "name": "Standard Pay Disabled"},
            ],
            description="Next-gen zero-friction instant payment checkout",
            is_client_visible=True,
        )

        # Flag 2: v3-pricing-engine (JSON, Experiment)
        flag_pricing, vars_pricing = await get_or_create_flag(
            key="v3-pricing-engine",
            name="V3 Dynamic Pricing Engine",
            flag_type=FlagType.JSON,
            toggle_kind=ToggleKind.EXPERIMENT,
            variations_data=[
                {
                    "key": "model_v3_balanced",
                    "value": {
                        "model": "xgboost_v3",
                        "margin": 0.15,
                        "surge": True,
                    },
                    "name": "Model V3 Balanced",
                },
                {
                    "key": "model_v2_legacy",
                    "value": {
                        "model": "rule_based",
                        "margin": 0.10,
                        "surge": False,
                    },
                    "name": "Model V2 Legacy",
                },
            ],
            description="Machine learning dynamic pricing optimization model",
            is_client_visible=False,
        )

        # Flag 3: dark-mode-theme (String, Release)
        flag_darkmode, vars_darkmode = await get_or_create_flag(
            key="dark-mode-theme",
            name="Dark Mode Theme Palette",
            flag_type=FlagType.STRING,
            toggle_kind=ToggleKind.RELEASE,
            variations_data=[
                {"key": "slate_dark", "value": "slate_dark", "name": "Slate Dark Theme"},
                {"key": "zinc_dark", "value": "zinc_dark", "name": "Zinc Dark Theme"},
                {"key": "light", "value": "light", "name": "Light Theme"},
            ],
            description="Enterprise UI high-contrast dark theme styling",
            is_client_visible=True,
        )

        # Flag 4: distributed-tracing-v2 (Boolean, Ops)
        flag_tracing, vars_tracing = await get_or_create_flag(
            key="distributed-tracing-v2",
            name="Distributed Tracing V2 (OpenTelemetry)",
            flag_type=FlagType.BOOLEAN,
            toggle_kind=ToggleKind.OPS,
            variations_data=[
                {"key": "true", "value": True, "name": "Tracing Enabled"},
                {"key": "false", "value": False, "name": "Tracing Disabled"},
            ],
            description="Distributed tracing sampling rate and APM spans",
            is_client_visible=False,
        )

        # Flag 5: checkout-v2 (Boolean, Release) — backward compatibility
        flag_checkout, vars_checkout = await get_or_create_flag(
            key="checkout-v2",
            name="Checkout V2 Flow",
            flag_type=FlagType.BOOLEAN,
            toggle_kind=ToggleKind.RELEASE,
            variations_data=[
                {"key": "true", "value": True, "name": "Checkout V2 (Enabled)"},
                {"key": "false", "value": False, "name": "Checkout Legacy (Disabled)"},
            ],
            description="Next-gen single-page checkout experience",
            is_client_visible=True,
        )

        # 8. Flag Environment Settings & Targeting Rules
        for env_key, env in envs.items():
            # Setting for checkout-instant-pay
            fes_instant = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_instant.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_instant:
                fes_instant = FlagEnvironmentSetting(
                    flag_id=flag_instant.id,
                    environment_id=env.id,
                    enabled=True,
                    default_variation_id=vars_instant["false"].id,
                    off_variation_id=vars_instant["false"].id,
                    bucketing_key="userId",
                )
                session.add(fes_instant)
                await session.flush()

                rule_instant = TargetingRule(
                    flag_environment_setting_id=fes_instant.id,
                    priority=1,
                    description="Country IN [VN] AND plan == premium -> ON",
                    conditions={
                        "operator": "AND",
                        "conditions": [
                            {"attribute": "country", "operator": "IN", "value": ["VN"]},
                            {"attribute": "plan", "operator": "EQ", "value": "premium"},
                        ],
                    },
                    distribution=[{"variation_id": str(vars_instant["true"].id), "weight": 100.0}],
                )
                session.add(rule_instant)

            # Setting for checkout-v2
            fes_checkout = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_checkout.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_checkout:
                fes_checkout = FlagEnvironmentSetting(
                    flag_id=flag_checkout.id,
                    environment_id=env.id,
                    enabled=True,
                    default_variation_id=vars_checkout["false"].id,
                    off_variation_id=vars_checkout["false"].id,
                    bucketing_key="userId",
                )
                session.add(fes_checkout)
                await session.flush()

                rule_checkout = TargetingRule(
                    flag_environment_setting_id=fes_checkout.id,
                    priority=1,
                    description="Country IN [VN] AND plan == premium -> ON",
                    conditions={
                        "operator": "AND",
                        "conditions": [
                            {"attribute": "country", "operator": "IN", "value": ["VN"]},
                            {"attribute": "plan", "operator": "EQ", "value": "premium"},
                        ],
                    },
                    distribution=[{"variation_id": str(vars_checkout["true"].id), "weight": 100.0}],
                )
                session.add(rule_checkout)

            # Setting for v3-pricing-engine
            fes_pricing = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_pricing.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_pricing:
                fes_pricing = FlagEnvironmentSetting(
                    flag_id=flag_pricing.id,
                    environment_id=env.id,
                    enabled=True,
                    default_variation_id=vars_pricing["model_v3_balanced"].id,
                    off_variation_id=vars_pricing["model_v2_legacy"].id,
                    bucketing_key="userId",
                )
                session.add(fes_pricing)

            # Setting for dark-mode-theme
            fes_dark = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_darkmode.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_dark:
                is_on = env_key in ("dev", "staging")
                fes_dark = FlagEnvironmentSetting(
                    flag_id=flag_darkmode.id,
                    environment_id=env.id,
                    enabled=is_on,
                    default_variation_id=vars_darkmode["slate_dark" if is_on else "light"].id,
                    off_variation_id=vars_darkmode["light"].id,
                    bucketing_key="userId",
                )
                session.add(fes_dark)

            # Setting for distributed-tracing-v2
            fes_trace = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_tracing.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_trace:
                is_trace = env_key in ("staging", "prod")
                fes_trace = FlagEnvironmentSetting(
                    flag_id=flag_tracing.id,
                    environment_id=env.id,
                    enabled=is_trace,
                    default_variation_id=vars_tracing["true" if is_trace else "false"].id,
                    off_variation_id=vars_tracing["false"].id,
                    bucketing_key="userId",
                )
                session.add(fes_trace)

        await session.flush()
        logger.info("Created / verified flag environment settings & targeting rules.")

        # 9. Config Namespaces & Config Items (dev environment)
        dev_env = envs["dev"]

        # Namespace 1: payment-service
        ns_payment = await session.scalar(
            select(ConfigNamespace).where(
                ConfigNamespace.environment_id == dev_env.id,
                ConfigNamespace.name == "payment-service",
            )
        )
        if not ns_payment:
            ns_payment = ConfigNamespace(
                environment_id=dev_env.id,
                name="payment-service",
                format=ConfigFormat.JSON,
            )
            session.add(ns_payment)
            await session.flush()

        # Namespace 2: application
        ns_app = await session.scalar(
            select(ConfigNamespace).where(
                ConfigNamespace.environment_id == dev_env.id,
                ConfigNamespace.name == "application",
            )
        )
        if not ns_app:
            ns_app = ConfigNamespace(
                environment_id=dev_env.id,
                name="application",
                format=ConfigFormat.JSON,
            )
            session.add(ns_app)
            await session.flush()

        # 6 Config items:
        config_items_data = [
            (ns_payment, "payment.timeout_ms", "3000", ConfigValueType.INT, False, None),
            (ns_payment, "payment.gateway", "stripe", ConfigValueType.STRING, False, None),
            (
                ns_payment,
                "payment.stripe_secret_key",
                encrypt_secret("sk_test_51MzDemoSecretKey987654321"),
                ConfigValueType.STRING,
                True,
                None,
            ),
            (ns_app, "app.maintenance_mode", "false", ConfigValueType.BOOL, False, None),
            (ns_app, "app.max_upload_mb", "50", ConfigValueType.INT, False, None),
            (ns_app, "app.rate_limit_per_min", "100", ConfigValueType.INT, False, None),
        ]
        for ns, key, val, vtype, is_sec, schema in config_items_data:
            item = await session.scalar(
                select(ConfigItem).where(ConfigItem.namespace_id == ns.id, ConfigItem.key == key)
            )
            if not item:
                item = ConfigItem(
                    namespace_id=ns.id,
                    key=key,
                    value=val,
                    value_type=vtype,
                    is_secret=is_sec,
                    json_schema=schema,
                )
                session.add(item)
        await session.flush()
        logger.info("Created / verified 6 config items.")

        # 10. Config Releases in payment-service
        dev_user = users["platform.dev@flagops.internal"]

        rel1 = await session.scalar(
            select(ConfigRelease).where(
                ConfigRelease.namespace_id == ns_payment.id, ConfigRelease.version == 1
            )
        )
        if not rel1:
            rel1 = ConfigRelease(
                namespace_id=ns_payment.id,
                version=1,
                snapshot={"payment.timeout_ms": 1000, "payment.gateway": "legacy"},
                comment="v1.0 Initial payment configuration",
                released_by=admin_user.id,
            )
            session.add(rel1)
            await session.flush()

        rel2 = await session.scalar(
            select(ConfigRelease).where(
                ConfigRelease.namespace_id == ns_payment.id, ConfigRelease.version == 2
            )
        )
        if not rel2:
            rel2 = ConfigRelease(
                namespace_id=ns_payment.id,
                version=2,
                snapshot={
                    "payment.timeout_ms": 5000,
                    "payment.gateway": "stripe",
                    "payment.stripe_secret_key": encrypt_secret("sk_test_old_key_555"),
                },
                comment="v1.1 Increased timeout to 5000ms and added Stripe",
                released_by=dev_user.id,
            )
            session.add(rel2)
            await session.flush()

        rel3 = await session.scalar(
            select(ConfigRelease).where(
                ConfigRelease.namespace_id == ns_payment.id, ConfigRelease.version == 3
            )
        )
        if not rel3:
            rel3 = ConfigRelease(
                namespace_id=ns_payment.id,
                version=3,
                snapshot={
                    "payment.timeout_ms": 3000,
                    "payment.gateway": "stripe",
                    "payment.stripe_secret_key": encrypt_secret(
                        "sk_test_51MzDemoSecretKey987654321"
                    ),
                },
                comment="v1.2 Rollback timeout to 3000ms and rotate secret",
                released_by=admin_user.id,
                is_rollback_of=rel1.id,
            )
            session.add(rel3)
            await session.flush()

        ns_payment.current_release_id = rel3.id

        # Application release v1
        app_rel1 = await session.scalar(
            select(ConfigRelease).where(
                ConfigRelease.namespace_id == ns_app.id, ConfigRelease.version == 1
            )
        )
        if not app_rel1:
            app_rel1 = ConfigRelease(
                namespace_id=ns_app.id,
                version=1,
                snapshot={
                    "app.maintenance_mode": False,
                    "app.max_upload_mb": 50,
                    "app.rate_limit_per_min": 100,
                },
                comment="v1.0 Production application baseline",
                released_by=admin_user.id,
            )
            session.add(app_rel1)
            await session.flush()
        ns_app.current_release_id = app_rel1.id

        await session.flush()
        logger.info("Created / verified 3 config releases in payment-service.")

        # 11. 20 Realistic Audit Logs
        current_audit_count = (
            await session.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.organization_id == org.id)
            )
            or 0
        )
        if current_audit_count < 20:
            base_time = datetime.now(timezone.utc) - timedelta(days=2)
            audit_events = [
                (
                    "USER_REGISTER",
                    "user",
                    admin_user.email,
                    None,
                    {"email": admin_user.email},
                ),
                (
                    "ORGANIZATION_CREATE",
                    "organization",
                    "global-core-infrastructure",
                    None,
                    {"name": "Global Core Infrastructure", "slug": "global-core-infrastructure"},
                ),
                (
                    "PROJECT_CREATE",
                    "project",
                    "production-platform-gateway",
                    None,
                    {"name": "Production Platform Gateway"},
                ),
                (
                    "USER_INVITE",
                    "membership",
                    dev_user.email,
                    None,
                    {"role": "DEVELOPER"},
                ),
                (
                    "USER_INVITE",
                    "membership",
                    users["compliance.auditor@flagops.internal"].email,
                    None,
                    {"role": "VIEWER"},
                ),
                (
                    "ENVIRONMENT_CREATE",
                    "environment",
                    "dev",
                    None,
                    {"key": "dev", "name": "Development"},
                ),
                (
                    "ENVIRONMENT_CREATE",
                    "environment",
                    "staging",
                    None,
                    {"key": "staging", "name": "Staging"},
                ),
                (
                    "ENVIRONMENT_CREATE",
                    "environment",
                    "prod",
                    None,
                    {"key": "prod", "name": "Production"},
                ),
                ("API_KEY_CREATE", "api_key", "Dev Server Key", None, {"scope": "SERVER"}),
                ("API_KEY_CREATE", "api_key", "Dev Client Key", None, {"scope": "CLIENT"}),
                (
                    "SEGMENT_CREATE",
                    "segment",
                    "vn-premium",
                    None,
                    {"name": "Vietnam Premium Users"},
                ),
                ("SEGMENT_CREATE", "segment", "early-adopters", None, {"name": "Early Adopters"}),
                (
                    "FLAG_CREATE",
                    "flag",
                    "checkout-instant-pay",
                    None,
                    {"key": "checkout-instant-pay", "type": "BOOLEAN"},
                ),
                (
                    "TARGETING_RULE_CREATE",
                    "targeting_rule",
                    "checkout-instant-pay",
                    None,
                    {"rule": "Country IN [VN]"},
                ),
                (
                    "FLAG_CREATE",
                    "flag",
                    "v3-pricing-engine",
                    None,
                    {"key": "v3-pricing-engine", "type": "JSON"},
                ),
                (
                    "FLAG_CREATE",
                    "flag",
                    "dark-mode-theme",
                    None,
                    {"key": "dark-mode-theme", "type": "STRING"},
                ),
                (
                    "FLAG_CREATE",
                    "flag",
                    "distributed-tracing-v2",
                    None,
                    {"key": "distributed-tracing-v2", "type": "BOOLEAN"},
                ),
                (
                    "CONFIG_NAMESPACE_CREATE",
                    "config_namespace",
                    "payment-service",
                    None,
                    {"format": "JSON"},
                ),
                (
                    "CONFIG_ITEM_UPDATE",
                    "config_item",
                    "payment.timeout_ms",
                    {"val": "1000"},
                    {"val": "3000"},
                ),
                (
                    "CONFIG_RELEASE_PUBLISH",
                    "config_release",
                    "payment-service:v3",
                    {"version": 2},
                    {"version": 3, "rollback_of": 1},
                ),
            ]

            for i, (action, entity_type, entity_id, before_data, after_data) in enumerate(
                audit_events
            ):
                log_time = base_time + timedelta(hours=i * 2)
                log_entry = AuditLog(
                    organization_id=org.id,
                    project_id=project.id,
                    environment_id=dev_env.id,
                    actor_id=admin_user.id if i % 2 == 0 else dev_user.id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    before=before_data,
                    after=after_data,
                    ip_address="127.0.0.1",
                    user_agent="FlagOps Seed Worker / 1.0",
                    created_at=log_time,
                )
                session.add(log_entry)
            await session.flush()
            logger.info("Created 20 realistic audit logs.")

        await session.commit()
        logger.info("Database seeding completed successfully and verified.")

        return {
            "organization": org.slug,
            "users": list(users.keys()),
            "project": project.slug,
            "environments": list(envs.keys()),
            "flags": [
                "checkout-instant-pay",
                "v3-pricing-engine",
                "dark-mode-theme",
                "distributed-tracing-v2",
                "checkout-v2",
            ],
            "segments": ["vn-premium", "early-adopters"],
            "namespaces": ["payment-service", "application"],
            "releases_count": 3,
        }


def main() -> None:
    """CLI entry point for seed execution."""
    parser = argparse.ArgumentParser(description="FlagOps Seed Data Tool")
    parser.add_argument(
        "--reset", action="store_true", help="Clean existing seed data before seeding"
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_seed(reset=args.reset))
        print("Done: FlagOps seed executed successfully.")
    except Exception as e:
        logger.exception("Error during database seed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
