"""Unit tests for FlagOpsClient public API and fail-safe behavior."""

import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from flagops.client import FlagOpsClient
from flagops.engine.types import Reason
from flagops.errors import TransportError


def test_is_enabled_with_mock_ruleset(sample_ruleset):
    """Verify is_enabled evaluates accurately against mock ruleset."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(
        api_key="test-key",
        base_url="http://testserver",
        http_client=mock_http,
        polling_interval=60.0,
    )
    try:
        # Default off variation
        assert client.is_enabled("checkout-v2", {"userId": "regular-user"}) is False

        # Beta user matches targeting rule
        assert client.is_enabled("checkout-v2", {"targetingKey": "u2", "is_beta": True}) is True

        # Individual override
        assert client.is_enabled("checkout-v2", {"targetingKey": "user-vip"}) is True

        # Disabled flag
        assert client.is_enabled("disabled-flag") is False

        # Non-existent flag returns default
        assert client.is_enabled("non-existent-flag", default=True) is True
        assert client.is_enabled("non-existent-flag", default=False) is False
    finally:
        client.close()


def test_get_typed_variants(sample_ruleset):
    """Verify get_string, get_number, get_json, get_variant."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(api_key="test-key", base_url="http://testserver", http_client=mock_http)
    try:
        # String
        assert client.get_string("banner-color", default="green") == "blue"

        # Number
        assert client.get_number("max-items", default=10) == 50

        # JSON
        assert client.get_json("feature-config", default={}) == {"theme": "dark", "retries": 3}

        # Variant key
        assert client.get_variant("banner-color", default="none") == "blue"

        # Evaluation details
        eval_res = client.get_evaluation("banner-color")
        assert eval_res.value == "blue"
        assert eval_res.variant == "blue"
        assert eval_res.reason == Reason.DEFAULT
    finally:
        client.close()


def test_in_process_mode_1000_evaluations_calls_server_once(sample_ruleset):
    """in_process mode: 1000 evaluations must execute in-memory with only 1 server transport call."""
    server_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal server_calls
        if request.url.path == "/eval/v1/ruleset":
            server_calls += 1
            return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})
        return httpx.Response(status_code=200, json={"status": "ok"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(
        api_key="test-key",
        base_url="http://testserver",
        mode="in_process",
        http_client=mock_http,
        polling_interval=60.0,
    )
    try:
        assert server_calls == 1

        for _ in range(1000):
            res = client.is_enabled("checkout-v2", {"is_beta": True})
            assert res is True

        # Exactly 1 transport call was made for all 1000 evaluations!
        assert server_calls == 1
    finally:
        client.close()


def test_server_returns_500_continues_using_cached_ruleset(sample_ruleset, caplog):
    """Server returns 500 on refresh: client continues serving cached ruleset without failing."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})
        # Subsequent calls fail with HTTP 500
        return httpx.Response(status_code=500, text="Internal Server Error")

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(
        api_key="test-key",
        base_url="http://testserver",
        http_client=mock_http,
        polling_interval=60.0,
    )
    try:
        assert client.is_enabled("checkout-v2", {"is_beta": True}) is True

        # Simulate polling refresh error
        with caplog.at_level(logging.WARNING):
            client._fetch_and_update_ruleset()

        # Flag evaluation still works using last cached ruleset!
        assert client.is_enabled("checkout-v2", {"is_beta": True}) is True
        assert "Using last cached ruleset" in caplog.text
    finally:
        client.close()


def test_never_connected_returns_default_without_raising(caplog):
    """SDK never connected to server: returns default value, never raises exception, logs warning once."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=503, text="Service Unavailable")

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))

    with caplog.at_level(logging.WARNING):
        client = FlagOpsClient(
            api_key="bad-key",
            base_url="http://dead-server",
            http_client=mock_http,
            polling_interval=60.0,
        )

    try:
        # Never raises exceptions!
        assert client.is_enabled("any-flag", default=False) is False
        assert client.is_enabled("any-flag", default=True) is True
        assert client.get_string("any-flag", default="fallback") == "fallback"
        assert client.get_number("any-flag", default=99) == 99
        assert client.get_json("any-flag", default={"a": 1}) == {"a": 1}

        eval_res = client.get_evaluation("any-flag", default="def")
        assert eval_res.reason == Reason.ERROR
        assert eval_res.value == "def"
    finally:
        client.close()


