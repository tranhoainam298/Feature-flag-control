"""Redis client — singleton pool with fail-open fallback.

Returns None when REDIS_ENABLED=false. All callers must handle None gracefully.
"""

import asyncio
import logging

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: redis.Redis | None = None
_pool_loop_id: int | None = None


def get_redis_pool() -> redis.Redis | None:
    """Return shared Redis connection pool, or None if Redis is disabled."""
    global _pool, _pool_loop_id
    if not settings.REDIS_ENABLED:
        return None

    try:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)
    except RuntimeError:
        current_loop = None
        current_loop_id = None

    # Reset pool if event loop changed (e.g. across test cases)
    if _pool is not None and current_loop_id is not None and _pool_loop_id != current_loop_id:
        _pool = None

    if _pool is None:
        _pool = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _pool_loop_id = current_loop_id
    return _pool


async def check_redis_health() -> bool:
    pool = get_redis_pool()
    if pool is None:
        return False
    try:
        return bool(await pool.ping())
    except Exception:
        return False


async def close_redis_pool() -> None:
    global _pool, _pool_loop_id
    if _pool is not None:
        try:
            await _pool.aclose()
        except Exception:
            pass
        _pool = None
        _pool_loop_id = None
