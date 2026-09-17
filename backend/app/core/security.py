"""Password hashing (Argon2id) and JWT token utilities."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import PyJWTError as JWTError
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Password hashing (Argon2id) ---

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# --- JWT ---

_DEV_SECRET = "change-me-to-a-random-string-at-least-32-chars"


def _get_secret_key() -> str:
    settings.validate_production_security()
    key = settings.SECRET_KEY
    if key == _DEV_SECRET and not settings.DEBUG:
        logger.warning(
            "SECRET_KEY is set to default dev value in non-debug mode! "
            "Set a strong SECRET_KEY environment variable for production."
        )
    return key


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Return (raw_token, token_hash) — only store the hash in DB."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = secrets.token_urlsafe(32)
    payload = {"sub": user_id, "exp": expire, "type": "refresh", "jti": jti}
    raw = jwt.encode(payload, _get_secret_key(), algorithm=settings.JWT_ALGORITHM)
    return raw, hash_token(raw)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError on any failure."""
    return jwt.decode(token, _get_secret_key(), algorithms=[settings.JWT_ALGORITHM])


__all__ = [
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "hash_token",
    "verify_password",
]
