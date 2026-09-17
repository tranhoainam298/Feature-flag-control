"""Ruleset cache, Pub/Sub invalidation, and rate limiting via Redis.

Every method is fail-open: Redis errors log a warning and fall through.
"""

import json
import logging
import time
from uuid import UUID

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)


def _cache_key(env_id: UUID) -> str:
    return f"ruleset:{env_id}"


def _pubsub_channel(env_id: UUID) -> str:
    return f"flagops:ruleset:{env_id}"


def _rate_key(api_key_id: UUID) -> str:
    minute = int(time.time()) // 60
    return f"ratelimit:{api_key_id}:{minute}"


async def get_cached_ruleset(env_id: UUID) -> dict | None:
    """Return cached ruleset dict or None on miss / Redis down."""
    pool = get_redis_pool()
    if pool is None:
        return None
    try:
        raw = await pool.get(_cache_key(env_id))
        if raw is not None:
            return json.loads(raw)
    except (RedisError, OSError) as exc:
        logger.warning("Redis cache read failed for env %s: %s", env_id, exc)
    return None


async def set_cached_ruleset(env_id: UUID, payload: dict) -> None:
    """Write ruleset dict to cache with TTL."""
    pool = get_redis_pool()
    if pool is None:
        return
    try:
        await pool.set(
            _cache_key(env_id),
            json.dumps(payload, default=str),
            ex=settings.RULESET_CACHE_TTL_SECONDS,
        )
    except (RedisError, OSError) as exc:
        logger.warning("Redis cache write failed for env %s: %s", env_id, exc)


async def invalidate(env_id: UUID, version: int = 0) -> None:
    """Delete cached ruleset and publish change notification."""
    pool = get_redis_pool()
    if pool is None:
        return
    try:
        await pool.delete(_cache_key(env_id))
        payload = json.dumps({"environmentId": str(env_id), "rulesetVersion": version})
        await pool.publish(_pubsub_channel(env_id), payload)
    except (RedisError, OSError) as exc:
        logger.warning("Redis invalidation failed for env %s: %s", env_id, exc)


async def check_rate_limit(api_key_id: UUID) -> tuple[bool, int]:
    """Sliding window rate limit. Returns (allowed, remaining).

    Fail-open: if Redis is down, allow the request.
    """
    pool = get_redis_pool()
    if pool is None:
        return True, settings.EVAL_RATE_LIMIT_PER_MINUTE

    limit = settings.EVAL_RATE_LIMIT_PER_MINUTE
    key = _rate_key(api_key_id)

    try:
        current = await pool.incr(key)
        if current == 1:
            await pool.expire(key, 60)
        remaining = max(0, limit - current)
        return current <= limit, remaining
    except (RedisError, OSError) as exc:
        logger.warning("Redis rate limit check failed for key %s: %s", api_key_id, exc)
        return True, limit
