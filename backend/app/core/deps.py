import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import FlagOpsError
from app.core.security import JWTError, decode_token
from app.models.project import ApiKey
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT, return the active User or raise 401."""
    if creds is None:
        raise FlagOpsError(
            code="UNAUTHORIZED", message="Missing authentication token", status_code=401
        )

    try:
        payload = decode_token(creds.credentials)
    except JWTError:
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    if payload.get("type") != "access":
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    user_id = payload.get("sub")
    if not user_id:
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    user = await db.scalar(select(User).where(User.id == UUID(user_id)))
    if not user or not user.is_active:
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    return user


async def verify_api_key(
    x_flagops_key: str | None = Header(default=None, alias="X-FlagOps-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Validate X-FlagOps-Key API key header, return ApiKey with environment attached."""
    if not x_flagops_key:
        raise FlagOpsError(
            code="UNAUTHORIZED", message="Missing X-FlagOps-Key header", status_code=401
        )

    key_hash = hashlib.sha256(x_flagops_key.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    api_key = await db.scalar(
        select(ApiKey).options(selectinload(ApiKey.environment)).where(ApiKey.key_hash == key_hash)
    )

    if not api_key or api_key.revoked_at is not None:
        raise FlagOpsError(
            code="UNAUTHORIZED", message="Invalid or revoked API key", status_code=401
        )

    if api_key.expires_at is not None and api_key.expires_at < now:
        raise FlagOpsError(code="UNAUTHORIZED", message="Expired API key", status_code=401)

    return api_key
