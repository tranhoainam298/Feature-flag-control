"""Unit tests for EventBatcher."""

import time
from unittest.mock import MagicMock

from flagops.events import EventBatcher
from flagops.transport import Transport


def test_event_batcher_tracks_and_flushes():
    """Verify event tracking and explicit flush."""
    mock_transport = MagicMock(spec=Transport)
    batcher = EventBatcher(transport=mock_transport, flush_interval=10.0, max_buffer=100)

    try:
        batcher.track("flag-1", True, "on", "DEFAULT", {"userId": "u1"})
        batcher.track("flag-2", "blue", "blue", "TARGETING_MATCH", {"userId": "u2"})

        assert mock_transport.send_events.call_count == 0

        batcher.flush()
        assert mock_transport.send_events.call_count == 1
        args, _ = mock_transport.send_events.call_args
        events = args[0]
        assert len(events) == 2
        assert events[0]["flagKey"] == "flag-1"
        assert events[1]["flagKey"] == "flag-2"
    finally:
        batcher.close()


def test_event_batcher_auto_flushes_on_max_buffer():
    """Verify automatic flush when max_buffer size is reached."""
    mock_transport = MagicMock(spec=Transport)
    batcher = EventBatcher(transport=mock_transport, flush_interval=10.0, max_buffer=3)

    try:
        batcher.track("f1", True, "on", "DEFAULT")
        batcher.track("f2", True, "on", "DEFAULT")
        assert mock_transport.send_events.call_count == 0

        # Third item reaches max_buffer=3 -> immediate flush
        batcher.track("f3", True, "on", "DEFAULT")
        assert mock_transport.send_events.call_count == 1
    finally:
        batcher.close()


def test_event_batcher_close_flushes_remaining():
    """Verify close() drains remaining events before stopping worker thread."""
    mock_transport = MagicMock(spec=Transport)
    batcher = EventBatcher(transport=mock_transport, flush_interval=10.0, max_buffer=100)

    batcher.track("f1", True, "on", "DEFAULT")
    assert mock_transport.send_events.call_count == 0

    batcher.close()
    assert mock_transport.send_events.call_count == 1
    assert not batcher._worker_thread.is_alive()
