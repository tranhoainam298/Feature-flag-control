"""RBAC and Multi-tenancy permission dependencies.

Data Isolation Rules:
- All queries must be scoped to the authenticated user's organization.
- User of Org A accessing Org B resource MUST receive 404 NOT_FOUND (never 403),
  to avoid leaking the existence of resources across tenants.
- Users with insufficient role within their OWN org receive 403 FORBIDDEN.
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import FlagOpsError
from app.models.enums import MemberRole
from app.models.flag import Flag
from app.models.organization import Membership
from app.models.project import ApiKey, Environment, Project
from app.models.user import User

# Hierarchy: higher number = more privilege
ROLE_RANK: dict[MemberRole, int] = {
    MemberRole.VIEWER: 0,
    MemberRole.DEVELOPER: 1,
    MemberRole.ADMIN: 2,
    MemberRole.OWNER: 3,
}


def require_role(*min_roles: MemberRole) -> Callable:
    """Dependency factory: user must have at least one of min_roles in ANY org.

    Coarse-grained gate for auth-only / global endpoints.
    """
    min_rank = min(ROLE_RANK[r] for r in min_roles)

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        result = await db.execute(select(Membership.role).where(Membership.user_id == user.id))
        roles = result.scalars().all()
        if not roles:
            raise FlagOpsError(
                code="FORBIDDEN", message="Insufficient permissions", status_code=403
            )

        max_rank = max(ROLE_RANK.get(r, -1) for r in roles)
        if max_rank < min_rank:
            raise FlagOpsError(
                code="FORBIDDEN", message="Insufficient permissions", status_code=403
            )
        return user

    return _check


def require_org_role(min_role: MemberRole = MemberRole.VIEWER) -> Callable:
    """Check user is member of org_id AND has role >= min_role.

    Returns 404 if org does not exist OR user is not a member (anti-enumeration).
    Returns 403 if user is a member but lacks sufficient role.
    """
    min_rank = ROLE_RANK[min_role]

    async def _check(
        org_id: UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Membership:
        # Check org exists and user is a member
        membership = await db.scalar(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == user.id,
            )
        )
        if not membership:
            raise FlagOpsError(
                code="ORGANIZATION_NOT_FOUND",
                message="Organization not found",
                status_code=404,
            )

        if ROLE_RANK[membership.role] < min_rank:
            raise FlagOpsError(
                code="FORBIDDEN",
                message="Insufficient permissions in this organization",
                status_code=403,
            )
        return membership

    return _check


def require_project_role(min_role: MemberRole = MemberRole.VIEWER) -> Callable:
    """Check user has access to project_id AND has role >= min_role.

    Returns 404 if project not found OR user belongs to another org (cross-org 404).
    Returns 403 if user belongs to the org but lacks sufficient role.
    """
    min_rank = ROLE_RANK[min_role]

    async def _check(
        project_id: UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[Project, Membership]:
        project = await db.scalar(select(Project).where(Project.id == project_id))
        if not project:
            raise FlagOpsError(
                code="PROJECT_NOT_FOUND",
                message="Project not found",
                status_code=404,
            )

        membership = await db.scalar(
            select(Membership).where(
                Membership.organization_id == project.organization_id,
                Membership.user_id == user.id,
            )
        )
        if not membership:
            # Cross-org isolation: 404, NEVER 403
            raise FlagOpsError(
                code="PROJECT_NOT_FOUND",
                message="Project not found",
                status_code=404,
            )

        if ROLE_RANK[membership.role] < min_rank:
            raise FlagOpsError(
                code="FORBIDDEN",
                message="Insufficient permissions in this project",
                status_code=403,
            )
        return project, membership

    return _check


async def require_project_access(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify user belongs to org owning project.

    Returns 404 (not 403) per security rules.
    """
    check_fn = require_project_role(MemberRole.VIEWER)
    await check_fn(project_id=project_id, user=user, db=db)
    return user


