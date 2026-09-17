"""Unit and integration tests for FlagOps database seed script."""

import pytest
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.models.audit import AuditLog
from app.models.config import ConfigItem, ConfigNamespace, ConfigRelease
from app.models.flag import Flag, FlagEnvironmentSetting, Segment, TargetingRule, Variation
from app.models.organization import Membership, Organization
from app.models.project import ApiKey, Environment, Project
from app.models.user import User
from app.seed import DEMO_USERS, run_seed


@pytest.mark.asyncio
async def test_seed_execution_and_verification():
    """Test run_seed(reset=True) populates all required entities correctly."""
    result = await run_seed(reset=True)
    assert result["organization"] == "global-core-infrastructure"
    assert len(result["users"]) == 4
    assert len(result["environments"]) == 3
    assert len(result["flags"]) == 5
    assert len(result["segments"]) == 2
    assert len(result["namespaces"]) == 2

    async with async_session_factory() as session:
        # 1. Organization
        org = await session.scalar(
            select(Organization).where(Organization.slug == "global-core-infrastructure")
        )
        assert org is not None
        assert org.name == "Global Core Infrastructure"

        # 2. Users & Memberships
        for u in DEMO_USERS:
            user = await session.scalar(select(User).where(User.email == u["email"]))
            assert user is not None
            mem = await session.scalar(
                select(Membership).where(
                    Membership.organization_id == org.id, Membership.user_id == user.id
                )
            )
            assert mem is not None
            assert mem.role == u["role"]

        # 3. Project & Environments
        proj = await session.scalar(
            select(Project).where(
                Project.organization_id == org.id, Project.slug == "production-platform-gateway"
            )
        )
        assert proj is not None

        envs = (
            await session.scalars(select(Environment).where(Environment.project_id == proj.id))
        ).all()
        assert len(envs) == 3
        env_map = {e.key: e for e in envs}
        assert "dev" in env_map
        assert "staging" in env_map
        assert "prod" in env_map
        assert env_map["prod"].is_production is True
        assert env_map["dev"].is_production is False

        # 4. API Keys (2 per env = 6 total)
        for env_key in ("dev", "staging", "prod"):
            env = env_map[env_key]
            keys = (
                await session.scalars(select(ApiKey).where(ApiKey.environment_id == env.id))
            ).all()
            assert len(keys) == 2
            scopes = {k.scope.value for k in keys}
            assert scopes == {"SERVER", "CLIENT"}

        # 5. Segments (2 total)
        segments = (
            await session.scalars(select(Segment).where(Segment.project_id == proj.id))
        ).all()
        assert len(segments) == 2
        seg_keys = {s.key for s in segments}
        assert seg_keys == {"vn-premium", "early-adopters"}

        # 6. Flags (5 total)
        flags = (await session.scalars(select(Flag).where(Flag.project_id == proj.id))).all()
        assert len(flags) == 5
        flag_map = {f.key: f for f in flags}
        assert "checkout-instant-pay" in flag_map
        assert "v3-pricing-engine" in flag_map
        assert "dark-mode-theme" in flag_map
        assert "distributed-tracing-v2" in flag_map
        assert "checkout-v2" in flag_map

        # Check flag variations
        f_checkout = flag_map["checkout-v2"]
        vars_checkout = (
            await session.scalars(select(Variation).where(Variation.flag_id == f_checkout.id))
        ).all()
        assert len(vars_checkout) == 2

        f_dark = flag_map["dark-mode-theme"]
        vars_dark = (
            await session.scalars(select(Variation).where(Variation.flag_id == f_dark.id))
        ).all()
        assert len(vars_dark) == 3

        # Check rules for checkout-v2
        dev_env = env_map["dev"]
        fes_checkout = await session.scalar(
            select(FlagEnvironmentSetting).where(
                FlagEnvironmentSetting.flag_id == f_checkout.id,
                FlagEnvironmentSetting.environment_id == dev_env.id,
            )
        )
        assert fes_checkout is not None
        rules_checkout = (
            await session.scalars(
                select(TargetingRule).where(
                    TargetingRule.flag_environment_setting_id == fes_checkout.id
                )
            )
        ).all()
        assert len(rules_checkout) >= 1

        # 7. Config Namespaces & Items
        namespaces = (
            await session.scalars(
                select(ConfigNamespace).where(ConfigNamespace.environment_id == dev_env.id)
            )
        ).all()
        assert len(namespaces) == 2
        ns_map = {n.name: n for n in namespaces}
        assert "payment-service" in ns_map
        assert "application" in ns_map

        ns_pay = ns_map["payment-service"]
        items_pay = (
            await session.scalars(select(ConfigItem).where(ConfigItem.namespace_id == ns_pay.id))
        ).all()
        assert len(items_pay) == 3
        item_keys = {i.key: i for i in items_pay}
        assert "payment.timeout_ms" in item_keys
        assert item_keys["payment.timeout_ms"].value == "3000"
        assert "payment.stripe_secret_key" in item_keys
        assert item_keys["payment.stripe_secret_key"].is_secret is True

        # Releases in payment-service
        releases_pay = (
            await session.scalars(
                select(ConfigRelease).where(ConfigRelease.namespace_id == ns_pay.id)
            )
        ).all()
        assert len(releases_pay) == 3
        assert ns_pay.current_release_id is not None

        # 8. Audit Logs (at least 20)
        audit_count = await session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.organization_id == org.id)
        )
        assert audit_count >= 20


@pytest.mark.asyncio
async def test_seed_idempotence():
    """Running seed twice in a row without --reset must NOT duplicate records."""
    await run_seed(reset=False)

    async with async_session_factory() as session:
        org_count = await session.scalar(
            select(func.count()).select_from(Organization).where(Organization.slug == "global-core-infrastructure")
        )
        user_count = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email.in_([u["email"] for u in DEMO_USERS]))
        )
        flag_count = await session.scalar(select(func.count()).select_from(Flag))
        ci_count = await session.scalar(select(func.count()).select_from(ConfigItem))
        rel_count = await session.scalar(select(func.count()).select_from(ConfigRelease))

    # Run seed a 2nd time without reset
    await run_seed(reset=False)

    async with async_session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Organization)
                .where(Organization.slug == "global-core-infrastructure")
            )
            == org_count
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.email.in_([u["email"] for u in DEMO_USERS]))
            )
            == user_count
        )
        assert await session.scalar(select(func.count()).select_from(Flag)) == flag_count
        assert await session.scalar(select(func.count()).select_from(ConfigItem)) == ci_count
        assert await session.scalar(select(func.count()).select_from(ConfigRelease)) == rel_count