def test_etag_304_keeps_cache_unchanged(sample_ruleset):
    """Server returns 304 Not Modified: cache remains unchanged."""
    fetch_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_count
        fetch_count += 1
        if fetch_count == 1:
            return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})
        if request.headers.get("If-None-Match") == '"v42"':
            return httpx.Response(status_code=304, headers={"ETag": '"v42"'})
        return httpx.Response(status_code=200, json=sample_ruleset)

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(api_key="test-key", base_url="http://testserver", http_client=mock_http)
    try:
        assert client._cache.get_etag() == "v42"

        # Poll again: sends ETag, gets 304
        success = client._fetch_and_update_ruleset()
        assert success is True
        assert client._cache.get_etag() == "v42"
        assert client._cache.get().ruleset_version == 42
    finally:
        client.close()


def test_remote_mode_evaluates_via_api():
    """Verify mode='remote' evaluates flags via server API."""
    called_keys = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "/evaluate" in request.url.path:
            flag_key = request.url.path.split("/")[-2]
            called_keys.append(flag_key)
            return httpx.Response(
                status_code=200,
                json={"value": "remote-val", "variant": "rem", "reason": "TARGETING_MATCH"},
            )
        return httpx.Response(status_code=200, json={})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(
        api_key="test-key",
        base_url="http://testserver",
        mode="remote",
        http_client=mock_http,
    )
    try:
        val = client.get_string("remote-flag", default="def")
        assert val == "remote-val"
        assert "remote-flag" in called_keys
    finally:
        client.close()


def test_get_config_namespace():
    """Verify get_config returns configs dict or empty dict on error."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/eval/v1/config/app-settings":
            return httpx.Response(
                status_code=200,
                json={"version": 1, "namespace": "app-settings", "configs": {"timeout": 5000}},
            )
        return httpx.Response(status_code=404, json={"detail": "Not Found"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(api_key="test-key", base_url="http://testserver", http_client=mock_http)
    try:
        cfg = client.get_config("app-settings")
        assert cfg == {"timeout": 5000}

        empty_cfg = client.get_config("missing-namespace")
        assert empty_cfg == {}
    finally:
        client.close()


def test_context_manager_syntax(sample_ruleset):
    """Verify context manager automatically closes client."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))

    with FlagOpsClient(api_key="test-key", base_url="http://testserver", http_client=mock_http) as client:
        assert client.is_enabled("checkout-v2", {"is_beta": True}) is True

    assert client._stop_event.is_set()


def test_get_number_edge_cases():
    """Verify get_number handles float strings, invalid conversions, and boolean rejection."""
    sample = {
        "environmentId": "e1",
        "rulesetVersion": 1,
        "flags": {
            "f-float": {
                "flagKey": "f-float",
                "enabled": True,
                "defaultVariation": {"key": "f", "value": "3.14"},
            },
            "f-bool": {
                "flagKey": "f-bool",
                "enabled": True,
                "defaultVariation": {"key": "b", "value": True},
            },
            "f-invalid": {
                "flagKey": "f-invalid",
                "enabled": True,
                "defaultVariation": {"key": "inv", "value": "not-a-number"},
            },
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=sample)

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    with FlagOpsClient(api_key="test-key", base_url="http://testserver", http_client=mock_http) as client:
        assert client.get_number("f-float", default=0) == 3.14
        assert client.get_number("f-bool", default=42) == 42
        assert client.get_number("f-invalid", default=99) == 99
        assert client.get_boolean("f-bool", default=False) is True