async def _check_env_impl(
    env_id: UUID,
    user: User,
    db: AsyncSession,
    min_rank: int,
) -> tuple[Environment, Membership]:
    env = await db.scalar(select(Environment).where(Environment.id == env_id))
    if not env:
        raise FlagOpsError(
            code="ENVIRONMENT_NOT_FOUND",
            message="Environment not found",
            status_code=404,
        )

    project = await db.scalar(select(Project).where(Project.id == env.project_id))
    if not project:
        raise FlagOpsError(
            code="ENVIRONMENT_NOT_FOUND",
            message="Environment not found",
            status_code=404,
        )

    membership = await db.scalar(
        select(Membership).where(
            Membership.organization_id == project.organization_id,
            Membership.user_id == user.id,
        )
    )
    if not membership:
        # Cross-org isolation: 404, NEVER 403
        raise FlagOpsError(
            code="ENVIRONMENT_NOT_FOUND",
            message="Environment not found",
            status_code=404,
        )

    if ROLE_RANK[membership.role] < min_rank:
        raise FlagOpsError(
            code="FORBIDDEN",
            message="Insufficient permissions in this environment",
            status_code=403,
        )
    return env, membership


def require_environment_role(
    min_role: MemberRole = MemberRole.VIEWER,
    param_name: str = "environment_id",
) -> Callable:
    """Check user has access to environment and role >= min_role.

    Supports either environment_id or env_id path parameter.
    """
    min_rank = ROLE_RANK[min_role]

    if param_name == "env_id":

        async def _check_env(
            env_id: UUID,
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
        ) -> tuple[Environment, Membership]:
            return await _check_env_impl(env_id, user, db, min_rank)

        return _check_env

    async def _check(
        environment_id: UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[Environment, Membership]:
        return await _check_env_impl(environment_id, user, db, min_rank)

    return _check


def require_api_key_role(min_role: MemberRole = MemberRole.DEVELOPER) -> Callable:
    """Check user has access to api_key_id AND has role >= min_role.

    Returns 404 if api_key not found OR user belongs to another org.
    Returns 403 if user belongs to the org but lacks role.
    """
    min_rank = ROLE_RANK[min_role]

    async def _check(
        api_key_id: UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[ApiKey, Membership]:
        api_key = await db.scalar(select(ApiKey).where(ApiKey.id == api_key_id))
        if not api_key:
            raise FlagOpsError(
                code="API_KEY_NOT_FOUND",
                message="API key not found",
                status_code=404,
            )

        env = await db.scalar(select(Environment).where(Environment.id == api_key.environment_id))
        if not env:
            raise FlagOpsError(
                code="API_KEY_NOT_FOUND",
                message="API key not found",
                status_code=404,
            )

        project = await db.scalar(select(Project).where(Project.id == env.project_id))
        if not project:
            raise FlagOpsError(
                code="API_KEY_NOT_FOUND",
                message="API key not found",
                status_code=404,
            )

        membership = await db.scalar(
            select(Membership).where(
                Membership.organization_id == project.organization_id,
                Membership.user_id == user.id,
            )
        )
        if not membership:
            # Cross-org isolation: 404, NEVER 403
            raise FlagOpsError(
                code="API_KEY_NOT_FOUND",
                message="API key not found",
                status_code=404,
            )

        if ROLE_RANK[membership.role] < min_rank:
            raise FlagOpsError(
                code="FORBIDDEN",
                message="Insufficient permissions for this API key",
                status_code=403,
            )
        return api_key, membership

    return _check


def require_flag_role(min_role: MemberRole = MemberRole.VIEWER) -> Callable:
    """Check user has access to flag_id AND has role >= min_role.

    Returns 404 if flag not found OR user belongs to another org.
    Returns 403 if user belongs to the org but lacks role.
    """
    min_rank = ROLE_RANK[min_role]

    async def _check(
        flag_id: UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[Flag, Membership]:
        flag = await db.scalar(
            select(Flag).options(selectinload(Flag.variations)).where(Flag.id == flag_id)
        )
        if not flag:
            raise FlagOpsError(
                code="FLAG_NOT_FOUND",
                message="Flag not found",
                status_code=404,
            )

        project = await db.scalar(select(Project).where(Project.id == flag.project_id))
        if not project:
            raise FlagOpsError(
                code="FLAG_NOT_FOUND",
                message="Flag not found",
                status_code=404,
            )

        membership = await db.scalar(
            select(Membership).where(
                Membership.organization_id == project.organization_id,
                Membership.user_id == user.id,
            )
        )
        if not membership:
            # Cross-org isolation: 404, NEVER 403
            raise FlagOpsError(
                code="FLAG_NOT_FOUND",
                message="Flag not found",
                status_code=404,
            )

        if ROLE_RANK[membership.role] < min_rank:
            raise FlagOpsError(
                code="FORBIDDEN",
                message="Insufficient permissions for this flag",
                status_code=403,
            )
        return flag, membership

    return _check
