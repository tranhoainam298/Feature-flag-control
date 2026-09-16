"""Flag service: Flag, Variation, FlagEnvironmentSetting, ruleset bump, and audit logging."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import FlagOpsError
from app.models.audit import AuditLog
from app.models.enums import FlagType
from app.models.flag import Flag, FlagEnvironmentSetting, Variation
from app.models.project import Environment, Project
from app.models.user import User
from app.schemas.flag import FlagCreate, FlagSettingUpdate, FlagUpdate, VariationCreate


async def bump_ruleset_version(db: AsyncSession, env_id: UUID) -> int:
    """Increment environment.ruleset_version by 1 on any write mutation."""
    stmt = (
        update(Environment)
        .where(Environment.id == env_id)
        .values(ruleset_version=Environment.ruleset_version + 1)
        .returning(Environment.ruleset_version)
    )
    result = await db.scalar(stmt)
    return result or 0


async def create_audit_log(
    db: AsyncSession,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    organization_id: UUID | None = None,
    project_id: UUID | None = None,
    environment_id: UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    """Create an append-only audit log entry."""
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        organization_id=organization_id,
        project_id=project_id,
        environment_id=environment_id,
        before=before,
        after=after,
    )
    db.add(log)
    return log


def validate_variation_value(flag_type: FlagType, value: Any) -> None:
    """Validate that variation value matches flag.type."""
    if flag_type == FlagType.BOOLEAN:
        if not isinstance(value, bool):
            raise FlagOpsError(
                code="TYPE_MISMATCH",
                message=f"Variation value '{value}' does not match flag type '{flag_type}'",
                status_code=422,
            )
    elif flag_type == FlagType.STRING:
        if not isinstance(value, str):
            raise FlagOpsError(
                code="TYPE_MISMATCH",
                message=f"Variation value '{value}' does not match flag type '{flag_type}'",
                status_code=422,
            )
    elif flag_type == FlagType.NUMBER:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise FlagOpsError(
                code="TYPE_MISMATCH",
                message=f"Variation value '{value}' does not match flag type '{flag_type}'",
                status_code=422,
            )
    elif flag_type == FlagType.JSON:
        if not isinstance(value, (dict, list)):
            raise FlagOpsError(
                code="TYPE_MISMATCH",
                message=f"Variation value '{value}' does not match flag type '{flag_type}'",
                status_code=422,
            )


class FlagService:
    async def create_flag(
        self, db: AsyncSession, project_id: UUID, user: User, payload: FlagCreate
    ) -> Flag:
        # Check uniqueness of key in project
        existing = await db.scalar(
            select(Flag).where(Flag.project_id == project_id, Flag.key == payload.key)
        )
        if existing:
            raise FlagOpsError(
                code="CONFLICT",
                message=f"Flag key '{payload.key}' already exists in this project",
                status_code=409,
            )

        # Get project for org_id
        project = await db.scalar(select(Project).where(Project.id == project_id))
        org_id = project.organization_id if project else None

        # Prepare variations
        if payload.type == FlagType.BOOLEAN:
            if not payload.variations:
                variations_to_create = [
                    VariationCreate(key="on", value=True, name="On"),
                    VariationCreate(key="off", value=False, name="Off"),
                ]
            else:
                variations_to_create = payload.variations
                for v in variations_to_create:
                    validate_variation_value(payload.type, v.value)
        else:
            if not payload.variations or len(payload.variations) < 2:
                raise FlagOpsError(
                    code="VALIDATION_ERROR",
                    message=f"Flag of type '{payload.type}' must have at least 2 variations",
                    status_code=422,
                )
            variations_to_create = payload.variations
            for v in variations_to_create:
                validate_variation_value(payload.type, v.value)

        # Create Flag
        flag = Flag(
            project_id=project_id,
            key=payload.key,
            name=payload.name,
            description=payload.description,
            type=payload.type,
            toggle_kind=payload.toggle_kind,
            is_temporary=payload.is_temporary,
            is_client_visible=payload.is_client_visible,
            tags=payload.tags,
            created_by=user.id,
        )
        db.add(flag)
        await db.flush()

        # Create Variations
        created_vars: list[Variation] = []
        for v in variations_to_create:
            var = Variation(
                flag_id=flag.id,
                key=v.key,
                value=v.value,
                name=v.name,
                description=v.description,
            )
            db.add(var)
            created_vars.append(var)
        await db.flush()

        # Pick default and off variations
        default_var = next((v for v in created_vars if v.key in ("on", "true")), created_vars[0])
        off_var = next(
            (v for v in created_vars if v.key in ("off", "false")),
            created_vars[-1] if len(created_vars) > 1 else None,
        )

        # Create flag_environment_setting for EVERY environment of the project
        envs = (
            await db.scalars(select(Environment).where(Environment.project_id == project_id))
        ).all()
        for env in envs:
            setting = FlagEnvironmentSetting(
                flag_id=flag.id,
                environment_id=env.id,
                enabled=False,
                default_variation_id=default_var.id,
                off_variation_id=off_var.id if off_var else None,
                bucketing_key="userId",
            )
            db.add(setting)
            await bump_ruleset_version(db, env.id)

        # Audit log
        await create_audit_log(
            db=db,
            actor_id=user.id,
            action="flag.create",
            entity_type="flag",
            entity_id=str(flag.id),
            organization_id=org_id,
            project_id=project_id,
            after={
                "key": flag.key,
                "name": flag.name,
                "type": flag.type,
                "toggle_kind": flag.toggle_kind,
            },
        )

        await db.commit()

        # Reload with variations
        stmt = select(Flag).options(selectinload(Flag.variations)).where(Flag.id == flag.id)
        result = await db.scalar(stmt)
        return result or flag

    async def list_flags(
        self,
        db: AsyncSession,
        project_id: UUID,
        tag: str | None = None,
        type_: FlagType | None = None,
        archived: bool | None = None,
        search: str | None = None,
    ) -> list[Flag]:
        stmt = (
            select(Flag).options(selectinload(Flag.variations)).where(Flag.project_id == project_id)
        )

        if archived is True:
            stmt = stmt.where(Flag.archived_at.is_not(None))
        elif archived is False:
            stmt = stmt.where(Flag.archived_at.is_(None))
        else:
            # Default: active flags only
            stmt = stmt.where(Flag.archived_at.is_(None))

        if tag:
            stmt = stmt.where(Flag.tags.contains([tag]))

        if type_:
            stmt = stmt.where(Flag.type == type_)

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(Flag.key.ilike(pattern) | Flag.name.ilike(pattern))

        stmt = stmt.order_by(Flag.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_flag(self, db: AsyncSession, flag_id: UUID) -> Flag:
        flag = await db.scalar(
            select(Flag).options(selectinload(Flag.variations)).where(Flag.id == flag_id)
        )
        if not flag:
            raise FlagOpsError(code="FLAG_NOT_FOUND", message="Flag not found", status_code=404)
        return flag

    async def update_flag(
        self,
        db: AsyncSession,
        flag: Flag,
        user: User,
        payload_dict: dict[str, Any],
        payload: FlagUpdate,
    ) -> Flag:
        # Immutable key rule: if body contains "key" -> 400 FLAG_KEY_IMMUTABLE
        if "key" in payload_dict:
            raise FlagOpsError(
                code="FLAG_KEY_IMMUTABLE",
                message="Flag key is immutable and cannot be changed",
                status_code=400,
            )

        before = {
            "name": flag.name,
            "description": flag.description,
            "toggle_kind": flag.toggle_kind,
            "is_temporary": flag.is_temporary,
            "is_client_visible": flag.is_client_visible,
            "tags": list(flag.tags),
        }

        if payload.name is not None:
            flag.name = payload.name
        if payload.description is not None:
            flag.description = payload.description
        if payload.toggle_kind is not None:
            flag.toggle_kind = payload.toggle_kind
        if payload.is_temporary is not None:
            flag.is_temporary = payload.is_temporary
        if payload.is_client_visible is not None:
            flag.is_client_visible = payload.is_client_visible
        if payload.tags is not None:
            flag.tags = payload.tags

        after = {
            "name": flag.name,
            "description": flag.description,
            "toggle_kind": flag.toggle_kind,
            "is_temporary": flag.is_temporary,
            "is_client_visible": flag.is_client_visible,
            "tags": list(flag.tags),
        }

        # Bump ruleset_version for all envs of this project
        envs = (
            await db.scalars(select(Environment).where(Environment.project_id == flag.project_id))
        ).all()
        for env in envs:
            await bump_ruleset_version(db, env.id)

        # Audit log
        project = await db.scalar(select(Project).where(Project.id == flag.project_id))
        await create_audit_log(
            db=db,
            actor_id=user.id,
            action="flag.update",
            entity_type="flag",
            entity_id=str(flag.id),
            organization_id=project.organization_id if project else None,
            project_id=flag.project_id,
            before=before,
            after=after,
        )

        await db.commit()
        await db.refresh(flag)
        return flag

    async def archive_flag(self, db: AsyncSession, flag: Flag, user: User) -> Flag:
        before = {"archived_at": flag.archived_at.isoformat() if flag.archived_at else None}
        flag.archived_at = datetime.now(timezone.utc)
        after = {"archived_at": flag.archived_at.isoformat()}

        envs = (
            await db.scalars(select(Environment).where(Environment.project_id == flag.project_id))
        ).all()
        for env in envs:
            await bump_ruleset_version(db, env.id)

        project = await db.scalar(select(Project).where(Project.id == flag.project_id))
        await create_audit_log(
            db=db,
            actor_id=user.id,
            action="flag.archive",
            entity_type="flag",
            entity_id=str(flag.id),
            organization_id=project.organization_id if project else None,
            project_id=flag.project_id,
            before=before,
            after=after,
        )

        await db.commit()
        await db.refresh(flag)
        return flag

    async def restore_flag(self, db: AsyncSession, flag: Flag, user: User) -> Flag:
        before = {"archived_at": flag.archived_at.isoformat() if flag.archived_at else None}
        flag.archived_at = None
        after = {"archived_at": None}

        envs = (
            await db.scalars(select(Environment).where(Environment.project_id == flag.project_id))
        ).all()
        for env in envs:
            await bump_ruleset_version(db, env.id)

        project = await db.scalar(select(Project).where(Project.id == flag.project_id))
        await create_audit_log(
            db=db,
            actor_id=user.id,
            action="flag.restore",
            entity_type="flag",
            entity_id=str(flag.id),
            organization_id=project.organization_id if project else None,
            project_id=flag.project_id,
            before=before,
            after=after,
        )

        await db.commit()
        await db.refresh(flag)
        return flag

    async def get_flag_setting(
        self, db: AsyncSession, flag_id: UUID, env_id: UUID
    ) -> FlagEnvironmentSetting:
        setting = await db.scalar(
            select(FlagEnvironmentSetting).where(
                FlagEnvironmentSetting.flag_id == flag_id,
                FlagEnvironmentSetting.environment_id == env_id,
            )
        )
        if not setting:
            raise FlagOpsError(
                code="FLAG_SETTING_NOT_FOUND",
                message="Flag environment setting not found",
                status_code=404,
            )
        return setting

    async def update_flag_setting(
        self,
        db: AsyncSession,
        flag: Flag,
        env_id: UUID,
        user: User,
        payload: FlagSettingUpdate,
    ) -> FlagEnvironmentSetting:
        setting = await self.get_flag_setting(db, flag.id, env_id)

        # Validate variation IDs if provided
        if payload.default_variation_id is not None:
            var = await db.scalar(
                select(Variation).where(
                    Variation.id == payload.default_variation_id,
                    Variation.flag_id == flag.id,
                )
            )
            if not var:
                raise FlagOpsError(
                    code="VALIDATION_ERROR",
                    message="default_variation_id does not belong to this flag",
                    status_code=422,
                )

        if payload.off_variation_id is not None:
            var = await db.scalar(
                select(Variation).where(
                    Variation.id == payload.off_variation_id,
                    Variation.flag_id == flag.id,
                )
            )
            if not var:
                raise FlagOpsError(
                    code="VALIDATION_ERROR",
                    message="off_variation_id does not belong to this flag",
                    status_code=422,
                )

        before = {
            "enabled": setting.enabled,
            "default_variation_id": str(setting.default_variation_id)
            if setting.default_variation_id
            else None,
            "off_variation_id": str(setting.off_variation_id) if setting.off_variation_id else None,
            "bucketing_key": setting.bucketing_key,
        }

        if payload.enabled is not None:
            setting.enabled = payload.enabled
        if payload.default_variation_id is not None:
            setting.default_variation_id = payload.default_variation_id
        if payload.off_variation_id is not None:
            setting.off_variation_id = payload.off_variation_id
        if payload.bucketing_key is not None:
            setting.bucketing_key = payload.bucketing_key

        after = {
            "enabled": setting.enabled,
            "default_variation_id": str(setting.default_variation_id)
            if setting.default_variation_id
            else None,
            "off_variation_id": str(setting.off_variation_id) if setting.off_variation_id else None,
            "bucketing_key": setting.bucketing_key,
        }

        # Bump ruleset_version for THIS environment only
        await bump_ruleset_version(db, env_id)

        project = await db.scalar(select(Project).where(Project.id == flag.project_id))
        await create_audit_log(
            db=db,
            actor_id=user.id,
            action="flag_setting.update",
            entity_type="flag_environment_setting",
            entity_id=str(setting.id),
            organization_id=project.organization_id if project else None,
            project_id=flag.project_id,
            environment_id=env_id,
            before=before,
            after=after,
        )

        await db.commit()
        await db.refresh(setting)
        return setting


flag_service = FlagService()
