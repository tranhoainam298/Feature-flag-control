"""Organization and Membership API router."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import require_org_role
from app.models.enums import MemberRole
from app.models.organization import Membership, Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.organization import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    OrgCreate,
    OrgResponse,
    OrgUpdate,
)
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.tenancy import tenancy_service

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


@router.post(
    "",
    response_model=OrgResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo organization mới",
)
async def create_organization(
    payload: OrgCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Organization:
    return await tenancy_service.create_org(db, current_user, payload)


@router.get("", response_model=list[OrgResponse], summary="Danh sách organization của user")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Organization]:
    return await tenancy_service.list_user_orgs(db, current_user)


@router.get("/{org_id}", response_model=OrgResponse, summary="Lấy chi tiết organization")
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.VIEWER)),
) -> Organization:
    return await tenancy_service.get_org(db, org_id)


@router.patch("/{org_id}", response_model=OrgResponse, summary="Cập nhật organization")
async def update_organization(
    org_id: UUID,
    payload: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.ADMIN)),
) -> Organization:
    return await tenancy_service.update_org(db, org_id, payload)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa organization")
async def delete_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.OWNER)),
) -> Response:
    await tenancy_service.delete_org(db, org_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── MEMBERSHIP ENDPOINTS ───


@router.get(
    "/{org_id}/members",
    response_model=list[MemberResponse],
    summary="Danh sách thành viên organization",
)
async def list_members(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.VIEWER)),
) -> list[Membership]:
    return await tenancy_service.list_members(db, org_id)


@router.post(
    "/{org_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm thành viên vào organization",
)
async def add_member(
    org_id: UUID,
    payload: MemberCreate,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.ADMIN)),
) -> Membership:
    return await tenancy_service.add_member(db, org_id, payload)


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=MemberResponse,
    summary="Cập nhật vai trò thành viên",
)
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    payload: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.ADMIN)),
) -> Membership:
    return await tenancy_service.update_member_role(db, org_id, user_id, payload)


@router.delete(
    "/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa thành viên khỏi organization",
)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.ADMIN)),
) -> Response:
    await tenancy_service.remove_member(db, org_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── PROJECTS IN ORG ───


@router.get(
    "/{org_id}/projects",
    response_model=list[ProjectResponse],
    summary="Danh sách project trong organization",
)
async def list_org_projects(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.VIEWER)),
) -> list[Project]:
    return await tenancy_service.list_projects(db, org_id)


@router.post(
    "/{org_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo project mới trong organization (tự động sinh 3 environments)",
)
async def create_project(
    org_id: UUID,
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_org_role(MemberRole.ADMIN)),
) -> Project:
    return await tenancy_service.create_project(db, org_id, payload)
