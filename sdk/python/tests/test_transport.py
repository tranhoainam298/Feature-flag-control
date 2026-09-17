"""Unit tests for FlagOps SDK HTTP Transport."""

import httpx
import pytest

from flagops.errors import TransportError
from flagops.transport import BACKOFF_DELAYS, Transport, calculate_backoff_delay


def test_calculate_backoff_delay():
    """Verify backoff sequence follows [1, 2, 4, 8, 16, 32, 60] with ±20% jitter."""
    for idx, expected_base in enumerate(BACKOFF_DELAYS):
        for _ in range(20):
            val = calculate_backoff_delay(idx, jitter_factor=0.2)
            assert 0.8 * expected_base <= val <= 1.2 * expected_base

    # Capped at 60s for higher indices
    val_high = calculate_backoff_delay(10, jitter_factor=0.2)
    assert 0.8 * 60.0 <= val_high <= 1.2 * 60.0


def test_transport_fetch_ruleset_success():
    """Test fetch_ruleset parses 200 OK and extracts ETag."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/eval/v1/ruleset"
        assert request.headers.get("X-FlagOps-Key") == "test-key"
        return httpx.Response(
            status_code=200,
            json={"environmentId": "env-1", "rulesetVersion": 1, "flags": {}},
            headers={"ETag": '"v1"'},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = Transport(api_key="test-key", base_url="http://testserver", http_client=client)

    status, data, etag = transport.fetch_ruleset()
    assert status == 200
    assert data is not None
    assert data["rulesetVersion"] == 1
    assert etag == "v1"


def test_transport_fetch_ruleset_304_not_modified():
    """Test fetch_ruleset handles 304 Not Modified when ETag matches."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("If-None-Match") == '"v1"'
        return httpx.Response(status_code=304, headers={"ETag": '"v1"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = Transport(api_key="test-key", base_url="http://testserver", http_client=client)

    status, data, etag = transport.fetch_ruleset(etag="v1")
    assert status == 304
    assert data is None
    assert etag == "v1"


def test_transport_fetch_ruleset_error():
    """Test fetch_ruleset raises TransportError on HTTP 500."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = Transport(api_key="test-key", base_url="http://testserver", http_client=client)

    with pytest.raises(TransportError) as exc_info:
        transport.fetch_ruleset()
    assert exc_info.value.status_code == 500


def test_transport_evaluate_remote():
    """Test remote evaluation POST endpoint."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/eval/v1/flags/test-flag/evaluate"
        return httpx.Response(
            status_code=200,
            json={"value": True, "variant": "on", "reason": "DEFAULT"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = Transport(api_key="test-key", base_url="http://testserver", http_client=client)

    res = transport.evaluate_remote("test-flag", {"userId": "123"})
    assert res["value"] is True
    assert res["variant"] == "on"


def test_transport_fetch_config():
    """Test fetching config namespace via GET /eval/v1/config/{namespace}."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/eval/v1/config/billing"
        return httpx.Response(
            status_code=200,
            json={"version": 1, "namespace": "billing", "configs": {"timeout": 3000}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = Transport(api_key="test-key", base_url="http://testserver", http_client=client)

    configs = transport.fetch_config("billing")
    assert configs == {"timeout": 3000}
