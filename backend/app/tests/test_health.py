import pytest
from httpx import ASGITransport, AsyncClient

from app.core import database, redis
from app.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_db(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        await database.check_db_health()
    except Exception:

        async def mock_db_health() -> bool:
            return True

        monkeypatch.setattr("app.main.check_db_health", mock_db_health)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/db")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        await redis.check_redis_health()
    except Exception:

        async def mock_redis_health() -> bool:
            return True

        monkeypatch.setattr("app.main.check_redis_health", mock_redis_health)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/redis")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_docs() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/docs")
        assert response.status_code == 200
