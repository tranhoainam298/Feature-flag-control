"""Auth API router — register, login, refresh, logout, me."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import login_user, logout_user, refresh_tokens, register_user

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user",
)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    return await register_user(db, data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access + refresh tokens",
)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await login_user(db, data.email, data.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using refresh token",
)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await refresh_tokens(db, data.refresh_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Logout and revoke refresh token",
)
async def logout(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await logout_user(db, user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
