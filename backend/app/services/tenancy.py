"""Tenancy service: Organization, Membership, Project, Environment, and API Key management."""

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FlagOpsError
from app.models.enums import ApiKeyScope, MemberRole
from app.models.organization import Membership, Organization
from app.models.project import ApiKey, Environment, Project
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.schemas.environment import EnvironmentCreate, EnvironmentUpdate
from app.schemas.organization import MemberCreate, MemberUpdate, OrgCreate, OrgUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate


class TenancyService:
    # ─── ORGANIZATION ───

    async def create_org(self, db: AsyncSession, user: User, payload: OrgCreate) -> Organization:
        existing = await db.scalar(select(Organization).where(Organization.slug == payload.slug))
        if existing:
            raise FlagOpsError(
                code="CONFLICT", message="Organization slug already exists", status_code=409
            )

        org = Organization(name=payload.name, slug=payload.slug)
        db.add(org)
        await db.flush()

        # Creator automatically becomes OWNER
        membership = Membership(
            organization_id=org.id,
            user_id=user.id,
            role=MemberRole.OWNER,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(org)
        return org

    async def list_user_orgs(self, db: AsyncSession, user: User) -> list[Organization]:
        stmt = (
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user.id)
            .order_by(Organization.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_org(self, db: AsyncSession, org_id: UUID) -> Organization:
        org = await db.scalar(select(Organization).where(Organization.id == org_id))
        if not org:
            raise FlagOpsError(
                code="ORGANIZATION_NOT_FOUND", message="Organization not found", status_code=404
            )
        return org

    async def update_org(self, db: AsyncSession, org_id: UUID, payload: OrgUpdate) -> Organization:
        org = await self.get_org(db, org_id)
        if payload.name is not None:
            org.name = payload.name
        await db.commit()
        await db.refresh(org)
        return org

    async def delete_org(self, db: AsyncSession, org_id: UUID) -> None:
        org = await self.get_org(db, org_id)
        await db.delete(org)
        await db.commit()

    # ─── MEMBERSHIP ───

    async def list_members(self, db: AsyncSession, org_id: UUID) -> list[Membership]:
        stmt = (
            select(Membership)
            .where(Membership.organization_id == org_id)
            .order_by(Membership.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def add_member(self, db: AsyncSession, org_id: UUID, payload: MemberCreate) -> Membership:
        user = await db.scalar(select(User).where(User.id == payload.user_id))
        if not user:
            raise FlagOpsError(code="USER_NOT_FOUND", message="User not found", status_code=404)

        existing = await db.scalar(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == payload.user_id,
            )
        )
        if existing:
            raise FlagOpsError(
                code="CONFLICT",
                message="User is already a member of this organization",
                status_code=409,
            )

        membership = Membership(
            organization_id=org_id,
            user_id=payload.user_id,
            role=payload.role,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(membership)
        return membership

    async def update_member_role(
        self, db: AsyncSession, org_id: UUID, user_id: UUID, payload: MemberUpdate
    ) -> Membership:
        membership = await db.scalar(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == user_id,
            )
        )
        if not membership:
            raise FlagOpsError(
                code="MEMBER_NOT_FOUND",
                message="Member not found in this organization",
                status_code=404,
            )

        if membership.role == MemberRole.OWNER and payload.role != MemberRole.OWNER:
            owner_count = await db.scalar(
                select(func.count(Membership.id)).where(
                    Membership.organization_id == org_id,
                    Membership.role == MemberRole.OWNER,
                )
            )
            if (owner_count or 0) <= 1:
                raise FlagOpsError(
                    code="CANNOT_REMOVE_LAST_OWNER",
                    message="Cannot demote the only owner of the organization",
                    status_code=400,
                )

        membership.role = payload.role
        await db.commit()
        await db.refresh(membership)
        return membership

    async def remove_member(self, db: AsyncSession, org_id: UUID, user_id: UUID) -> None:
        membership = await db.scalar(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == user_id,
            )
        )
        if not membership:
            raise FlagOpsError(
                code="MEMBER_NOT_FOUND",
                message="Member not found in this organization",
                status_code=404,
            )

        if membership.role == MemberRole.OWNER:
            owner_count = await db.scalar(
                select(func.count(Membership.id)).where(
                    Membership.organization_id == org_id,
                    Membership.role == MemberRole.OWNER,
                )
            )
            if (owner_count or 0) <= 1:
                raise FlagOpsError(
                    code="CANNOT_REMOVE_LAST_OWNER",
                    message="Cannot remove the only owner of the organization",
                    status_code=400,
                )

        await db.delete(membership)
        await db.commit()

    # ─── PROJECT ───

    async def create_project(
        self, db: AsyncSession, org_id: UUID, payload: ProjectCreate
    ) -> Project:
        existing = await db.scalar(
            select(Project).where(
                Project.organization_id == org_id,
                Project.slug == payload.slug,
            )
        )
        if existing:
            raise FlagOpsError(
                code="CONFLICT",
                message="Project slug already exists in this organization",
                status_code=409,
            )

        project = Project(
            organization_id=org_id,
            name=payload.name,
            slug=payload.slug,
            default_stale_days=payload.default_stale_days,
        )
        db.add(project)
        await db.flush()

        # Automatic generation of 3 environments
        envs = [
            Environment(
                project_id=project.id, name="Development", key="development", is_production=False
            ),
            Environment(project_id=project.id, name="Staging", key="staging", is_production=False),
            Environment(
                project_id=project.id, name="Production", key="production", is_production=True
            ),
        ]
        db.add_all(envs)
        await db.commit()
        await db.refresh(project)
        return project

    async def list_projects(self, db: AsyncSession, org_id: UUID) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.organization_id == org_id)
            .order_by(Project.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_project(
        self, db: AsyncSession, project: Project, payload: ProjectUpdate
    ) -> Project:
        if payload.name is not None:
            project.name = payload.name
        if payload.default_stale_days is not None:
            project.default_stale_days = payload.default_stale_days
        await db.commit()
        await db.refresh(project)
        return project

    async def delete_project(self, db: AsyncSession, project: Project) -> None:
        await db.delete(project)
        await db.commit()

    # ─── ENVIRONMENT ───

    async def list_environments(self, db: AsyncSession, project_id: UUID) -> list[Environment]:
        stmt = (
            select(Environment)
            .where(Environment.project_id == project_id)
            .order_by(Environment.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_environment(
        self, db: AsyncSession, project_id: UUID, payload: EnvironmentCreate
    ) -> Environment:
        existing = await db.scalar(
            select(Environment).where(
                Environment.project_id == project_id,
                Environment.key == payload.key,
            )
        )
        if existing:
            raise FlagOpsError(
                code="CONFLICT",
                message="Environment key already exists in this project",
                status_code=409,
            )

        env = Environment(
            project_id=project_id,
            name=payload.name,
            key=payload.key,
            is_production=payload.is_production,
        )
        db.add(env)
        await db.commit()
        await db.refresh(env)
        return env

    async def update_environment(
        self, db: AsyncSession, env: Environment, payload: EnvironmentUpdate
    ) -> Environment:
        if payload.name is not None:
            env.name = payload.name
        await db.commit()
        await db.refresh(env)
        return env

    async def delete_environment(self, db: AsyncSession, env: Environment) -> None:
        await db.delete(env)
        await db.commit()

    # ─── API KEY ───

    async def create_api_key(
        self, db: AsyncSession, env_id: UUID, payload: ApiKeyCreate
    ) -> tuple[ApiKey, str]:
        prefix = "fo_srv_" if payload.scope == ApiKeyScope.SERVER else "fo_cli_"
        random_part = secrets.token_urlsafe(32)
        raw_key = f"{prefix}{random_part}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]

        api_key = ApiKey(
            environment_id=env_id,
            name=payload.name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scope=payload.scope,
            expires_at=payload.expires_at,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key, raw_key

    async def list_api_keys(self, db: AsyncSession, env_id: UUID) -> list[ApiKey]:
        stmt = (
            select(ApiKey).where(ApiKey.environment_id == env_id).order_by(ApiKey.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def revoke_api_key(self, db: AsyncSession, api_key: ApiKey) -> ApiKey:
        api_key.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(api_key)
        return api_key

    async def verify_api_key(self, db: AsyncSession, raw_key: str) -> ApiKey:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
        if not api_key or api_key.revoked_at is not None:
            raise FlagOpsError(
                code="UNAUTHORIZED", message="API key is invalid or revoked", status_code=401
            )

        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            raise FlagOpsError(code="UNAUTHORIZED", message="API key has expired", status_code=401)

        return api_key


tenancy_service = TenancyService()
