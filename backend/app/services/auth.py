"""Auth service — register, login, refresh, logout.

Business logic lives here, NOT in routers.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FlagOpsError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import RegisterRequest

logger = logging.getLogger(__name__)

# Identical error for wrong-password AND user-not-found — prevents user enumeration
_INVALID_CREDENTIALS = FlagOpsError(
    code="UNAUTHORIZED", message="Invalid email or password", status_code=401
)


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    """Create a new user. Raises 409 if email already exists."""
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise FlagOpsError(code="CONFLICT", message="Email already registered", status_code=409)

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()
    logger.info("User %s registered", user.id)
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> dict:
    """Authenticate and return tokens. Error message identical for wrong pw and missing user."""
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        # Hash anyway to prevent timing-based user enumeration
        verify_password(password, hash_password("dummy"))
        raise _INVALID_CREDENTIALS

    if not verify_password(password, user.password_hash):
        raise _INVALID_CREDENTIALS

    if not user.is_active:
        raise _INVALID_CREDENTIALS

    access = create_access_token(str(user.id))
    refresh, refresh_hash = create_refresh_token(str(user.id))

    user.refresh_token_hash = refresh_hash
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("User %s logged in", user.id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


async def refresh_tokens(db: AsyncSession, raw_refresh: str) -> dict:
    """Issue new access+refresh pair. Old refresh token is invalidated (rotation)."""
    from app.core.security import JWTError

    try:
        payload = decode_token(raw_refresh)
    except JWTError:
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    if payload.get("type") != "refresh":
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    user_id = payload.get("sub")
    if not user_id:
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise FlagOpsError(code="UNAUTHORIZED", message="Invalid or expired token", status_code=401)

    # Check that this refresh token hasn't been revoked
    if user.refresh_token_hash != hash_token(raw_refresh):
        raise FlagOpsError(code="UNAUTHORIZED", message="Token has been revoked", status_code=401)

    # Rotate: issue new pair, invalidate old
    access = create_access_token(str(user.id))
    new_refresh, new_hash = create_refresh_token(str(user.id))
    user.refresh_token_hash = new_hash
    await db.flush()

    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


async def logout_user(db: AsyncSession, user: User) -> None:
    """Revoke refresh token by clearing its hash."""
    await db.execute(update(User).where(User.id == user.id).values(refresh_token_hash=None))
    await db.flush()
    logger.info("User %s logged out", user.id)
