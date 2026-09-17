"""HTTP Transport client for FlagOps SDK.

Handles network requests to the FlagOps evaluation server with strict timeouts,
ETag caching support, and exponential backoff with jitter.
"""

import logging
import random
from typing import Any

import httpx

from .errors import TransportError

logger = logging.getLogger("flagops.transport")

BACKOFF_DELAYS = [1, 2, 4, 8, 16, 32, 60]


def calculate_backoff_delay(failure_count: int, jitter_factor: float = 0.2) -> float:
    """Calculate exponential backoff delay with ±20% jitter.

    Sequence: 1, 2, 4, 8, 16, 32, 60 seconds (capped at 60s).
    """
    idx = min(max(0, failure_count), len(BACKOFF_DELAYS) - 1)
    base = float(BACKOFF_DELAYS[idx])
    # Jitter between -20% and +20%
    jitter = random.uniform(-jitter_factor, jitter_factor) * base
    return max(0.1, base + jitter)


class Transport:
    """Synchronous HTTP client for FlagOps server communication."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 2.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._headers = {
            "X-FlagOps-Key": self.api_key,
            "User-Agent": "FlagOps-Python-SDK/0.1.0",
            "Accept": "application/json",
        }

        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            headers=self._headers,
            timeout=httpx.Timeout(self.timeout),
        )

    def _request_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = dict(self._headers)
        if extra:
            h.update(extra)
        return h

    def fetch_ruleset(
        self, etag: str | None = None
    ) -> tuple[int, dict[str, Any] | None, str | None]:
        """Fetch the environment ruleset from /eval/v1/ruleset.

        Supports HTTP ETag and 304 Not Modified.

        Returns:
            tuple of (status_code, payload_dict_or_None, new_etag_or_None)
        """
        extra_headers: dict[str, str] = {}
        if etag:
            extra_headers["If-None-Match"] = f'"{etag.strip().strip('"')}"'

        url = f"{self.base_url}/eval/v1/ruleset"
        try:
            res = self._client.get(url, headers=self._request_headers(extra_headers))
        except Exception as exc:
            raise TransportError(f"Network error fetching ruleset: {exc}") from exc

        if res.status_code == 304:
            return 304, None, etag

        if res.status_code != 200:
            raise TransportError(
                f"Failed to fetch ruleset: HTTP {res.status_code} - {res.text[:200]}",
                status_code=res.status_code,
            )

        raw_etag = res.headers.get("ETag")
        clean_etag = raw_etag.strip().strip('"') if raw_etag else None

        try:
            payload = res.json()
        except Exception as exc:
            raise TransportError(f"Invalid JSON in ruleset response: {exc}") from exc

        return 200, payload, clean_etag

    def evaluate_remote(self, flag_key: str, context: dict[str, Any]) -> dict[str, Any]:
        """Perform remote flag evaluation via POST /eval/v1/flags/{key}/evaluate."""
        url = f"{self.base_url}/eval/v1/flags/{flag_key}/evaluate"
        try:
            res = self._client.post(
                url,
                json={"context": context},
                headers=self._request_headers(),
            )
        except Exception as exc:
            raise TransportError(f"Network error evaluating flag '{flag_key}': {exc}") from exc

        if res.status_code != 200:
            raise TransportError(
                f"Failed remote evaluation for '{flag_key}': HTTP {res.status_code}",
                status_code=res.status_code,
            )

        try:
            return res.json()
        except Exception as exc:
            raise TransportError(f"Invalid JSON from evaluate: {exc}") from exc

    def send_events(self, events: list[dict[str, Any]]) -> bool:
        """Send a batch of evaluation events via POST /eval/v1/events."""
        if not events:
            return True

        url = f"{self.base_url}/eval/v1/events"
        try:
            res = self._client.post(
                url,
                json={"events": events},
                headers=self._request_headers(),
            )
            return res.status_code in (200, 201, 202)
        except Exception as exc:
            logger.warning(f"Failed to send evaluation events batch ({len(events)}): {exc}")
            return False

    def fetch_config(self, namespace: str) -> dict[str, Any]:
        """Fetch published configurations for a namespace via GET /eval/v1/config/{namespace}."""
        url = f"{self.base_url}/eval/v1/config/{namespace}"
        try:
            res = self._client.get(url, headers=self._request_headers())
        except Exception as exc:
            raise TransportError(
                f"Network error fetching config for namespace '{namespace}': {exc}"
            ) from exc

        if res.status_code != 200:
            raise TransportError(
                f"Failed to fetch config for '{namespace}': HTTP {res.status_code}",
                status_code=res.status_code,
            )

        try:
            data = res.json()
            return data.get("configs", {})
        except Exception as exc:
            raise TransportError(f"Invalid JSON in config response: {exc}") from exc

    def close(self) -> None:
        """Close underlying HTTP client."""
        try:
            self._client.close()
        except Exception:
            pass
