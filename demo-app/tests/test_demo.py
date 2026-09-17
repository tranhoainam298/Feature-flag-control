"""Tests for FlagOps Demo Web Application."""

import pytest
from httpx import ASGITransport, AsyncClient

# Import app from demo-app main
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app, sdk_client


@pytest.mark.asyncio
async def test_demo_home_page_returns_200():
    """Verify that GET / returns 200 OK and renders main showcase elements."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "FlagOps Demo Portal" in html
        assert "checkout-v2" in html
        assert "Context Evaluation Playground" in html
        assert "1,000-User Monte Carlo Rollout Simulator" in html


@pytest.mark.asyncio
async def test_demo_evaluate_api():
    """Verify POST /api/evaluate executes context evaluation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/evaluate",
            json={
                "flag_key": "checkout-v2",
                "user_id": "vip_user_1",
                "country": "VN",
                "plan": "premium",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["flag_key"] == "checkout-v2"
        assert "value" in data
        assert "variant" in data
        assert "reason" in data
        assert "latency_us" in data


@pytest.mark.asyncio
async def test_demo_simulate_1000_api():
    """Verify POST /api/simulate-1000 computes distribution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/simulate-1000",
            json={"flag_key": "new-homepage", "sample_size": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sample_size"] == 100
        assert "percentages" in data
        assert "counts" in data
        assert sum(data["counts"].values()) == 100


@pytest.mark.asyncio
async def test_demo_status_api():
    """Verify GET /api/status returns live status for frontend polling."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_ready" in data
        assert "ruleset_version" in data
        assert "checkout_v2_enabled" in data


@pytest.mark.asyncio
async def test_demo_failsafe_when_backend_unreachable(monkeypatch):
    """Verify that when backend network call raises, demo app STILL serves 200."""
    # Force SDK transport to fail
    def mock_fetch_ruleset(*args, **kwargs):
        raise ConnectionError("Backend simulated network failure")

    monkeypatch.setattr(sdk_client._transport, "fetch_ruleset", mock_fetch_ruleset)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "FlagOps Demo Portal" in resp.text
