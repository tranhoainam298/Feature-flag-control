"""API Key operations router (Revocation)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_api_key_role
from app.models.enums import MemberRole
from app.models.organization import Membership
from app.models.project import ApiKey
from app.schemas.api_key import ApiKeyResponse
from app.services.tenancy import tenancy_service

router = APIRouter(prefix="/api/v1/api-keys", tags=["API Keys"])


@router.post(
    "/{api_key_id}/revoke",
    response_model=ApiKeyResponse,
    summary="Thu hồi API key (không xóa cứng, vô hiệu hóa vĩnh viễn)",
)
async def revoke_api_key(
    db: AsyncSession = Depends(get_db),
    api_key_and_membership: tuple[ApiKey, Membership] = Depends(
        require_api_key_role(MemberRole.DEVELOPER)
    ),
) -> ApiKey:
    api_key, _ = api_key_and_membership
    return await tenancy_service.revoke_api_key(db, api_key)
