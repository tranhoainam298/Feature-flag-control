"""Project and Project-Environments API router."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_project_role
from app.models.enums import MemberRole
from app.models.organization import Membership
from app.models.project import Environment, Project
from app.schemas.environment import EnvironmentCreate, EnvironmentResponse
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.services.tenancy import tenancy_service

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.get("/{project_id}", response_model=ProjectResponse, summary="Lấy chi tiết project")
async def get_project(
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.VIEWER)
    ),
) -> Project:
    project, _ = project_and_membership
    return project


@router.patch("/{project_id}", response_model=ProjectResponse, summary="Cập nhật project")
async def update_project(
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.ADMIN)
    ),
) -> Project:
    project, _ = project_and_membership
    return await tenancy_service.update_project(db, project, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa project")
async def delete_project(
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.ADMIN)
    ),
) -> Response:
    project, _ = project_and_membership
    await tenancy_service.delete_project(db, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── ENVIRONMENTS IN PROJECT ───


@router.get(
    "/{project_id}/environments",
    response_model=list[EnvironmentResponse],
    summary="Danh sách environment của project",
)
async def list_environments(
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.VIEWER)
    ),
) -> list[Environment]:
    project, _ = project_and_membership
    return await tenancy_service.list_environments(db, project.id)


@router.post(
    "/{project_id}/environments",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo environment mới trong project",
)
async def create_environment(
    payload: EnvironmentCreate,
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.ADMIN)
    ),
) -> Environment:
    project, _ = project_and_membership
    return await tenancy_service.create_environment(db, project.id, payload)
