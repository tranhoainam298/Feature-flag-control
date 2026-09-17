"""Unit tests for FlagOps service layer.

Covers direct service method invocations:
- config_service.py: Schema validation, draft updates, release publish, diff, rollback, secret decryption.
- flag_debt.py: calculate_debt_score 4-vector breakdown, lifecycle state derivation, recommendations.
- change_request.py: State machine transitions, four-eyes self-approval check, scheduled execution.
- targeting.py: Condition tree depth limits, cyclic segment references, atomic rule replacements, rollback on error.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import MASKED_SECRET, encrypt_secret
from app.core.exceptions import FlagOpsError
from app.models.change_request import ChangeRequest
from app.models.config import ConfigItem, ConfigNamespace, ConfigRelease
from app.models.enums import (
    ApiKeyScope,
    ChangeRequestStatus,
    ConfigFormat,
    ConfigValueType,
    FlagType,
    LifecycleState,
    MemberRole,
)
from app.models.flag import (
    Flag,
    FlagEnvironmentSetting,
    Segment,
    TargetingRule,
    Variation,
)
from app.models.evaluation import EvaluationEvent
from app.models.organization import Organization
from app.models.project import Environment, Project
from app.models.user import User
from app.schemas.config import (
    ConfigItemInput,
    ConfigNamespaceCreate,
    ConfigReleaseCreate,
)
from app.schemas.segment import SegmentCreate, SegmentUpdate
from app.schemas.targeting import (
    DistributionItem,
    IndividualOverrideCreate,
    TargetingRuleCreate,
    TargetingRulesUpdate,
)
from app.services import config_service, targeting
from app.services.change_request import change_request_service
from app.services.config_service import (
    _parse_item_value,
    validate_item_schema,
)
from app.core.database import async_session_factory
from app.services.flag_debt import (
    DebtWeights,
    FlagSnapshot,
    calculate_debt_score,
    derive_lifecycle_state,
    get_recommendations,
)
from app.services import auth as auth_service
from app.services import flag_health as flag_health_svc
from app.services.tenancy import tenancy_service
from app.services.flag import flag_service, bump_ruleset_version, create_audit_log
from app.services import eval as eval_service
from app.schemas.auth import RegisterRequest
from app.schemas.organization import OrgCreate, OrgUpdate, MemberCreate, MemberUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.environment import EnvironmentCreate, EnvironmentUpdate
from app.schemas.api_key import ApiKeyCreate
from app.schemas.flag import FlagCreate, FlagUpdate, FlagSettingUpdate
import uuid


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def test_org(db_session: AsyncSession) -> Organization:
    org = Organization(name="Service Test Org", slug=f"svc-org-{uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.fixture
async def test_project(db_session: AsyncSession, test_org: Organization) -> Project:
    project = Project(
        organization_id=test_org.id,
        name="Service Test Project",
        slug=f"svc-proj-{uuid4().hex[:8]}",
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"svc-test-{uuid4().hex[:8]}@flagops.internal",
        password_hash="secure-hashed-password",
        full_name="Service Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ============================================================================
# 1. CONFIG SERVICE TESTS
# ============================================================================


class TestConfigServiceParsingAndSchema:
    def test_parse_item_value_types(self):
        assert _parse_item_value("42", ConfigValueType.INT) == 42
        assert _parse_item_value("3.14", ConfigValueType.FLOAT) == 3.14
        assert _parse_item_value("true", ConfigValueType.BOOL) is True
        assert _parse_item_value("1", ConfigValueType.BOOL) is True
        assert _parse_item_value("false", ConfigValueType.BOOL) is False
        assert _parse_item_value("0", ConfigValueType.BOOL) is False
        assert _parse_item_value('{"k": "v"}', ConfigValueType.JSON) == {"k": "v"}
        assert _parse_item_value("hello", ConfigValueType.STRING) == "hello"

        with pytest.raises(ValueError):
            _parse_item_value("not-a-bool", ConfigValueType.BOOL)

    def test_validate_item_schema_no_schema(self):
        item = ConfigItem(
            namespace_id=uuid4(),
            key="api_url",
            value="https://example.com",
            value_type=ConfigValueType.STRING,
            json_schema=None,
        )
        assert validate_item_schema(item) is None

    def test_validate_item_schema_success(self):
        schema = {
            "type": "object",
            "properties": {"timeout": {"type": "integer", "minimum": 1}},
            "required": ["timeout"],
        }
        item = ConfigItem(
            namespace_id=uuid4(),
            key="db_settings",
            value='{"timeout": 30}',
            value_type=ConfigValueType.JSON,
            json_schema=schema,
        )
        assert validate_item_schema(item) is None

    def test_validate_item_schema_failure(self):
        schema = {
            "type": "object",
            "properties": {"timeout": {"type": "integer", "minimum": 10}},
            "required": ["timeout"],
        }
        item = ConfigItem(
            namespace_id=uuid4(),
            key="db_settings",
            value='{"timeout": 2}',
            value_type=ConfigValueType.JSON,
            json_schema=schema,
        )
        err = validate_item_schema(item)
        assert err is not None
        assert "2 is less than the minimum of 10" in err

    def test_validate_item_schema_invalid_schema_definition(self):
        invalid_schema = {"type": "invalid_type_here"}
        item = ConfigItem(
            namespace_id=uuid4(),
            key="test",
            value="val",
            value_type=ConfigValueType.STRING,
            json_schema=invalid_schema,
        )
        err = validate_item_schema(item)
        assert err is not None
        assert "Invalid JSON schema definition" in err

    def test_validate_item_schema_unparseable_value(self):
        schema = {"type": "integer"}
        item = ConfigItem(
            namespace_id=uuid4(),
            key="port",
            value="not-an-int",
            value_type=ConfigValueType.INT,
            json_schema=schema,
        )
        err = validate_item_schema(item)
        assert err is not None
        assert "Cannot parse value as INT" in err

    def test_validate_item_schema_encrypted_secret(self):
        schema = {"type": "string", "minLength": 5}
        plaintext = "secret-token-12345"
        encrypted = encrypt_secret(plaintext)
        item = ConfigItem(
            namespace_id=uuid4(),
            key="api_token",
            value=encrypted,
            value_type=ConfigValueType.STRING,
            is_secret=True,
            json_schema=schema,
        )
        assert validate_item_schema(item) is None

    def test_validate_item_schema_corrupted_secret_fails(self):
        schema = {"type": "string"}
        item = ConfigItem(
            namespace_id=uuid4(),
            key="bad_token",
            value="invalid:corrupted:ciphertext",
            value_type=ConfigValueType.STRING,
            is_secret=True,
            json_schema=schema,
        )
        err = validate_item_schema(item)
        assert err is not None
        assert "Cannot decrypt secret value for validation" in err

    def test_decrypt_secret_invalid_master_key(self, monkeypatch: pytest.MonkeyPatch):
        from app.core import crypto
        from app.core.config import settings

        encrypted = crypto.encrypt_secret("my-secret")
        # Change master key to a different 32-byte key
        monkeypatch.setattr(settings, "CONFIG_MASTER_KEY", "different-32-byte-key-here1234!")
        with pytest.raises(Exception):
            crypto.decrypt_secret(encrypted)


@pytest.mark.asyncio
class TestConfigServiceOperations:
    async def test_draft_items_and_release_publish(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Staging",
            key=f"staging-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        ns_payload = ConfigNamespaceCreate(
            name=f"billing-ns-{uuid4().hex[:6]}",
            format=ConfigFormat.JSON,
            description="Billing configuration",
        )
        ns = await config_service.create_namespace(db_session, env, ns_payload, test_user)
        assert ns.id is not None

        # 1. Update draft items with secrets and regular items
        items_input = [
            ConfigItemInput(
                key="max_retries",
                value="3",
                value_type=ConfigValueType.INT,
                json_schema={"type": "integer", "maximum": 5},
            ),
            ConfigItemInput(
                key="payment_api_key",
                value="stripe_secret_key_12345",
                value_type=ConfigValueType.STRING,
                is_secret=True,
            ),
        ]
        saved_items = await config_service.update_draft_items(
            db_session, ns, items_input, test_user
        )
        assert len(saved_items) == 2
        # Secret is masked in return
        secret_saved = next(i for i in saved_items if i.key == "payment_api_key")
        assert secret_saved.value == MASKED_SECRET

        # 2. Get pending diff
        diff = await config_service.get_pending_diff(db_session, ns)
        assert "max_retries" in diff["added"]
        assert "payment_api_key" in diff["added"]

        # 3. Publish release with invalid schema should fail
        invalid_items_input = [
            ConfigItemInput(
                key="max_retries",
                value="10",  # exceeds maximum 5
                value_type=ConfigValueType.INT,
                json_schema={"type": "integer", "maximum": 5},
            )
        ]
        await config_service.update_draft_items(db_session, ns, invalid_items_input, test_user)
        with pytest.raises(FlagOpsError) as exc_info:
            await config_service.publish_release(
                db_session, ns, ConfigReleaseCreate(comment="invalid publish"), test_user
            )
        assert exc_info.value.code == "CONFIG_VALIDATION_FAILED"

        # 4. Fix draft item and publish release successfully
        valid_items_input = [
            ConfigItemInput(
                key="max_retries",
                value="4",
                value_type=ConfigValueType.INT,
                json_schema={"type": "integer", "maximum": 5},
            ),
            ConfigItemInput(
                key="payment_api_key",
                value="stripe_secret_valid",
                value_type=ConfigValueType.STRING,
                is_secret=True,
            ),
        ]
        await config_service.update_draft_items(db_session, ns, valid_items_input, test_user)
        rel1 = await config_service.publish_release(
            db_session, ns, ConfigReleaseCreate(comment="v1 initial"), test_user
        )
        assert rel1.version == 1
        assert ns.current_release_id == rel1.id

        # 5. Publish release v2 with updated value
        v2_items = [
            ConfigItemInput(
                key="max_retries",
                value="5",
                value_type=ConfigValueType.INT,
            ),
            ConfigItemInput(
                key="payment_api_key",
                value=MASKED_SECRET,  # sending masked keeps old ciphertext
                value_type=ConfigValueType.STRING,
                is_secret=True,
            ),
        ]
        await config_service.update_draft_items(db_session, ns, v2_items, test_user)
        rel2 = await config_service.publish_release(
            db_session, ns, ConfigReleaseCreate(comment="v2 update"), test_user
        )
        assert rel2.version == 2

        # 6. Releases diff between v1 and v2
        releases_diff = await config_service.get_releases_diff(db_session, ns, 1, 2)
        assert "max_retries" in releases_diff["changed"]

        # Diff for non-existent release raises 404
        with pytest.raises(FlagOpsError) as exc_info:
            await config_service.get_releases_diff(db_session, ns, 1, 99)
        assert exc_info.value.code == "RELEASE_NOT_FOUND"

        # 7. Rollback to v1
        rel3 = await config_service.rollback_release(db_session, ns, 1, test_user)
        assert rel3.version == 3  # new release version 3 containing v1 snapshot
        assert rel3.snapshot["configs"]["max_retries"] == "4"

        # Rollback to non-existent release raises 404
        with pytest.raises(FlagOpsError) as exc_info:
            await config_service.rollback_release(db_session, ns, 999, test_user)
        assert exc_info.value.code == "RELEASE_NOT_FOUND"

    async def test_get_draft_items_secret_reveal_permissions(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Prod",
            key=f"prod-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        ns = await config_service.create_namespace(
            db_session,
            env,
            ConfigNamespaceCreate(name=f"auth-ns-{uuid4().hex[:6]}", format=ConfigFormat.JSON),
            test_user,
        )

        plaintext = "super-secret-token"
        await config_service.update_draft_items(
            db_session,
            ns,
            [
                ConfigItemInput(
                    key="jwt_secret",
                    value=plaintext,
                    value_type=ConfigValueType.STRING,
                    is_secret=True,
                )
            ],
            test_user,
        )

        # Non-admin / non-owner reveal request raises 403 FORBIDDEN
        with pytest.raises(FlagOpsError) as exc_info:
            await config_service.list_draft_items(
                db_session,
                ns,
                reveal=True,
                user_role=MemberRole.DEVELOPER,
                user=test_user,
            )
        assert exc_info.value.code == "FORBIDDEN"

        # Admin reveal request decrypts value
        admin_items = await config_service.list_draft_items(
            db_session,
            ns,
            reveal=True,
            user_role=MemberRole.ADMIN,
            user=test_user,
        )
        assert admin_items[0].value == plaintext

    async def test_list_namespaces_and_evaluate_client_configs(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Eval Env",
            key=f"eval-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        ns = await config_service.create_namespace(
            db_session,
            env,
            ConfigNamespaceCreate(name=f"eval-ns-{uuid4().hex[:6]}", format=ConfigFormat.JSON),
            test_user,
        )
        # Test list namespaces
        namespaces = await config_service.list_namespaces(db_session, env.id)
        assert len(namespaces) >= 1
        assert any(n.id == ns.id for n in namespaces)

        # Publish a release with items
        await config_service.update_draft_items(
            db_session,
            ns,
            [
                ConfigItemInput(key="timeout", value="30", value_type=ConfigValueType.INT),
                ConfigItemInput(
                    key="secret_token",
                    value="supersecret",
                    value_type=ConfigValueType.STRING,
                    is_secret=True,
                ),
            ],
            test_user,
        )
        await config_service.publish_release(
            db_session, ns, ConfigReleaseCreate(comment="eval release"), test_user
        )

        # Test get_client_config with CLIENT scope (secrets masked)
        ver, client_configs = await config_service.get_client_config(
            db=db_session,
            env_id=env.id,
            namespace_name=ns.name,
            scope=ApiKeyScope.CLIENT,
        )
        assert ver >= 1
        assert client_configs["timeout"] == "30"
        assert client_configs["secret_token"] == MASKED_SECRET

        # Test get_client_config with SERVER scope (secrets decrypted)
        ver_server, server_configs = await config_service.get_client_config(
            db=db_session,
            env_id=env.id,
            namespace_name=ns.name,
            scope=ApiKeyScope.SERVER,
        )
        assert ver_server >= 1
        assert server_configs["secret_token"] == "supersecret"

        # Non-existent namespace raises 404
        with pytest.raises(FlagOpsError) as exc_info:
            await config_service.get_client_config(
                db=db_session,
                env_id=env.id,
                namespace_name="non-existent-ns",
                scope=ApiKeyScope.CLIENT,
            )
        assert exc_info.value.code == "NAMESPACE_NOT_FOUND"


# ============================================================================
# 2. FLAG DEBT SERVICE TESTS
# ============================================================================


class TestFlagDebtCalculation:
    def test_calculate_debt_score_components(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        created_at = now - timedelta(days=180)  # ~50% of 365
        snap = FlagSnapshot(
            created_at=created_at,
            archived_at=None,
            is_temporary=True,
            enabled_env_count=2,
            production_rollout_pct=100.0,
            days_at_full_rollout=45,  # 50% of 90
            days_since_last_eval=15,  # 50% of 30
            stale_days=30,
            now=now,
        )
        weights = DebtWeights(w_age=0.25, w_rollout=0.35, w_staleness=0.25, w_temporary=0.15)
        res = calculate_debt_score(snap, weights)

        assert 0 <= res.score <= 100
        assert res.age_score > 0
        assert res.rollout_score > 0
        assert res.staleness_score > 0
        assert res.temporary_score > 0
        assert res.state == LifecycleState.STALE  # days_at_full_rollout (45) > stale_days (30)
        assert len(res.recommendations) > 0

    def test_derive_lifecycle_state_all_branches(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)

        # 1. Archived
        archived_snap = FlagSnapshot(
            created_at=now,
            archived_at=now,
            is_temporary=False,
            enabled_env_count=1,
            production_rollout_pct=100.0,
            days_at_full_rollout=0,
            days_since_last_eval=0,
            stale_days=30,
            now=now,
        )
        assert derive_lifecycle_state(archived_snap) == LifecycleState.ARCHIVED
        assert get_recommendations(LifecycleState.ARCHIVED, archived_snap) == []

        # 2. Draft (not enabled anywhere)
        draft_snap = FlagSnapshot(
            created_at=now,
            archived_at=None,
            is_temporary=True,
            enabled_env_count=0,
            production_rollout_pct=0.0,
            days_at_full_rollout=0,
            days_since_last_eval=None,
            stale_days=30,
            now=now,
        )
        assert derive_lifecycle_state(draft_snap) == LifecycleState.DRAFT
        assert any("chưa được bật" in r for r in get_recommendations(LifecycleState.DRAFT, draft_snap))

        # 3. Stale via days_since_last_eval >= 14
        stale_eval_snap = FlagSnapshot(
            created_at=now - timedelta(days=20),
            archived_at=None,
            is_temporary=False,
            enabled_env_count=1,
            production_rollout_pct=50.0,
            days_at_full_rollout=0,
            days_since_last_eval=15,
            stale_days=30,
            now=now,
        )
        assert derive_lifecycle_state(stale_eval_snap) == LifecycleState.STALE

        # 4. Rolled out (100% production and not yet stale)
        rolled_out_snap = FlagSnapshot(
            created_at=now - timedelta(days=10),
            archived_at=None,
            is_temporary=True,
            enabled_env_count=1,
            production_rollout_pct=100.0,
            days_at_full_rollout=5,
            days_since_last_eval=1,
            stale_days=30,
            now=now,
        )
        assert derive_lifecycle_state(rolled_out_snap) == LifecycleState.ROLLED_OUT
        assert any("rollout 100%" in r for r in get_recommendations(LifecycleState.ROLLED_OUT, rolled_out_snap))

        # 5. Active
        active_snap = FlagSnapshot(
            created_at=now - timedelta(days=5),
            archived_at=None,
            is_temporary=False,
            enabled_env_count=1,
            production_rollout_pct=50.0,
            days_at_full_rollout=0,
            days_since_last_eval=2,
            stale_days=30,
            now=now,
        )
        assert derive_lifecycle_state(active_snap) == LifecycleState.ACTIVE


# ============================================================================
# 3. CHANGE REQUEST SERVICE TESTS
# ============================================================================


@pytest.mark.asyncio
class TestChangeRequestService:
    async def test_change_request_lifecycle_and_four_eyes(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        # Create second user for review
        reviewer = User(
            email=f"reviewer-{uuid4().hex[:6]}@flagops.internal",
            password_hash="secure-hashed-password",
            full_name="Reviewer User",
            is_active=True,
        )
        db_session.add(reviewer)

        env = Environment(
            project_id=test_project.id,
            name="Production",
            key=f"prod-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        flag = Flag(
            project_id=test_project.id,
            key=f"feature-payment-{uuid4().hex[:6]}",
            name="Payment Feature",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        payload = {"enabled": True, "flag_id": str(flag.id), "flag_key": flag.key}

        # 1. Create CR
        cr = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Enable Payment Feature",
            payload=payload,
        )
        assert cr.status == ChangeRequestStatus.PENDING

        # 2. Self-approval blocked (Four-Eyes Principle)
        with pytest.raises(FlagOpsError) as exc_info:
            await change_request_service.approve_change_request(
                db=db_session,
                cr=cr,
                reviewer_user=test_user,  # creator attempting to self-approve
            )
        assert exc_info.value.code == "SELF_APPROVAL_FORBIDDEN"
        assert exc_info.value.status_code == 403

        # 3. Valid approval by different reviewer applies changes immediately
        approved_cr = await change_request_service.approve_change_request(
            db=db_session,
            cr=cr,
            reviewer_user=reviewer,
        )
        assert approved_cr.status == ChangeRequestStatus.APPLIED
        assert approved_cr.reviewed_by == reviewer.id

        # 4. Approving an already applied CR raises 400 INVALID_STATE_TRANSITION
        with pytest.raises(FlagOpsError) as exc_info:
            await change_request_service.approve_change_request(
                db=db_session,
                cr=approved_cr,
                reviewer_user=reviewer,
            )
        assert exc_info.value.code == "INVALID_STATE_TRANSITION"

        # 5. Cancelling an applied CR raises INVALID_STATE_TRANSITION
        with pytest.raises(FlagOpsError) as exc_info:
            await change_request_service.cancel_change_request(
                db=db_session,
                cr=approved_cr,
                user=test_user,
            )
        assert exc_info.value.code == "INVALID_STATE_TRANSITION"

    async def test_change_request_rejection_and_cancellation(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        reviewer = User(
            email=f"reviewer-{uuid4().hex[:6]}@flagops.internal",
            password_hash="secure-hashed-password",
            full_name="Reviewer User",
            is_active=True,
        )
        other_user = User(
            email=f"other-{uuid4().hex[:6]}@flagops.internal",
            password_hash="secure-hashed-password",
            full_name="Other User",
            is_active=True,
        )
        db_session.add_all([reviewer, other_user])

        env = Environment(
            project_id=test_project.id,
            name="Prod",
            key=f"prod-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        cr = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Update config",
            payload={"key": "val"},
        )

        # Non-requester non-admin cannot cancel
        with pytest.raises(FlagOpsError) as exc_info:
            await change_request_service.cancel_change_request(
                db=db_session,
                cr=cr,
                user=other_user,
                is_admin=False,
            )
        assert exc_info.value.code == "FORBIDDEN"

        # Valid rejection
        rejected_cr = await change_request_service.reject_change_request(
            db=db_session,
            cr=cr,
            reviewer_user=reviewer,
        )
        assert rejected_cr.status == ChangeRequestStatus.REJECTED

    async def test_change_request_scheduled_execution(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        reviewer = User(
            email=f"rev-{uuid4().hex[:6]}@flagops.internal",
            password_hash="secure-hashed-password",
            full_name="Rev",
            is_active=True,
        )
        db_session.add(reviewer)

        env = Environment(
            project_id=test_project.id,
            name="Scheduled Env",
            key=f"s-env-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        flag = Flag(
            project_id=test_project.id,
            key=f"sched-flag-{uuid4().hex[:6]}",
            name="Sched Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        # Scheduled 1 hour in the past so scheduler applies it immediately
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        cr = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Scheduled change",
            payload={"enabled": True, "flag_id": str(flag.id), "flag_key": flag.key},
            scheduled_at=past_time,
            status=ChangeRequestStatus.APPROVED,
        )

        applied_count = await change_request_service.process_scheduled_change_requests(db_session)
        assert applied_count >= 1

        await db_session.refresh(cr)
        assert cr.status == ChangeRequestStatus.APPLIED

    async def test_get_and_list_change_requests(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="CR List Env",
            key=f"cr-list-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        # Non-existent CR raises 404
        with pytest.raises(FlagOpsError) as exc_info:
            await change_request_service.get_change_request(db_session, uuid4())
        assert exc_info.value.code == "CHANGE_REQUEST_NOT_FOUND"

        # Create 2 CRs
        cr1 = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="CR 1",
            payload={"key": "val1"},
            status=ChangeRequestStatus.DRAFT,
        )
        cr2 = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="CR 2",
            payload={"key": "val2"},
            status=ChangeRequestStatus.PENDING,
        )

        fetched = await change_request_service.get_change_request(db_session, cr1.id)
        assert fetched.id == cr1.id

        # List all in env
        all_crs = await change_request_service.list_change_requests(db_session, env.id)
        assert len(all_crs) >= 2

        # Filter by status
        pending_crs = await change_request_service.list_change_requests(
            db_session, env.id, status=ChangeRequestStatus.PENDING
        )
        assert all(c.status == ChangeRequestStatus.PENDING for c in pending_crs)
        assert any(c.id == cr2.id for c in pending_crs)

    async def test_simulate_impact(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Sim Env",
            key=f"sim-env-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        flag = Flag(
            project_id=test_project.id,
            key=f"sim-flag-{uuid4().hex[:6]}",
            name="Sim Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        var_true = Variation(flag_id=flag.id, key="true", value=True)
        var_false = Variation(flag_id=flag.id, key="false", value=False)
        db_session.add_all([var_true, var_false])
        await db_session.flush()

        cr_payload = {
            "flag_id": str(flag.id),
            "flag_key": flag.key,
            "enabled": True,
            "default_variation": "true",
            "off_variation": "false",
        }
        cr = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Simulate Flag Toggle",
            payload=cr_payload,
        )

        # Simulate impact when no evaluation events exist
        impact_resp = await change_request_service.simulate_impact(db_session, cr)
        assert impact_resp.total_contexts == 0
        assert impact_resp.change_percentage == 0.0

        # Simulate impact with non-existent flag
        cr_no_flag = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Non-existent flag CR",
            payload={"flag_key": "non_existent_flag_key"},
        )
        impact_no_flag = await change_request_service.simulate_impact(db_session, cr_no_flag)
        assert impact_no_flag.total_contexts == 0

    async def test_approve_future_and_cancel(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        reviewer = User(
            email=f"rev-fut-{uuid4().hex[:6]}@flagops.internal",
            password_hash="secure-hashed-password",
            full_name="Rev Future",
            is_active=True,
        )
        db_session.add(reviewer)

        env = Environment(
            project_id=test_project.id,
            name="Future Env",
            key=f"fut-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        flag = Flag(
            project_id=test_project.id,
            key=f"fut-flag-{uuid4().hex[:6]}",
            name="Future Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        future_time = datetime.now(timezone.utc) + timedelta(days=2)
        cr = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Future Flag Change",
            payload={"enabled": True, "flag_id": str(flag.id), "flag_key": flag.key},
            scheduled_at=future_time,
        )
        assert cr.status == ChangeRequestStatus.PENDING

        # Approving future CR sets status to APPROVED without immediate execution
        approved_cr = await change_request_service.approve_change_request(
            db=db_session,
            cr=cr,
            reviewer_user=reviewer,
        )
        assert approved_cr.status == ChangeRequestStatus.APPROVED

        # Creator cancels the approved future CR
        cancelled_cr = await change_request_service.cancel_change_request(
            db=db_session,
            cr=approved_cr,
            user=test_user,
        )
        assert cancelled_cr.status == ChangeRequestStatus.CANCELLED

    async def test_simulate_impact_with_events_and_rules(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Sim Event Env",
            key=f"sim-ev-{uuid4().hex[:6]}",
        )
        db_session.add(env)
        await db_session.flush()

        flag = Flag(
            project_id=test_project.id,
            key=f"sim-ev-flag-{uuid4().hex[:6]}",
            name="Sim Event Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        v_true = Variation(flag_id=flag.id, key="true", value=True)
        v_false = Variation(flag_id=flag.id, key="false", value=False)
        db_session.add_all([v_true, v_false])
        await db_session.flush()

        # Add setting for flag
        setting = await targeting.get_or_create_flag_setting(db_session, flag.id, env.id)
        setting.enabled = True
        setting.default_variation_id = v_false.id
        setting.off_variation_id = v_false.id
        await db_session.commit()

        # Add evaluation event
        evt = EvaluationEvent(
            flag_id=flag.id,
            environment_id=env.id,
            variation_id=v_false.id,
            reason="DEFAULT",
            context_key_hash="hash-12345",
            context={"targetingKey": "user-ev-1", "country": "VN"},
        )
        db_session.add(evt)
        await db_session.commit()

        # CR payload changes default_variation to true and includes targeting rules
        cr_payload = {
            "flag_id": str(flag.id),
            "flag_key": flag.key,
            "enabled": True,
            "default_variation": "true",
            "off_variation": "false",
            "rules": [
                {
                    "id": "rule-1",
                    "priority": 1,
                    "description": "Rule 1",
                    "conditions": {"attribute": "country", "operator": "EQ", "value": "VN"},
                    "distribution": [{"variation_id": str(v_true.id), "weight": 100.0}],
                }
            ],
        }
        cr = await change_request_service.create_change_request(
            db=db_session,
            env_id=env.id,
            user_id=test_user.id,
            title="Update to true",
            payload=cr_payload,
        )

        impact = await change_request_service.simulate_impact(db_session, cr)
        assert impact.total_contexts == 1
        assert impact.flag_key == flag.key


# ============================================================================
# 4. TARGETING SERVICE TESTS
# ============================================================================


class TestTargetingService:
    def test_condition_tree_validation(self):
        # Valid operator
        targeting.validate_condition_tree({"attribute": "country", "operator": "EQ", "value": "VN"})

        # Invalid operator raises INVALID_OPERATOR
        with pytest.raises(FlagOpsError) as exc_info:
            targeting.validate_condition_tree(
                {"attribute": "country", "operator": "INVALID_OP", "value": "VN"}
            )
        assert exc_info.value.code == "INVALID_OPERATOR"

        # Deep nesting (> 5) raises CONDITION_DEPTH_EXCEEDED
        nested = {"attribute": "a", "operator": "EQ", "value": "1"}
        for _ in range(6):
            nested = {"children": [nested]}

        with pytest.raises(FlagOpsError) as exc_info:
            targeting.validate_condition_tree(nested)
        assert exc_info.value.code == "CONDITION_DEPTH_EXCEEDED"

    @pytest.mark.asyncio
    async def test_cyclic_segment_reference_detection(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        # Segment 1 references Segment 2
        seg1_key = f"seg1-{uuid4().hex[:6]}"
        seg2_key = f"seg2-{uuid4().hex[:6]}"

        seg1_payload = SegmentCreate(
            key=seg1_key,
            name="Segment 1",
            conditions={
                "operator": "IS_ONE_OF_SEGMENT",
                "value": seg2_key,
            },
        )
        seg1 = await targeting.create_segment(db_session, test_project, seg1_payload, test_user.id)
        assert seg1.id is not None

        # Creating Segment 2 that references Segment 1 creates a circular loop (1 -> 2 -> 1)
        seg2_payload = SegmentCreate(
            key=seg2_key,
            name="Segment 2",
            conditions={
                "operator": "IS_ONE_OF_SEGMENT",
                "value": seg1_key,
            },
        )
        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.create_segment(
                db_session, test_project, seg2_payload, test_user.id
            )
        assert exc_info.value.code == "CYCLIC_SEGMENT_REFERENCE"

        # Direct self-reference also raises CYCLIC_SEGMENT_REFERENCE
        self_ref_payload = SegmentCreate(
            key=f"self-{uuid4().hex[:6]}",
            name="Self Referencing",
            conditions={
                "operator": "IS_ONE_OF_SEGMENT",
                "value": f"self-{uuid4().hex[:6]}",
            },
        )
        # Point to own key
        self_ref_payload.conditions["value"] = self_ref_payload.key
        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.create_segment(
                db_session, test_project, self_ref_payload, test_user.id
            )
        assert exc_info.value.code == "CYCLIC_SEGMENT_REFERENCE"

    @pytest.mark.asyncio
    async def test_atomic_targeting_rules_rollback_on_error(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Targeting Env",
            key=f"t-env-{uuid4().hex[:6]}",
        )
        db_session.add(env)

        flag = Flag(
            project_id=test_project.id,
            key=f"t-flag-{uuid4().hex[:6]}",
            name="Targeting Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        var_true = Variation(flag_id=flag.id, key="true", value=True)
        var_false = Variation(flag_id=flag.id, key="false", value=False)
        db_session.add_all([var_true, var_false])
        await db_session.flush()

        # Set initial rule
        initial_rules = TargetingRulesUpdate(
            rules=[
                TargetingRuleCreate(
                    priority=1,
                    description="Initial Rule",
                    conditions={"attribute": "plan", "operator": "EQ", "value": "pro"},
                    distribution=[
                        DistributionItem(variation_id=var_true.id, weight=100.0)
                    ],
                )
            ]
        )
        created_rules = await targeting.set_targeting_rules_atomic(
            db=db_session,
            flag=flag,
            env=env,
            rules_data=initial_rules,
            user_id=test_user.id,
        )
        assert len(created_rules) == 1
        initial_rule_id = created_rules[0].id

        # Attempt to replace rules with an invalid payload (distribution sum = 80 instead of 100)
        invalid_rules = TargetingRulesUpdate(
            rules=[
                TargetingRuleCreate(
                    priority=1,
                    description="Broken Rule",
                    conditions={"attribute": "plan", "operator": "EQ", "value": "enterprise"},
                    distribution=[
                        DistributionItem(variation_id=var_true.id, weight=80.0)  # Invalid weight!
                    ],
                )
            ]
        )

        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.set_targeting_rules_atomic(
                db=db_session,
                flag=flag,
                env=env,
                rules_data=invalid_rules,
                user_id=test_user.id,
            )
        assert exc_info.value.code == "INVALID_DISTRIBUTION_WEIGHT"

        # Verify transaction rollback: original rule remains intact
        current_rules = await targeting.get_targeting_rules(db_session, flag.id, env.id)
        assert len(current_rules) == 1
        assert current_rules[0].id == initial_rule_id
        assert current_rules[0].description == "Initial Rule"

    @pytest.mark.asyncio
    async def test_segment_crud_and_overrides(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        # 1. Create segment
        seg = await targeting.create_segment(
            db=db_session,
            project=test_project,
            data=SegmentCreate(
                key=f"beta-{uuid4().hex[:6]}",
                name="Beta Testers",
                conditions={"attribute": "beta", "operator": "EQ", "value": True},
            ),
            user_id=test_user.id,
        )
        # 2. Get project segments
        all_segs = await targeting.get_project_segments(db_session, test_project.id)
        assert any(s.id == seg.id for s in all_segs)

        # 3. Get single segment
        fetched_seg = await targeting.get_segment(db_session, test_project.id, seg.id)
        assert fetched_seg.name == "Beta Testers"

        # Not found raises 404
        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.get_segment(db_session, test_project.id, uuid4())
        assert exc_info.value.code == "SEGMENT_NOT_FOUND"

        # 4. Update segment
        updated_seg = await targeting.update_segment(
            db=db_session,
            project=test_project,
            segment_id=seg.id,
            data=SegmentUpdate(name="Beta Testers V2"),
            user_id=test_user.id,
        )
        assert updated_seg.name == "Beta Testers V2"

        # 5. Overrides test
        env = Environment(
            project_id=test_project.id,
            name="Override Env",
            key=f"ov-{uuid4().hex[:6]}",
        )
        db_session.add(env)

        flag = Flag(
            project_id=test_project.id,
            key=f"ov-flag-{uuid4().hex[:6]}",
            name="Override Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        v1 = Variation(flag_id=flag.id, key="true", value=True)
        v2 = Variation(flag_id=flag.id, key="false", value=False)
        db_session.add_all([v1, v2])
        await db_session.flush()

        # Create individual overrides
        ov1 = await targeting.create_individual_override(
            db=db_session,
            flag=flag,
            env=env,
            data=IndividualOverrideCreate(context_key="user-vip-1", variation_id=v1.id),
            user_id=test_user.id,
        )
        assert ov1.context_key == "user-vip-1"

        # Update existing override
        ov1_updated = await targeting.create_individual_override(
            db=db_session,
            flag=flag,
            env=env,
            data=IndividualOverrideCreate(context_key="user-vip-1", variation_id=v2.id),
            user_id=test_user.id,
        )
        assert ov1_updated.variation_id == v2.id

        # Invalid variation raises INVALID_VARIATION
        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.create_individual_override(
                db=db_session,
                flag=flag,
                env=env,
                data=IndividualOverrideCreate(context_key="user-err", variation_id=uuid4()),
                user_id=test_user.id,
            )
        assert exc_info.value.code == "INVALID_VARIATION"

        # Delete non-existent override raises OVERRIDE_NOT_FOUND
        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.delete_individual_override(
                db=db_session,
                flag=flag,
                env=env,
                override_id=uuid4(),
                user_id=test_user.id,
            )
        assert exc_info.value.code == "OVERRIDE_NOT_FOUND"

        # Delete individual override
        await targeting.delete_individual_override(
            db=db_session,
            flag=flag,
            env=env,
            override_id=ov1.id,
            user_id=test_user.id,
        )

        # 6. Delete segment
        await targeting.delete_segment(db_session, test_project, seg.id, test_user.id)
        with pytest.raises(FlagOpsError) as exc_info:
            await targeting.get_segment(db_session, test_project.id, seg.id)
        assert exc_info.value.code == "SEGMENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_simulate_flag_evaluation(
        self, db_session: AsyncSession, test_project: Project, test_user: User
    ):
        env = Environment(
            project_id=test_project.id,
            name="Sim Eval Env",
            key=f"sim-ev-{uuid4().hex[:6]}",
        )
        db_session.add(env)

        flag = Flag(
            project_id=test_project.id,
            key=f"eval-flag-{uuid4().hex[:6]}",
            name="Eval Flag",
            type=FlagType.BOOLEAN,
        )
        db_session.add(flag)
        await db_session.flush()

        v_true = Variation(flag_id=flag.id, key="true", value=True)
        v_false = Variation(flag_id=flag.id, key="false", value=False)
        db_session.add_all([v_true, v_false])
        await db_session.flush()

        # Set flag environment setting
        setting = await targeting.get_or_create_flag_setting(db_session, flag.id, env.id)
        setting.enabled = True
        setting.default_variation_id = v_true.id
        setting.off_variation_id = v_false.id
        await db_session.commit()

        # Simulate evaluation matching default variation
        sim_res = await targeting.simulate_flag_evaluation(
            db=db_session,
            flag=flag,
            env=env,
            context_raw={"targetingKey": "user-123", "country": "US"},
        )
        assert sim_res.flag_key == flag.key
        assert sim_res.value is True
        assert sim_res.variant == "true"

        # Simulate with matching rule
        rule_input = TargetingRulesUpdate(
            rules=[
                TargetingRuleCreate(
                    priority=1,
                    description="Match VN",
                    conditions={
                        "operator": "AND",
                        "conditions": [{"attribute": "country", "operator": "EQ", "value": "VN"}],
                    },
                    distribution=[DistributionItem(variation_id=v_true.id, weight=100.0)],
                )
            ]
        )
        await targeting.set_targeting_rules_atomic(db_session, flag, env, rule_input, test_user.id)
        sim_matched = await targeting.simulate_flag_evaluation(
            db=db_session,
            flag=flag,
            env=env,
            context_raw={"targetingKey": "user-123", "country": "VN"},
        )
        assert sim_matched.matched_rule_description == "Match VN"

        # Simulate when flag setting is disabled
        setting.enabled = False
        await db_session.commit()
        sim_disabled = await targeting.simulate_flag_evaluation(
            db=db_session,
            flag=flag,
            env=env,
            context_raw={"targetingKey": "user-123"},
        )
        assert sim_disabled.reason == "DISABLED"

        # Test list conditions and list segment refs
        targeting.validate_condition_tree([{"attribute": "plan", "operator": "EQ", "value": "pro"}])
        refs = targeting._extract_segment_refs([{"operator": "IS_ONE_OF_SEGMENT", "value": "s1"}])
        assert refs == ["s1"]


# ============================================================================
# 5. AUTH SERVICE TESTS
# ============================================================================


class TestAuthService:
    @pytest.mark.asyncio
    async def test_register_user_success_and_conflict(self, db_session: AsyncSession) -> None:
        email = f"auth_test_{uuid.uuid4().hex[:8]}@example.com"
        req = RegisterRequest(email=email, password="SecurePassword123!", full_name="Auth User")
        user = await auth_service.register_user(db_session, req)
        assert user.email == email
        assert user.full_name == "Auth User"
        await db_session.commit()

        # Duplicate email raises CONFLICT 409
        with pytest.raises(FlagOpsError) as exc_info:
            await auth_service.register_user(db_session, req)
        assert exc_info.value.code == "CONFLICT"
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_login_user_scenarios(self, db_session: AsyncSession) -> None:
        email = f"login_test_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"
        req = RegisterRequest(email=email, password=password, full_name="Login User")
        user = await auth_service.register_user(db_session, req)
        await db_session.commit()

        # Successful login
        tokens = await auth_service.login_user(db_session, email, password)
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # Wrong password raises UNAUTHORIZED
        with pytest.raises(FlagOpsError) as exc_info:
            await auth_service.login_user(db_session, email, "WrongPassword!")
        assert exc_info.value.code == "UNAUTHORIZED"

        # Missing user raises UNAUTHORIZED
        with pytest.raises(FlagOpsError) as exc_info:
            await auth_service.login_user(db_session, "missing@example.com", password)
        assert exc_info.value.code == "UNAUTHORIZED"

        # Inactive user raises UNAUTHORIZED
        user.is_active = False
        await db_session.commit()
        with pytest.raises(FlagOpsError) as exc_info:
            await auth_service.login_user(db_session, email, password)
        assert exc_info.value.code == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_refresh_and_logout_user(self, db_session: AsyncSession) -> None:
        email = f"refresh_test_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"
        req = RegisterRequest(email=email, password=password, full_name="Refresh User")
        user = await auth_service.register_user(db_session, req)
        await db_session.commit()

        tokens = await auth_service.login_user(db_session, email, password)
        raw_refresh = tokens["refresh_token"]

        # Valid refresh rotates tokens
        new_tokens = await auth_service.refresh_tokens(db_session, raw_refresh)
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

        # Old refresh token is revoked
        with pytest.raises(FlagOpsError) as exc_info:
            await auth_service.refresh_tokens(db_session, raw_refresh)
        assert exc_info.value.code == "UNAUTHORIZED"

        # Invalid JWT token
        with pytest.raises(FlagOpsError) as exc_info:
            await auth_service.refresh_tokens(db_session, "invalid.jwt.token")
        assert exc_info.value.code == "UNAUTHORIZED"

        # Logout revokes refresh token
        await auth_service.logout_user(db_session, user)
        assert user.refresh_token_hash is None


# ============================================================================
# 6. FLAG HEALTH SERVICE TESTS
# ============================================================================


class TestFlagHealthService:
    @pytest.mark.asyncio
    async def test_flag_health_list_and_filters(
        self, db_session: AsyncSession, test_user: User, test_org: Organization
    ) -> None:
        project = Project(
            organization_id=test_org.id,
            name=f"Health Proj {uuid.uuid4().hex[:6]}",
            slug=f"health-proj-{uuid.uuid4().hex[:6]}",
        )
        db_session.add(project)
        await db_session.flush()

        prod_env = Environment(
            project_id=project.id,
            name="Production",
            key="production",
            is_production=True,
            ruleset_version=1,
        )
        dev_env = Environment(
            project_id=project.id,
            name="Development",
            key="development",
            is_production=False,
            ruleset_version=1,
        )
        db_session.add_all([prod_env, dev_env])
        await db_session.flush()

        flag = Flag(
            project_id=project.id,
            key=f"health_flag_{uuid.uuid4().hex[:6]}",
            name="Health Flag",
            type=FlagType.BOOLEAN,
            is_temporary=True,
        )
        db_session.add(flag)
        await db_session.flush()

        fes = FlagEnvironmentSetting(
            flag_id=flag.id,
            environment_id=prod_env.id,
            enabled=True,
        )
        db_session.add(fes)
        await db_session.commit()

        # List flags health
        res = await flag_health_svc.get_flag_health_list(db_session, project.id, sort_by="score")
        assert res.summary.total >= 1
        assert len(res.items) >= 1

        # Test sorts and filters
        res_name = await flag_health_svc.get_flag_health_list(db_session, project.id, sort_by="name")
        assert len(res_name.items) >= 1
        res_state = await flag_health_svc.get_flag_health_list(db_session, project.id, sort_by="state")
        assert len(res_state.items) >= 1
        res_filtered = await flag_health_svc.get_flag_health_list(
            db_session, project.id, state_filter=LifecycleState.ACTIVE
        )
        assert isinstance(res_filtered.items, list)
        res_min_score = await flag_health_svc.get_flag_health_list(
            db_session, project.id, min_score=999
        )
        assert len(res_min_score.items) == 0

        # Single flag health
        single = await flag_health_svc.get_single_flag_health(db_session, flag.id, project.id)
        assert single.flag_id == flag.id

        # Not found flag health
        with pytest.raises(FlagOpsError) as exc_info:
            await flag_health_svc.get_single_flag_health(db_session, uuid.uuid4(), project.id)
        assert exc_info.value.code == "NOT_FOUND"

        # Archive flag
        archived = await flag_health_svc.archive_flag(db_session, flag.id, project.id, test_user.id)
        assert archived.state == LifecycleState.ARCHIVED

        # Re-archiving raises CONFLICT
        with pytest.raises(FlagOpsError) as exc_info:
            await flag_health_svc.archive_flag(db_session, flag.id, project.id, test_user.id)
        assert exc_info.value.code == "CONFLICT"


# ============================================================================
# 7. TENANCY SERVICE TESTS
# ============================================================================


class TestTenancyService:
    @pytest.mark.asyncio
    async def test_tenancy_full_crud(self, db_session: AsyncSession, test_user: User) -> None:
        slug = f"tenancy-org-{uuid.uuid4().hex[:8]}"
        org = await tenancy_service.create_org(
            db_session, test_user, OrgCreate(name="Tenancy Org", slug=slug)
        )
        assert org.name == "Tenancy Org"

        # Duplicate slug raises CONFLICT
        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.create_org(db_session, test_user, OrgCreate(name="Dup", slug=slug))
        assert exc_info.value.code == "CONFLICT"

        # List user orgs
        orgs = await tenancy_service.list_user_orgs(db_session, test_user)
        assert any(o.id == org.id for o in orgs)

        # Get & Update Org
        fetched_org = await tenancy_service.get_org(db_session, org.id)
        assert fetched_org.id == org.id
        updated_org = await tenancy_service.update_org(db_session, org.id, OrgUpdate(name="Renamed Org"))
        assert updated_org.name == "Renamed Org"

        # Member management
        other_user = User(
            email=f"member_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="hash123",
            full_name="Member User",
        )
        db_session.add(other_user)
        await db_session.flush()

        member = await tenancy_service.add_member(
            db_session, org.id, MemberCreate(user_id=other_user.id, role=MemberRole.DEVELOPER)
        )
        assert member.role == MemberRole.DEVELOPER
        members = await tenancy_service.list_members(db_session, org.id)
        assert len(members) >= 2

        updated_member = await tenancy_service.update_member_role(
            db_session, org.id, other_user.id, MemberUpdate(role=MemberRole.ADMIN)
        )
        assert updated_member.role == MemberRole.ADMIN

        # Project CRUD
        proj_slug = f"proj-{uuid.uuid4().hex[:6]}"
        project = await tenancy_service.create_project(
            db_session, org.id, ProjectCreate(name="Tenancy Project", slug=proj_slug)
        )
        assert project.slug == proj_slug
        projs = await tenancy_service.list_projects(db_session, org.id)
        assert any(p.id == project.id for p in projs)

        # Environment CRUD
        env = await tenancy_service.create_environment(
            db_session,
            project.id,
            EnvironmentCreate(name="Staging", key=f"staging-{uuid.uuid4().hex[:4]}", is_production=False),
        )
        envs = await tenancy_service.list_environments(db_session, project.id)
        assert any(e.id == env.id for e in envs)

        # API Key CRUD
        api_key, raw_key = await tenancy_service.create_api_key(
            db_session,
            env.id,
            ApiKeyCreate(name="SDK Server Key", scope=ApiKeyScope.SERVER),
        )
        assert raw_key.startswith("fo_srv_")
        verified = await tenancy_service.verify_api_key(db_session, raw_key)
        assert verified.id == api_key.id

        # Revoke API Key
        await tenancy_service.revoke_api_key(db_session, api_key)
        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.verify_api_key(db_session, raw_key)
        assert exc_info.value.code == "UNAUTHORIZED"

        # Cannot demote or remove last owner
        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.update_member_role(
                db_session, org.id, test_user.id, MemberUpdate(role=MemberRole.DEVELOPER)
            )
        assert exc_info.value.code == "CANNOT_REMOVE_LAST_OWNER"

        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.remove_member(db_session, org.id, test_user.id)
        assert exc_info.value.code == "CANNOT_REMOVE_LAST_OWNER"

        # Not found errors
        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.get_org(db_session, uuid.uuid4())
        assert exc_info.value.code == "ORGANIZATION_NOT_FOUND"

        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.remove_member(db_session, org.id, uuid.uuid4())
        assert exc_info.value.code == "MEMBER_NOT_FOUND"

        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.add_member(
                db_session, org.id, MemberCreate(user_id=uuid.uuid4(), role=MemberRole.VIEWER)
            )
        assert exc_info.value.code == "USER_NOT_FOUND"

        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.add_member(
                db_session, org.id, MemberCreate(user_id=other_user.id, role=MemberRole.VIEWER)
            )
        assert exc_info.value.code == "CONFLICT"

        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.create_project(
                db_session, org.id, ProjectCreate(name="Dup Proj", slug=proj_slug)
            )
        assert exc_info.value.code == "CONFLICT"

        with pytest.raises(FlagOpsError) as exc_info:
            await tenancy_service.create_environment(
                db_session,
                project.id,
                EnvironmentCreate(name="Dup Env", key=env.key, is_production=False),
            )
        assert exc_info.value.code == "CONFLICT"

        # Update project and environment
        updated_proj = await tenancy_service.update_project(
            db_session, project, ProjectUpdate(name="Renamed Proj")
        )
        assert updated_proj.name == "Renamed Proj"

        updated_env = await tenancy_service.update_environment(
            db_session, env, EnvironmentUpdate(name="Renamed Env")
        )
        assert updated_env.name == "Renamed Env"

        # Cleanup member & org
        await tenancy_service.remove_member(db_session, org.id, other_user.id)
        await tenancy_service.delete_environment(db_session, env)
        await tenancy_service.delete_project(db_session, project)
        await tenancy_service.delete_org(db_session, org.id)


# ============================================================================
# 8. FLAG AND EVAL SERVICE TESTS
# ============================================================================


class TestFlagAndEvalService:
    @pytest.mark.asyncio
    async def test_flag_service_lifecycle_and_eval(
        self, db_session: AsyncSession, test_user: User, test_org: Organization
    ) -> None:
        project = Project(
            organization_id=test_org.id,
            name=f"Flag Eval Proj {uuid.uuid4().hex[:6]}",
            slug=f"eval-proj-{uuid.uuid4().hex[:6]}",
        )
        db_session.add(project)
        await db_session.flush()

        env = Environment(
            project_id=project.id,
            name="Development",
            key=f"dev-{uuid.uuid4().hex[:4]}",
            ruleset_version=1,
        )
        db_session.add(env)
        await db_session.flush()

        # Create flag via flag service
        flag_in = FlagCreate(
            key=f"eval_flag_{uuid.uuid4().hex[:6]}",
            name="Eval Flag",
            type=FlagType.BOOLEAN,
            description="Test flag",
            tags=["eval", "core"],
            is_temporary=False,
            default_on_variation="true",
            default_off_variation="false",
        )
        flag = await flag_service.create_flag(db_session, project.id, test_user, flag_in)
        assert flag.key == flag_in.key

        # List flags
        flags = await flag_service.list_flags(db_session, project.id)
        assert any(f.id == flag.id for f in flags)

        # Update flag
        updated_flag = await flag_service.update_flag(
            db_session,
            flag,
            test_user,
            {"name": "Updated Name", "description": "New description"},
            FlagUpdate(name="Updated Name", description="New description"),
        )
        assert updated_flag.name == "Updated Name"

        # Update flag environment setting
        setting = await flag_service.get_flag_setting(db_session, flag.id, env.id)
        assert setting is not None
        updated_setting = await flag_service.update_flag_setting(
            db_session,
            flag,
            env.id,
            test_user,
            FlagSettingUpdate(enabled=True),
        )
        assert updated_setting.enabled is True

        # Ruleset version bump and audit log
        ver = await bump_ruleset_version(db_session, env.id)
        assert ver >= 2

        audit = await create_audit_log(
            db=db_session,
            actor_id=test_user.id,
            action="flag.updated",
            entity_type="flag",
            entity_id=str(flag.id),
            project_id=project.id,
        )
        assert audit.action == "flag.updated"
        await db_session.commit()

        # Evaluate flag via eval service
        eval_resp = await eval_service.evaluate_flag(
            db=db_session,
            env=env,
            flag_key=flag.key,
            raw_context={"targetingKey": "user-99"},
            scope=ApiKeyScope.SERVER,
        )
        assert eval_resp.flag_key == flag.key

        # Evaluate all flags
        all_eval = await eval_service.evaluate_all_flags(
            db=db_session,
            env=env,
            raw_context={"targetingKey": "user-99"},
            scope=ApiKeyScope.SERVER,
        )
        assert flag.key in all_eval.flags

        # Get ruleset payload
        payload = await eval_service.get_ruleset_payload(db_session, env, ApiKeyScope.SERVER)
        assert "flags" in payload
        assert "rulesetVersion" in payload

        # Archive and restore flag
        archived_flag = await flag_service.archive_flag(db_session, flag, test_user)
        assert archived_flag.archived_at is not None

        restored_flag = await flag_service.restore_flag(db_session, flag, test_user)
        assert restored_flag.archived_at is None
