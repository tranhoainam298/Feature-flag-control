import redis.asyncio as redis

from app.core.config import settings


def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def check_redis_health() -> bool:
    client = get_redis_client()
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()
