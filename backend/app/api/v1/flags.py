"""Flags and FlagEnvironmentSettings API router."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import FlagOpsError
from app.core.permissions import (
    require_environment_role,
    require_flag_role,
    require_project_role,
)
from app.models.enums import ChangeRequestStatus, FlagType, MemberRole
from app.models.flag import Flag, FlagEnvironmentSetting
from app.models.organization import Membership
from app.models.project import Environment, Project
from app.models.user import User
from app.schemas.flag import (
    FlagCreate,
    FlagResponse,
    FlagSettingResponse,
    FlagSettingUpdate,
    FlagUpdate,
)
from app.services.change_request import change_request_service
from app.services.flag import flag_service

router = APIRouter(tags=["Flags"])


@router.get(
    "/api/v1/projects/{project_id}/flags",
    response_model=list[FlagResponse],
    summary="Danh sách flag trong project (lọc theo tag, type, archived, search)",
)
async def list_flags(
    tag: str | None = Query(None, description="Lọc theo tag"),
    type: FlagType | None = Query(None, description="Lọc theo kiểu flag"),
    archived: bool | None = Query(None, description="Lọc cờ lưu trữ"),
    search: str | None = Query(None, description="Tìm kiếm theo key hoặc tên"),
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.VIEWER)
    ),
) -> list[Flag]:
    project, _ = project_and_membership
    return await flag_service.list_flags(
        db=db,
        project_id=project.id,
        tag=tag,
        type_=type,
        archived=archived,
        search=search,
    )


@router.post(
    "/api/v1/projects/{project_id}/flags",
    response_model=FlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo flag mới + variations trong 1 transaction",
)
async def create_flag(
    payload: FlagCreate,
    db: AsyncSession = Depends(get_db),
    project_and_membership: tuple[Project, Membership] = Depends(
        require_project_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> Flag:
    project, _ = project_and_membership
    return await flag_service.create_flag(
        db=db, project_id=project.id, user=current_user, payload=payload
    )


@router.get(
    "/api/v1/flags/{flag_id}",
    response_model=FlagResponse,
    summary="Lấy chi tiết flag",
)
async def get_flag(
    flag_and_membership: tuple[Flag, Membership] = Depends(require_flag_role(MemberRole.VIEWER)),
) -> Flag:
    flag, _ = flag_and_membership
    return flag


@router.put(
    "/api/v1/flags/{flag_id}",
    response_model=FlagResponse,
    summary="Cập nhật metadata flag (PUT)",
)
@router.patch(
    "/api/v1/flags/{flag_id}",
    response_model=FlagResponse,
    summary="Cập nhật metadata flag (KHÔNG cho sửa key)",
)
async def update_flag(
    request: Request,
    payload: FlagUpdate,
    db: AsyncSession = Depends(get_db),
    flag_and_membership: tuple[Flag, Membership] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    current_user: User = Depends(get_current_user),
) -> Flag:
    flag, _ = flag_and_membership
    body = await request.json()
    if "key" in body:
        raise FlagOpsError(
            code="FLAG_KEY_IMMUTABLE",
            message="Flag key is immutable and cannot be changed",
            status_code=400,
        )

    return await flag_service.update_flag(
        db=db, flag=flag, user=current_user, payload_dict=body, payload=payload
    )


@router.post(
    "/api/v1/flags/{flag_id}/archive",
    response_model=FlagResponse,
    summary="Lưu trữ flag (archive)",
)
async def archive_flag(
    db: AsyncSession = Depends(get_db),
    flag_and_membership: tuple[Flag, Membership] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    current_user: User = Depends(get_current_user),
) -> Flag:
    flag, _ = flag_and_membership
    return await flag_service.archive_flag(db=db, flag=flag, user=current_user)


@router.post(
    "/api/v1/flags/{flag_id}/restore",
    response_model=FlagResponse,
    summary="Khôi phục flag đã lưu trữ (restore)",
)
async def restore_flag(
    db: AsyncSession = Depends(get_db),
    flag_and_membership: tuple[Flag, Membership] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    current_user: User = Depends(get_current_user),
) -> Flag:
    flag, _ = flag_and_membership
    return await flag_service.restore_flag(db=db, flag=flag, user=current_user)


@router.get(
    "/api/v1/flags/{flag_id}/environments/{env_id}",
    response_model=FlagSettingResponse,
    summary="Lấy cấu hình flag trên một environment cụ thể",
)
async def get_flag_setting(
    env_id: UUID,
    db: AsyncSession = Depends(get_db),
    flag_and_membership: tuple[Flag, Membership] = Depends(require_flag_role(MemberRole.VIEWER)),
    _env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.VIEWER, param_name="env_id")
    ),
) -> FlagEnvironmentSetting:
    flag, _ = flag_and_membership
    return await flag_service.get_flag_setting(db=db, flag_id=flag.id, env_id=env_id)


@router.put(
    "/api/v1/flags/{flag_id}/environments/{env_id}",
    response_model=FlagSettingResponse,
    summary="Cập nhật cấu hình flag trên environment (bật/tắt, variation, bucketing)",
)
async def update_flag_setting(
    env_id: UUID,
    payload: FlagSettingUpdate,
    db: AsyncSession = Depends(get_db),
    flag_and_membership: tuple[Flag, Membership] = Depends(require_flag_role(MemberRole.DEVELOPER)),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.DEVELOPER, param_name="env_id")
    ),
    current_user: User = Depends(get_current_user),
):
    flag, _ = flag_and_membership
    env, _ = env_and_membership

    # Rule: is_production = True -> DO NOT apply directly, create PENDING ChangeRequest
    if env.is_production:
        cr = await change_request_service.create_change_request(
            db=db,
            env_id=env.id,
            user_id=current_user.id,
            title=f"Update flag setting for {flag.key}",
            description="Auto-generated change request for production environment",
            payload={
                "type": "flag_setting",
                "flag_id": str(flag.id),
                "flag_key": flag.key,
                "setting": payload.model_dump(exclude_unset=True, mode="json"),
            },
            status=ChangeRequestStatus.PENDING,
        )
        current_setting = await flag_service.get_flag_setting(db, flag.id, env_id)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "id": str(current_setting.id),
                "flag_id": str(current_setting.flag_id),
                "environment_id": str(current_setting.environment_id),
                "enabled": current_setting.enabled,
                "default_variation_id": str(current_setting.default_variation_id)
                if current_setting.default_variation_id
                else None,
                "off_variation_id": str(current_setting.off_variation_id)
                if current_setting.off_variation_id
                else None,
                "bucketing_key": current_setting.bucketing_key,
                "change_request_id": str(cr.id),
                "change_request_status": cr.status.value,
                "message": "Change request created in PENDING status for production environment",
            },
            headers={"X-Change-Request-Id": str(cr.id)},
        )

    return await flag_service.update_flag_setting(
        db=db, flag=flag, env_id=env_id, user=current_user, payload=payload
    )
