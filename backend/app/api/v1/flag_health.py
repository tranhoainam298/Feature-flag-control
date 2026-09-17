"""Flag Health API — lifecycle state, debt score, archive action."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import require_project_role
from app.models.enums import LifecycleState, MemberRole
from app.models.organization import Membership
from app.models.project import Project
from app.models.user import User
from app.schemas.flag_health import FlagHealthListResponse, FlagHealthResponse
from app.services import flag_health as health_svc

router = APIRouter(tags=["Flag Health"])


@router.get(
    "/api/v1/projects/{project_id}/flag-health",
    response_model=FlagHealthListResponse,
    summary="Danh sách sức khỏe flag trong project",
)
async def list_flag_health(
    state: LifecycleState | None = Query(None, description="Lọc theo trạng thái"),
    min_score: int | None = Query(None, ge=0, le=100, description="Điểm nợ tối thiểu"),
    sort: str = Query("score", description="Sắp xếp: score | name | state"),
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.VIEWER)
    ),
) -> FlagHealthListResponse:
    project, _ = project_and_membership
    return await health_svc.get_flag_health_list(
        db,
        project.id,
        state_filter=state,
        min_score=min_score,
        sort_by=sort,
    )


@router.get(
    "/api/v1/projects/{project_id}/flags/{flag_id}/health",
    response_model=FlagHealthResponse,
    summary="Chi tiết sức khỏe của một flag",
)
async def get_flag_health(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.VIEWER)
    ),
) -> FlagHealthResponse:
    project, _ = project_and_membership
    return await health_svc.get_single_flag_health(db, flag_id, project.id)


@router.post(
    "/api/v1/projects/{project_id}/flags/{flag_id}/archive",
    response_model=FlagHealthResponse,
    summary="Archive một flag",
)
async def archive_flag(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
) -> FlagHealthResponse:
    project, _ = project_and_membership
    return await health_svc.archive_flag(db, flag_id, project.id, current_user.id)
