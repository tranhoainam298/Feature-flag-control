import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import (
    ApiKey,
    ApiKeyScope,
    AuditLog,
    ChangeRequest,
    ChangeRequestStatus,
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
    ToggleKind,
    User,
    Variation,
)

# Use NullPool for integration tests to prevent connection sharing across asyncio event loops
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as s:
        yield s
        await s.rollback()


@pytest.mark.asyncio
async def test_full_entity_creation_chain(session: AsyncSession) -> None:
    # 1. Organization
    org_slug = f"org-{uuid.uuid4().hex[:8]}"
    org = Organization(name="Test Org", slug=org_slug)
    session.add(org)
    await session.flush()
    assert org.id is not None

    # 2. User
    user_email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=user_email,
        password_hash="argon2id$mockhash",
        full_name="Nguyen Van A",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    # 3. Membership
    member = Membership(user_id=user.id, organization_id=org.id, role=MemberRole.OWNER)
    session.add(member)
    await session.flush()

    # 4. Project
    proj_slug = f"proj-{uuid.uuid4().hex[:8]}"
    project = Project(
        organization_id=org.id,
        name="Checkout Service",
        slug=proj_slug,
        default_stale_days=30,
    )
    session.add(project)
    await session.flush()

    # 5. Environment
    env = Environment(
        project_id=project.id,
        name="Production",
        key="production",
        is_production=True,
        ruleset_version=0,
    )
    session.add(env)
    await session.flush()
    assert env.ruleset_version == 0

    # 6. ApiKey
    api_key = ApiKey(
        environment_id=env.id,
        name="Server SDK Key",
        key_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        key_prefix="fo_srv_a1b2",
        scope=ApiKeyScope.SERVER,
    )
    session.add(api_key)
    await session.flush()

    # 7. Flag
    flag = Flag(
        project_id=project.id,
        key="checkout-v2",
        name="New Checkout Flow",
        description="Enable multi-step checkout",
        type=FlagType.BOOLEAN,
        toggle_kind=ToggleKind.RELEASE,
        is_temporary=True,
        is_client_visible=False,
        tags=["payment", "v2"],
        created_by=user.id,
    )
    session.add(flag)
    await session.flush()

    # 8. Variation
    var_on = Variation(flag_id=flag.id, key="on", value=True, name="True")
    var_off = Variation(flag_id=flag.id, key="off", value=False, name="False")
    session.add_all([var_on, var_off])
    await session.flush()

    # 9. FlagEnvironmentSetting
    setting = FlagEnvironmentSetting(
        flag_id=flag.id,
        environment_id=env.id,
        enabled=True,
        default_variation_id=var_on.id,
        off_variation_id=var_off.id,
        bucketing_key="userId",
    )
    session.add(setting)
    await session.flush()

    # 10. Segment
    segment = Segment(
        project_id=project.id,
        key="beta-users",
        name="Beta Users",
        conditions={
            "op": "AND",
            "children": [{"attribute": "beta", "operator": "EQ", "value": True}],
        },
    )
    session.add(segment)
    await session.flush()

    # 11. TargetingRule
    rule = TargetingRule(
        flag_environment_setting_id=setting.id,
        priority=1,
        description="Beta users get 100% on",
        segment_id=segment.id,
        distribution=[{"variation_id": str(var_on.id), "weight": 100}],
    )
    session.add(rule)
    await session.flush()

    # 12. IndividualOverride
    override = IndividualOverride(
        flag_environment_setting_id=setting.id,
        context_key="user-vip-999",
        variation_id=var_on.id,
    )
    session.add(override)
    await session.flush()

    # 13. ConfigNamespace
    ns = ConfigNamespace(
        environment_id=env.id,
        name="application",
        format=ConfigFormat.JSON,
    )
    session.add(ns)
    await session.flush()

    # 14. ConfigItem
    item = ConfigItem(
        namespace_id=ns.id,
        key="payment.timeout_ms",
        value="5000",
        value_type=ConfigValueType.INT,
        is_secret=False,
    )
    session.add(item)
    await session.flush()

    # 15. ConfigRelease
    release = ConfigRelease(
        namespace_id=ns.id,
        version=1,
        snapshot={"payment.timeout_ms": 5000, "payment.retry": 3},
        comment="Initial release",
        released_by=user.id,
    )
    session.add(release)
    await session.flush()
    ns.current_release_id = release.id
    await session.flush()

    # 16. AuditLog
    audit = AuditLog(
        organization_id=org.id,
        project_id=project.id,
        environment_id=env.id,
        actor_id=user.id,
        action="flag.created",
        entity_type="flag",
        entity_id=str(flag.id),
        before=None,
        after={"key": flag.key, "type": flag.type.value},
    )
    session.add(audit)
    await session.flush()

    # 17. ChangeRequest
    cr = ChangeRequest(
        environment_id=env.id,
        title="Rollout checkout v2 to 50%",
        payload={"rules": [{"priority": 1, "distribution": [{"variation": "on", "weight": 50}]}]},
        status=ChangeRequestStatus.PENDING,
        requested_by=user.id,
    )
    session.add(cr)
    await session.flush()

    # Verify query back
    q_flag = await session.scalar(select(Flag).where(Flag.id == flag.id))
    assert q_flag is not None
    assert q_flag.key == "checkout-v2"
    assert q_flag.type == FlagType.BOOLEAN

    q_env = await session.scalar(select(Environment).where(Environment.id == env.id))
    assert q_env is not None
    assert q_env.ruleset_version == 0


