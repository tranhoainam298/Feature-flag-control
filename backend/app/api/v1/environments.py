"""Environment and API Key generation router."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_environment_role
from app.models.enums import MemberRole
from app.models.organization import Membership
from app.models.project import ApiKey, Environment
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from app.schemas.environment import EnvironmentResponse, EnvironmentUpdate
from app.services.tenancy import tenancy_service

router = APIRouter(prefix="/api/v1/environments", tags=["Environments"])


@router.get(
    "/{environment_id}", response_model=EnvironmentResponse, summary="Lấy chi tiết environment"
)
async def get_environment(
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.VIEWER)
    ),
) -> Environment:
    env, _ = env_and_membership
    return env


@router.patch(
    "/{environment_id}", response_model=EnvironmentResponse, summary="Cập nhật environment"
)
async def update_environment(
    payload: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.ADMIN)
    ),
) -> Environment:
    env, _ = env_and_membership
    return await tenancy_service.update_environment(db, env, payload)


@router.delete(
    "/{environment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa environment"
)
async def delete_environment(
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.ADMIN)
    ),
) -> Response:
    env, _ = env_and_membership
    await tenancy_service.delete_environment(db, env)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── API KEYS IN ENVIRONMENT ───


@router.get(
    "/{environment_id}/api-keys",
    response_model=list[ApiKeyResponse],
    summary="Danh sách API key của environment (chỉ hiển thị key_prefix, không có raw key)",
)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.VIEWER)
    ),
) -> list[ApiKey]:
    env, _ = env_and_membership
    return await tenancy_service.list_api_keys(db, env.id)


@router.post(
    "/{environment_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo API key mới (trả raw key duy nhất 1 lần trong response)",
)
async def create_api_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.DEVELOPER)
    ),
) -> ApiKeyCreateResponse:
    env, _ = env_and_membership
    api_key, raw_key = await tenancy_service.create_api_key(db, env.id, payload)
    return ApiKeyCreateResponse(
        id=api_key.id,
        environment_id=api_key.environment_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=raw_key,
        scope=api_key.scope,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )
