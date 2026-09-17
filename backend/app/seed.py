"""FlagOps Database Seed Script.

Idempotent seed script to initialize demo organization, users, projects,
environments, API keys, segments, flags, variations, targeting rules,
config namespaces, config items, releases, and audit logs.

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

DEMO_USERS = [
    {"email": "owner@demo.local", "full_name": "Demo Owner", "role": MemberRole.OWNER},
    {"email": "dev@demo.local", "full_name": "Demo Developer", "role": MemberRole.DEVELOPER},
    {"email": "viewer@demo.local", "full_name": "Demo Viewer", "role": MemberRole.VIEWER},
]


async def clean_seed_data(session: AsyncSession) -> None:
    """Clean all demo data from the database."""
    logger.info("Cleaning existing demo data (--reset requested)...")

    # 1. Find demo org
    org = await session.scalar(select(Organization).where(Organization.slug == "demo-org"))
    if org:
        # Delete audit logs related to demo org
        await session.execute(delete(AuditLog).where(AuditLog.organization_id == org.id))
        # Delete org (cascades to project, environments, flags, variations, namespaces, etc.)
        await session.delete(org)
        await session.flush()

    # 2. Delete demo users
    user_emails = [u["email"] for u in DEMO_USERS]
    demo_users = (await session.scalars(select(User).where(User.email.in_(user_emails)))).all()
    user_ids = [u.id for u in demo_users]
    if user_ids:
        await session.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        for u in demo_users:
            await session.delete(u)
        await session.flush()

    await session.commit()
    logger.info("Demo data cleaned successfully.")


async def run_seed(reset: bool = False) -> dict[str, Any]:
    """Execute the database seed with full idempotency."""
    async with async_session_factory() as session:
        if reset:
            await clean_seed_data(session)

        # 1. Organization
        org = await session.scalar(select(Organization).where(Organization.slug == "demo-org"))
        if not org:
            org = Organization(name="Demo Organization", slug="demo-org")
            session.add(org)
            await session.flush()
            logger.info("Created organization: Demo Organization (demo-org)")
        else:
            logger.info("Organization demo-org already exists, keeping existing.")

        # 2. Users & Memberships
        users: dict[str, User] = {}
        for u_data in DEMO_USERS:
            user = await session.scalar(select(User).where(User.email == u_data["email"]))
            if not user:
                user = User(
                    email=u_data["email"],
                    password_hash=hash_password("demo1234"),
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

        # 3. Project
        project = await session.scalar(
            select(Project).where(Project.organization_id == org.id, Project.slug == "demo-project")
        )
        if not project:
            project = Project(
                organization_id=org.id,
                name="Demo Project",
                slug="demo-project",
                default_stale_days=30,
            )
            session.add(project)
            await session.flush()
            logger.info("Created project: Demo Project (demo-project)")

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
                    created_by=users["owner@demo.local"].id,
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

        # Flag 1: checkout-v2 (boolean, country IN [VN] AND plan == premium -> on)
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

        # Flag 2: new-homepage (boolean, 20/80 rollout)
        flag_homepage, vars_homepage = await get_or_create_flag(
            key="new-homepage",
            name="New Homepage Redesign",
            flag_type=FlagType.BOOLEAN,
            toggle_kind=ToggleKind.EXPERIMENT,
            variations_data=[
                {"key": "true", "value": True, "name": "New Modern Layout"},
                {"key": "false", "value": False, "name": "Classic Layout"},
            ],
            description="Redesigned high-converting homepage",
            is_client_visible=True,
        )

        # Flag 3: dark-mode (boolean, 100% in dev, off in prod)
        flag_darkmode, vars_darkmode = await get_or_create_flag(
            key="dark-mode",
            name="Dark Mode Theme",
            flag_type=FlagType.BOOLEAN,
            toggle_kind=ToggleKind.RELEASE,
            variations_data=[
                {"key": "true", "value": True, "name": "Dark Theme Enabled"},
                {"key": "false", "value": False, "name": "Light Theme Default"},
            ],
            description="System-wide dark mode theme support",
            is_client_visible=True,
        )

        # Flag 4: payment-v2 (multivariate 34/33/33)
        flag_payment, vars_payment = await get_or_create_flag(
            key="payment-v2",
            name="Payment Gateway V2",
            flag_type=FlagType.STRING,
            toggle_kind=ToggleKind.EXPERIMENT,
            variations_data=[
                {"key": "control", "value": "control", "name": "Control (Legacy Stripe)"},
                {"key": "variant_a", "value": "variant_a", "name": "Variant A (Stripe Elements)"},
                {"key": "variant_b", "value": "variant_b", "name": "Variant B (Adyen Drop-in)"},
            ],
            description="A/B/n test for multiple payment gateways",
            is_client_visible=False,
        )

        # Flag 5: recommendation-engine (JSON config flag)
        flag_recs, vars_recs = await get_or_create_flag(
            key="recommendation-engine",
            name="Recommendation Engine Config",
            flag_type=FlagType.JSON,
            toggle_kind=ToggleKind.OPS,
            variations_data=[
                {
                    "key": "v1_collaborative",
                    "value": {
                        "algorithm": "collaborative",
                        "max_items": 10,
                        "cache_ttl_sec": 300,
                        "fallback": "trending",
                    },
                    "name": "Collaborative Filtering v1",
                },
                {
                    "key": "v2_deep_rank",
                    "value": {
                        "algorithm": "deep_rank",
                        "max_items": 20,
                        "cache_ttl_sec": 60,
                        "fallback": "trending",
                    },
                    "name": "Deep Ranking Neural Model v2",
                },
            ],
            description="Runtime configuration object for machine-learning recommendations",
            is_client_visible=False,
        )

        # 8. Flag Environment Settings & Targeting Rules
        for env_key, env in envs.items():
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

            # Setting for new-homepage (rollout 20/80)
            fes_homepage = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_homepage.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_homepage:
                fes_homepage = FlagEnvironmentSetting(
                    flag_id=flag_homepage.id,
                    environment_id=env.id,
                    enabled=True,
                    default_variation_id=vars_homepage["false"].id,
                    off_variation_id=vars_homepage["false"].id,
                    bucketing_key="userId",
                )
                session.add(fes_homepage)
                await session.flush()

                rule_homepage = TargetingRule(
                    flag_environment_setting_id=fes_homepage.id,
                    priority=1,
                    description="20/80 Percentage Rollout",
                    conditions=None,
                    distribution=[
                        {"variation_id": str(vars_homepage["true"].id), "weight": 20.0},
                        {"variation_id": str(vars_homepage["false"].id), "weight": 80.0},
                    ],
                )
                session.add(rule_homepage)

            # Setting for dark-mode: 100% on in dev, off in prod
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
                    default_variation_id=vars_darkmode["true" if is_on else "false"].id,
                    off_variation_id=vars_darkmode["false"].id,
                    bucketing_key="userId",
                )
                session.add(fes_dark)

            # Setting for payment-v2: 34/33/33 split
            fes_pay = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_payment.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_pay:
                fes_pay = FlagEnvironmentSetting(
                    flag_id=flag_payment.id,
                    environment_id=env.id,
                    enabled=True,
                    default_variation_id=vars_payment["control"].id,
                    off_variation_id=vars_payment["control"].id,
                    bucketing_key="userId",
                )
                session.add(fes_pay)
                await session.flush()

                rule_pay = TargetingRule(
                    flag_environment_setting_id=fes_pay.id,
                    priority=1,
                    description="Multivariate 34/33/33 Split",
                    conditions=None,
                    distribution=[
                        {"variation_id": str(vars_payment["control"].id), "weight": 34.0},
                        {"variation_id": str(vars_payment["variant_a"].id), "weight": 33.0},
                        {"variation_id": str(vars_payment["variant_b"].id), "weight": 33.0},
                    ],
                )
                session.add(rule_pay)

            # Setting for recommendation-engine
            fes_recs = await session.scalar(
                select(FlagEnvironmentSetting).where(
                    FlagEnvironmentSetting.flag_id == flag_recs.id,
                    FlagEnvironmentSetting.environment_id == env.id,
                )
            )
            if not fes_recs:
                fes_recs = FlagEnvironmentSetting(
                    flag_id=flag_recs.id,
                    environment_id=env.id,
                    enabled=True,
                    default_variation_id=vars_recs["v1_collaborative"].id,
                    off_variation_id=vars_recs["v1_collaborative"].id,
                    bucketing_key="userId",
                )
                session.add(fes_recs)

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
        # In payment-service:
        # 1. payment.timeout_ms = 3000 (INT)
        # 2. payment.stripe_secret_key (STRING, is_secret=True)
        # 3. payment.gateway = "stripe" (STRING)
        # In application:
        # 4. app.maintenance_mode = "false" (BOOL)
        # 5. app.max_upload_mb = "50" (INT)
        # 6. app.rate_limit_per_min = "100" (INT)
        config_items_spec = [
            (
                ns_payment.id,
                "payment.timeout_ms",
                "3000",
                ConfigValueType.INT,
                False,
                "Payment gateway request timeout in milliseconds",
            ),
            (
                ns_payment.id,
                "payment.stripe_secret_key",
                encrypt_secret("sk_test_51MzDemoSecretKey987654321"),
                ConfigValueType.STRING,
                True,
                "Live Stripe API secret key (AES-256 encrypted)",
            ),
            (
                ns_payment.id,
                "payment.gateway",
                "stripe",
                ConfigValueType.STRING,
                False,
                "Default active payment gateway provider",
            ),
            (
                ns_app.id,
                "app.maintenance_mode",
                "false",
                ConfigValueType.BOOL,
                False,
                "Toggle global maintenance mode status",
            ),
            (
                ns_app.id,
                "app.max_upload_mb",
                "50",
                ConfigValueType.INT,
                False,
                "Maximum file upload size allowed in megabytes",
            ),
            (
                ns_app.id,
                "app.rate_limit_per_min",
                "100",
                ConfigValueType.INT,
                False,
                "API rate limit request threshold per minute",
            ),
        ]

        for ns_id, key, val, val_type, is_sec, cmt in config_items_spec:
            ci = await session.scalar(
                select(ConfigItem).where(ConfigItem.namespace_id == ns_id, ConfigItem.key == key)
            )
            if not ci:
                ci = ConfigItem(
                    namespace_id=ns_id,
                    key=key,
                    value=val,
                    value_type=val_type,
                    is_secret=is_sec,
                    comment=cmt,
                )
                session.add(ci)

        await session.flush()
        logger.info("Created / verified 6 config items across namespaces.")

        # 10. Config Releases (3 releases in payment-service with rollback history)
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
                released_by=users["owner@demo.local"].id,
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
                released_by=users["dev@demo.local"].id,
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
                released_by=users["owner@demo.local"].id,
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
                released_by=users["owner@demo.local"].id,
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
                    users["owner@demo.local"].email,
                    None,
                    {"email": users["owner@demo.local"].email},
                ),
                (
                    "ORGANIZATION_CREATE",
                    "organization",
                    "demo-org",
                    None,
                    {"name": "Demo Organization", "slug": "demo-org"},
                ),
                ("PROJECT_CREATE", "project", "demo-project", None, {"name": "Demo Project"}),
                (
                    "USER_INVITE",
                    "membership",
                    users["dev@demo.local"].email,
                    None,
                    {"role": "DEVELOPER"},
                ),
                (
                    "USER_INVITE",
                    "membership",
                    users["viewer@demo.local"].email,
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
                    "checkout-v2",
                    None,
                    {"key": "checkout-v2", "type": "BOOLEAN"},
                ),
                (
                    "TARGETING_RULE_CREATE",
                    "targeting_rule",
                    "checkout-v2",
                    None,
                    {"rule": "Country IN [VN]"},
                ),
                (
                    "FLAG_CREATE",
                    "flag",
                    "new-homepage",
                    None,
                    {"key": "new-homepage", "rollout": "20/80"},
                ),
                ("FLAG_CREATE", "flag", "dark-mode", None, {"key": "dark-mode", "dev_on": True}),
                (
                    "FLAG_CREATE",
                    "flag",
                    "payment-v2",
                    None,
                    {"key": "payment-v2", "type": "STRING"},
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
                    actor_id=users["owner@demo.local"].id
                    if i % 2 == 0
                    else users["dev@demo.local"].id,
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
                "checkout-v2",
                "new-homepage",
                "dark-mode",
                "payment-v2",
                "recommendation-engine",
            ],
            "segments": ["vn-premium", "early-adopters"],
            "namespaces": ["payment-service", "application"],
            "releases_count": 3,
        }


def main() -> None:
    """CLI entry point for seed execution."""
    parser = argparse.ArgumentParser(description="FlagOps Seed Data Tool")
    parser.add_argument(
        "--reset", action="store_true", help="Clean existing demo data before seeding"
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