@pytest.mark.asyncio
async def test_flag_unique_project_id_key(session: AsyncSession) -> None:
    org = Organization(name="Org Unique", slug=f"org-u-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    proj = Project(organization_id=org.id, name="Proj", slug=f"proj-u-{uuid.uuid4().hex[:8]}")
    session.add(proj)
    await session.flush()

    f1 = Flag(
        project_id=proj.id,
        key="unique-flag-key",
        name="F1",
        type=FlagType.BOOLEAN,
    )
    session.add(f1)
    await session.flush()

    f2 = Flag(
        project_id=proj.id,
        key="unique-flag-key",
        name="F2",
        type=FlagType.BOOLEAN,
    )
    session.add(f2)

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_project_cascade_delete_flags(session: AsyncSession) -> None:
    org = Organization(name="Org Cascade", slug=f"org-c-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    proj = Project(organization_id=org.id, name="Proj C", slug=f"proj-c-{uuid.uuid4().hex[:8]}")
    session.add(proj)
    await session.flush()

    flag = Flag(
        project_id=proj.id,
        key="cascade-flag",
        name="Cascade Flag",
        type=FlagType.BOOLEAN,
    )
    session.add(flag)
    await session.flush()

    flag_id = flag.id
    await session.delete(proj)
    await session.flush()

    q_flag = await session.scalar(select(Flag).where(Flag.id == flag_id))
    assert q_flag is None


@pytest.mark.asyncio
async def test_jsonb_nested_three_levels(session: AsyncSession) -> None:
    org = Organization(name="Org JSONB", slug=f"org-j-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    proj = Project(organization_id=org.id, name="Proj J", slug=f"proj-j-{uuid.uuid4().hex[:8]}")
    session.add(proj)
    await session.flush()

    three_level_conditions = {
        "op": "AND",
        "children": [
            {"attribute": "country", "operator": "IN", "value": ["VN", "TH"]},
            {
                "op": "OR",
                "children": [
                    {"attribute": "plan", "operator": "EQ", "value": "premium"},
                    {"attribute": "appVersion", "operator": "SEMVER_GTE", "value": "3.2.0"},
                ],
            },
        ],
    }

    segment = Segment(
        project_id=proj.id,
        key="nested-segment",
        name="Nested Segment",
        conditions=three_level_conditions,
    )
    session.add(segment)
    await session.flush()

    q_seg = await session.scalar(select(Segment).where(Segment.id == segment.id))
    assert q_seg is not None
    assert q_seg.conditions == three_level_conditions
    assert q_seg.conditions["children"][1]["children"][0]["value"] == "premium"


@pytest.mark.asyncio
async def test_flag_key_regex_check_constraint(session: AsyncSession) -> None:
    org = Organization(name="Org Regex", slug=f"org-r-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()

    proj = Project(organization_id=org.id, name="Proj R", slug=f"proj-r-{uuid.uuid4().hex[:8]}")
    session.add(proj)
    await session.flush()

    # Invalid key with spaces and special character
    invalid_flag = Flag(
        project_id=proj.id,
        key="invalid flag key with spaces!",
        name="Invalid Key Flag",
        type=FlagType.BOOLEAN,
    )
    session.add(invalid_flag)

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
