"""Evaluation Event Batching and Flushing for FlagOps SDK."""

import logging
import threading
import time
from typing import Any

from .transport import Transport

logger = logging.getLogger("flagops.events")


class EventBatcher:
    """Thread-safe batch event collector that periodically flushes events to the server."""

    def __init__(
        self,
        transport: Transport,
        flush_interval: float = 10.0,
        max_buffer: int = 100,
    ) -> None:
        self._transport = transport
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer

        self._lock = threading.Lock()
        self._buffer: list[dict[str, Any]] = []

        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="flagops-event-flusher",
            daemon=True,
        )
        self._worker_thread.start()

    def track(
        self,
        flag_key: str,
        value: Any,
        variant: str,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record an evaluation event into the batch buffer."""
        event = {
            "flagKey": flag_key,
            "value": value,
            "variant": variant,
            "reason": str(reason),
            "context": context or {},
            "timestamp": int(time.time() * 1000),
        }

        should_flush = False
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self._max_buffer:
                should_flush = True

        if should_flush:
            self.flush()

    def flush(self) -> None:
        """Immediately drain and send all buffered events to the server."""
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        try:
            self._transport.send_events(batch)
        except Exception as exc:
            logger.warning(f"Error flushing evaluation events ({len(batch)} items): {exc}")

    def _worker_loop(self) -> None:
        """Background thread loop flushing events every flush_interval seconds."""
        while not self._stop_event.wait(timeout=self._flush_interval):
            try:
                self.flush()
            except Exception as exc:
                logger.warning(f"Error in background event flusher: {exc}")

    def close(self) -> None:
        """Stop background worker and flush all remaining events."""
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self.flush()
