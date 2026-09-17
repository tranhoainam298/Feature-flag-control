"""Server client to query FlagOps server for flag definitions and health data."""

import logging
from typing import Any
import httpx

from flag_scanner.models import ServerFlag

logger = logging.getLogger("flag_scanner.server")


def fetch_server_flags(
    api_url: str,
    api_key: str,
    timeout: float = 5.0,
) -> dict[str, ServerFlag] | None:
    """Fetch feature flag status and debt scores from FlagOps server.

    Returns dict mapping flag_key -> ServerFlag.
    Returns None if server is not reachable or credentials missing (offline mode).
    """
    if not api_url or not api_key:
        return None

    base = api_url.rstrip("/")
    headers = {
        "X-FlagOps-Key": api_key,
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{base}/eval/v1/flag-health", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                flags_map: dict[str, ServerFlag] = {}
                for item in items:
                    key = item.get("flag_key")
                    if key:
                        flags_map[key] = ServerFlag(
                            key=key,
                            state=item.get("state", "ACTIVE"),
                            debt_score=item.get("score", 0),
                            is_temporary=item.get("is_temporary", False),
                            recommendations=item.get("recommendations", []),
                        )
                return flags_map

            logger.warning("Failed to fetch flag health: HTTP %s", resp.status_code)
            return None
    except Exception as exc:
        logger.warning("Could not connect to FlagOps server at %s: %s", api_url, exc)
        return None
