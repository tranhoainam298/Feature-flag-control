"""Config Center API router — Namespaces, Draft Items, Diff, Releases, Rollback."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import require_environment_role, require_namespace_role
from app.models.config import ConfigItem, ConfigNamespace, ConfigRelease
from app.models.enums import MemberRole
from app.models.organization import Membership
from app.models.project import Environment
from app.models.user import User
from app.schemas.config import (
    ConfigDiffResponse,
    ConfigItemInput,
    ConfigItemResponse,
    ConfigItemsUpdateRequest,
    ConfigNamespaceCreate,
    ConfigNamespaceResponse,
    ConfigReleaseCreate,
    ConfigReleaseResponse,
)
from app.services import config_service

router = APIRouter(prefix="/api/v1", tags=["Config Center"])


# ──────────────────────────────────────────────────────────────────────────────
# NAMESPACES
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/environments/{environment_id}/namespaces",
    response_model=list[ConfigNamespaceResponse],
    summary="Danh sách namespace trong environment",
)
async def list_namespaces(
    environment_id: UUID,
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.VIEWER)
    ),
) -> list[ConfigNamespace]:
    env, _ = env_and_membership
    return await config_service.list_namespaces(db, env.id)


@router.post(
    "/environments/{environment_id}/namespaces",
    response_model=ConfigNamespaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo namespace mới trong environment",
)
async def create_namespace(
    environment_id: UUID,
    payload: ConfigNamespaceCreate,
    db: AsyncSession = Depends(get_db),
    env_and_membership: tuple[Environment, Membership] = Depends(
        require_environment_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> ConfigNamespace:
    env, _ = env_and_membership
    return await config_service.create_namespace(db, env, payload, current_user)


# ──────────────────────────────────────────────────────────────────────────────
# DRAFT ITEMS
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/namespaces/{namespace_id}/items",
    response_model=list[ConfigItemResponse],
    summary="Lấy danh sách config item trong bản nháp",
)
async def list_draft_items(
    namespace_id: UUID,
    reveal: bool = Query(
        default=False, description="Reveal plaintext secrets (requires ADMIN role)"
    ),
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.VIEWER)
    ),
    current_user: User = Depends(get_current_user),
) -> list[ConfigItem]:
    ns, membership = ns_and_membership
    return await config_service.list_draft_items(
        db=db,
        namespace=ns,
        reveal=reveal,
        user_role=membership.role,
        user=current_user,
    )


@router.put(
    "/namespaces/{namespace_id}/items",
    response_model=list[ConfigItemResponse],
    summary="Cập nhật bản nháp cấu hình",
)
async def update_draft_items(
    namespace_id: UUID,
    payload: ConfigItemsUpdateRequest | list[ConfigItemInput],
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> list[ConfigItem]:
    ns, _ = ns_and_membership
    items_list = payload.items if isinstance(payload, ConfigItemsUpdateRequest) else payload
    return await config_service.update_draft_items(db, ns, items_list, current_user)


@router.get(
    "/namespaces/{namespace_id}/pending-diff",
    response_model=ConfigDiffResponse,
    summary="Xem diff giữa bản nháp và release hiện tại",
)
async def get_pending_diff(
    namespace_id: UUID,
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.VIEWER)
    ),
) -> dict:
    ns, _ = ns_and_membership
    return await config_service.get_pending_diff(db, ns)


# ──────────────────────────────────────────────────────────────────────────────
# RELEASES
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/namespaces/{namespace_id}/releases",
    response_model=ConfigReleaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Phát hành (publish) bản nháp thành release mới",
)
async def publish_release(
    namespace_id: UUID,
    payload: ConfigReleaseCreate = ConfigReleaseCreate(),
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> ConfigRelease:
    ns, _ = ns_and_membership
    return await config_service.publish_release(db, ns, payload, current_user)


@router.get(
    "/namespaces/{namespace_id}/releases",
    response_model=list[ConfigReleaseResponse],
    summary="Lịch sử các release của namespace",
)
async def list_releases(
    namespace_id: UUID,
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.VIEWER)
    ),
) -> list[ConfigRelease]:
    ns, _ = ns_and_membership
    return await config_service.list_releases(db, ns)


@router.get(
    "/namespaces/{namespace_id}/releases/{v1}/diff/{v2}",
    response_model=ConfigDiffResponse,
    summary="So sánh diff giữa hai phiên bản release",
)
async def get_releases_diff(
    namespace_id: UUID,
    v1: int,
    v2: int,
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.VIEWER)
    ),
) -> dict:
    ns, _ = ns_and_membership
    return await config_service.get_releases_diff(db, ns, v1, v2)


@router.post(
    "/namespaces/{namespace_id}/releases/{v}/rollback",
    response_model=ConfigReleaseResponse,
    summary="Rollback cấu hình về phiên bản chỉ định",
)
async def rollback_release(
    namespace_id: UUID,
    v: int,
    db: AsyncSession = Depends(get_db),
    ns_and_membership: tuple[ConfigNamespace, Membership] = Depends(
        require_namespace_role(MemberRole.DEVELOPER)
    ),
    current_user: User = Depends(get_current_user),
) -> ConfigRelease:
    ns, _ = ns_and_membership
    return await config_service.rollback_release(db, ns, v, current_user)
