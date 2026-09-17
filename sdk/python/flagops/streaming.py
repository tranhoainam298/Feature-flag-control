"""Server-Sent Events (SSE) Streaming subscriber for FlagOps SDK.

Maintains a background SSE connection to /eval/v1/stream for real-time
ruleset invalidation. Automatically falls back to polling and reconnects
with exponential backoff upon network interruption.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

from .transport import Transport, calculate_backoff_delay

logger = logging.getLogger("flagops.streaming")


class SSESubscriber:
    """Background listener for /eval/v1/stream Server-Sent Events."""

    def __init__(
        self,
        transport: Transport,
        on_ruleset_updated: Callable[[dict[str, Any] | None], None],
    ) -> None:
        """Initialize SSE Subscriber.

        Args:
            transport: SDK Transport instance providing HTTP client and auth credentials.
            on_ruleset_updated: Callback invoked when a ruleset_updated event is received.
        """
        self._transport = transport
        self._on_ruleset_updated = on_ruleset_updated
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._is_connected = False
        self._last_heartbeat = 0.0
        self._active_response: httpx.Response | None = None

    def start(self) -> None:
        """Start the background SSE listener thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._stream_loop,
            name="flagops-sse-subscriber",
            daemon=True,
        )
        self._thread.start()
        logger.debug("SSE subscriber thread started.")

    def stop(self) -> None:
        """Signal the listener thread to shut down cleanly."""
        self._stop_event.set()
        if self._active_response is not None:
            try:
                self._active_response.close()
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._is_connected = False
        logger.debug("SSE subscriber stopped.")

    def is_alive(self) -> bool:
        """Check if listener thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def is_connected(self) -> bool:
        """Check if the SSE connection is currently established."""
        return self._is_connected

    def _stream_loop(self) -> None:
        """Continuous reconnection and stream processing loop."""
        attempt = 0
        url = f"{self._transport.base_url}/eval/v1/stream"
        headers = self._transport._request_headers()

        while not self._stop_event.is_set():
            try:
                logger.debug("Connecting to SSE stream at %s...", url)
                # Use client streaming request with no timeout on read
                with self._transport._client.stream(
                    "GET",
                    url,
                    headers=headers,
                    timeout=httpx.Timeout(connect=self._transport.timeout, read=None, write=5.0, pool=5.0),
                ) as response:
                    if response.status_code != 200:
                        logger.warning(
                            "SSE connection failed with HTTP %d. Reverting to polling fallback.",
                            response.status_code,
                        )
                        self._is_connected = False
                        attempt += 1
                        delay = calculate_backoff_delay(attempt)
                        self._stop_event.wait(delay)
                        continue

                    self._active_response = response
                    self._is_connected = True
                    attempt = 0
                    logger.info("SSE stream connection established for real-time updates.")

                    current_event = "message"
                    current_data: list[str] = []

                    for line in response.iter_lines():
                        if self._stop_event.is_set():
                            break

                        line = line.rstrip("\r\n")
                        if line.startswith("event:"):
                            current_event = line[len("event:") :].strip()
                        elif line.startswith("data:"):
                            current_data.append(line[len("data:") :].strip())
                        elif line == "":
                            # End of event frame — dispatch
                            raw_payload = "\n".join(current_data)
                            if current_event == "ruleset_updated":
                                parsed_data = None
                                if raw_payload:
                                    try:
                                        parsed_data = json.loads(raw_payload)
                                    except Exception:
                                        pass
                                logger.info(
                                    "Received ruleset_updated SSE notification: %s",
                                    raw_payload,
                                )
                                self._on_ruleset_updated(parsed_data)
                            elif current_event == "heartbeat":
                                self._last_heartbeat = time.time()
                                logger.debug("SSE heartbeat received.")

                            current_event = "message"
                            current_data = []

            except (httpx.HTTPError, OSError, Exception) as exc:
                self._is_connected = False
                if self._stop_event.is_set():
                    break

                attempt += 1
                delay = calculate_backoff_delay(attempt)
                logger.warning(
                    "SSE stream disconnected: %s. Falling back to polling, retrying in %.1fs...",
                    exc,
                    delay,
                )
                self._stop_event.wait(delay)
            finally:
                self._active_response = None
                self._is_connected = False
