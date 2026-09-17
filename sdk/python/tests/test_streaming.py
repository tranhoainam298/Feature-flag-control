"""Unit tests for SSESubscriber and streaming real-time invalidation in Python SDK."""

import json
import threading
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from flagops.client import FlagOpsClient
from flagops.streaming import SSESubscriber
from flagops.transport import Transport


def test_sse_subscriber_receives_ruleset_updated():
    """Verify SSESubscriber parses event frames and calls on_ruleset_updated callback."""
    events_received = []

    def callback(data):
        events_received.append(data)

    sse_lines = [
        b"event: heartbeat\r\n",
        b"data: {}\r\n",
        b"\r\n",
        b"event: ruleset_updated\r\n",
        b'data: {"environmentId": "env-dev", "rulesetVersion": 42}\r\n',
        b"\r\n",
    ]

    event_done = threading.Event()

    class MockStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_lines(self):
            for line in sse_lines:
                yield line.decode("utf-8")
            event_done.wait(2.0)

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.stream.return_value = MockStreamResponse()

    transport = Transport(
        api_key="test-key",
        base_url="http://testserver",
        http_client=mock_client,
    )

    subscriber = SSESubscriber(transport=transport, on_ruleset_updated=callback)
    subscriber.start()

    # Wait briefly for thread to process mock lines
    time.sleep(0.1)
    event_done.set()
    subscriber.stop()

    assert len(events_received) == 1
    assert events_received[0] == {"environmentId": "env-dev", "rulesetVersion": 42}
    assert subscriber.is_connected() is False


def test_sse_subscriber_reconnection_backoff(caplog):
    """Verify SSESubscriber logs warning and retries on stream error."""
    mock_client = MagicMock(spec=httpx.Client)
    # Fail first time with HTTP 503, then stop
    fail_res = MagicMock()
    fail_res.status_code = 503
    mock_client.stream.return_value.__enter__.return_value = fail_res
    mock_client.stream.return_value.__exit__.return_value = None

    transport = Transport(
        api_key="test-key",
        base_url="http://testserver",
        http_client=mock_client,
    )

    subscriber = SSESubscriber(transport=transport, on_ruleset_updated=lambda x: None)

    with patch("flagops.streaming.calculate_backoff_delay", return_value=0.05):
        subscriber.start()
        time.sleep(0.2)
        subscriber.stop()

    assert "SSE connection failed with HTTP 503" in caplog.text


def test_client_skips_duplicate_fetch_on_older_or_equal_version(sample_ruleset):
    """Verify FlagOpsClient skips fetching when incoming version is <= cached version."""
    fetch_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_calls
        if "/eval/v1/ruleset" in request.url.path:
            fetch_calls += 1
            return httpx.Response(status_code=200, json=sample_ruleset, headers={"ETag": '"v42"'})
        return httpx.Response(status_code=200, json={})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FlagOpsClient(
        api_key="test-key",
        base_url="http://testserver",
        http_client=mock_http,
        enable_streaming=False,  # Manually trigger callback
    )
    try:
        # Initial fetch
        assert fetch_calls == 1
        assert client._cache.get().ruleset_version == 42

        # Trigger update with older version -> ignored
        client._on_stream_update({"rulesetVersion": 41})
        assert fetch_calls == 1

        # Trigger update with equal version -> ignored
        client._on_stream_update({"rulesetVersion": 42})
        assert fetch_calls == 1

        # Trigger update with newer version -> triggers fetch
        client._on_stream_update({"rulesetVersion": 43})
        assert fetch_calls == 2
    finally:
        client.close()
