"""Change Request API Router — Multi-environment Governance, Four-Eyes Approval, and Impact Simulation."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import FlagOpsError
from app.core.permissions import (
    ROLE_RANK,
    require_change_request_role,
    require_environment_role,
)
from app.models.change_request import ChangeRequest
from app.models.enums import ChangeRequestStatus, MemberRole
from app.models.organization import Membership
from app.models.project import Environment
from app.models.user import User
from app.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestImpactResponse,
    ChangeRequestResponse,
)
from app.services.change_request import change_request_service

router = APIRouter(prefix="/api/v1", tags=["Change Requests"])


@router.post(
    "/environments/{environment_id}/change-requests",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo change request mới cho một environment",
)
async def create_change_request(
    environment_id: UUID,
    payload: ChangeRequestCreate,
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> ChangeRequest:
    env, _ = env_and_membership
    return await change_request_service.create_change_request(
        db=db,
        env_id=env.id,
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        payload=payload.payload,
        scheduled_at=payload.scheduled_at,
        status=payload.status,
    )


@router.get(
    "/environments/{environment_id}/change-requests",
    response_model=list[ChangeRequestResponse],
    summary="Danh sách change request trong environment (lọc theo status)",
)
async def list_change_requests(
    environment_id: UUID,
    status: ChangeRequestStatus | None = Query(None, description="Lọc theo trạng thái change request"),
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.VIEWER)
    ),
) -> list[ChangeRequest]:
    env, _ = env_and_membership
    return await change_request_service.list_change_requests(
        db=db, env_id=env.id, status=status
    )


@router.get(
    "/change-requests/{change_request_id}",
    response_model=ChangeRequestResponse,
    summary="Chi tiết change request",
)
async def get_change_request(
    cr_and_membership: tuple[ChangeRequest, Membership] = Depends(
        require_change_request_role(MemberRole.VIEWER)
    ),
) -> ChangeRequest:
    cr, _ = cr_and_membership
    return cr


@router.get(
    "/change-requests/{change_request_id}/impact",
    response_model=ChangeRequestImpactResponse,
    summary="Mô phỏng tác động của change request trên 1000 context gần nhất",
)
async def get_change_request_impact(
    db: AsyncSession = Depends(get_db),
    cr_and_membership: tuple[ChangeRequest, Membership] = Depends(
        require_change_request_role(MemberRole.VIEWER)
    ),
) -> ChangeRequestImpactResponse:
    cr, _ = cr_and_membership
    return await change_request_service.simulate_impact(db, cr)


@router.post(
    "/change-requests/{change_request_id}/approve",
    response_model=ChangeRequestResponse,
    summary="Duyệt change request (nguyên tắc bốn mắt, chỉ ADMIN/OWNER)",
)
async def approve_change_request(
    db: AsyncSession = Depends(get_db),
    cr_and_membership: tuple[ChangeRequest, Membership] = Depends(
        require_change_request_role(MemberRole.VIEWER)
    ),
    current_user: User = Depends(get_current_user),
) -> ChangeRequest:
    cr, membership = cr_and_membership

    # 1. Four-eyes check: creator can NEVER self-approve
    if cr.requested_by == current_user.id:
        raise FlagOpsError(
            code="SELF_APPROVAL_FORBIDDEN",
            message="Người tạo không được phép tự duyệt Change Request (nguyên tắc bốn mắt)",
            status_code=403,
        )

    # 2. Privilege check: only ADMIN or OWNER can approve
    if ROLE_RANK[membership.role] < ROLE_RANK[MemberRole.ADMIN]:
        raise FlagOpsError(
            code="FORBIDDEN",
            message="Chỉ ADMIN hoặc OWNER mới có quyền duyệt Change Request",
            status_code=403,
        )

    return await change_request_service.approve_change_request(
        db=db,
        cr=cr,
        reviewer_user=current_user,
    )


@router.post(
    "/change-requests/{change_request_id}/reject",
    response_model=ChangeRequestResponse,
    summary="Từ chối change request (chỉ ADMIN/OWNER)",
)
async def reject_change_request(
    db: AsyncSession = Depends(get_db),
    cr_and_membership: tuple[ChangeRequest, Membership] = Depends(
        require_change_request_role(MemberRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
) -> ChangeRequest:
    cr, _ = cr_and_membership
    return await change_request_service.reject_change_request(
        db=db,
        cr=cr,
        reviewer_user=current_user,
    )


@router.post(
    "/change-requests/{change_request_id}/cancel",
    response_model=ChangeRequestResponse,
    summary="Hủy change request (người tạo hoặc ADMIN/OWNER)",
)
async def cancel_change_request(
    db: AsyncSession = Depends(get_db),
    cr_and_membership: tuple[ChangeRequest, Membership] = Depends(
        require_change_request_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> ChangeRequest:
    cr, membership = cr_and_membership
    is_admin = ROLE_RANK[membership.role] >= ROLE_RANK[MemberRole.ADMIN]
    return await change_request_service.cancel_change_request(
        db=db,
        cr=cr,
        user=current_user,
        is_admin=is_admin,
    )
