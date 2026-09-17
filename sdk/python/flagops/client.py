"""Official FlagOps Python SDK Client.

Features:
- In-process evaluation with sub-millisecond local latency.
- Remote evaluation mode option.
- Strict fail-safe architecture: never raises exceptions to client code.
- Thread-safe in-memory caching.
- HTTP ETag / 304 caching and exponential backoff with jitter.
- Batched evaluation event tracking and flushing.
"""

import logging
import threading
from typing import Any

import httpx

from .cache import RulesetCache, parse_ruleset
from .engine.evaluator import evaluate
from .engine.types import (
    ErrorCode,
    EvaluationContext,
    EvaluationResult,
    Reason,
)
from .events import EventBatcher
from .streaming import SSESubscriber
from .transport import Transport, calculate_backoff_delay

logger = logging.getLogger("flagops.client")


def _to_evaluation_context(raw: dict[str, Any] | EvaluationContext | None) -> EvaluationContext:
    """Normalize input context dictionary or EvaluationContext."""
    if raw is None:
        return EvaluationContext(targeting_key="", attributes={})
    if isinstance(raw, EvaluationContext):
        return raw

    if "targeting_key" in raw:
        t_key = str(raw["targeting_key"])
        attrs = raw.get("attributes", {})
    elif "targetingKey" in raw:
        t_key = str(raw["targetingKey"])
        attrs = {k: v for k, v in raw.items() if k != "targetingKey"}
    elif "userId" in raw:
        t_key = str(raw["userId"])
        attrs = {k: v for k, v in raw.items() if k != "userId"}
    else:
        t_key = ""
        attrs = raw

    return EvaluationContext(targeting_key=t_key, attributes=attrs)


class FlagOpsClient:
    """FlagOps feature flag and configuration client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        mode: str = "in_process",
        polling_interval: float = 30.0,
        enable_streaming: bool = True,
        timeout: float = 2.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Initialize FlagOps client.

        Args:
            api_key: Environment API Key (fo_srv_... or fo_cli_...).
            base_url: Base URL of FlagOps server (e.g. https://flagops.example.com).
            mode: "in_process" (local evaluation) or "remote" (server API evaluation).
            polling_interval: Seconds between ruleset refresh polls in in_process mode.
            enable_streaming: Whether to enable SSE real-time streaming updates.
            timeout: Network request timeout in seconds for all calls.
            http_client: Optional pre-configured httpx.Client for testing/mocking.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.mode = mode.lower()
        self.polling_interval = polling_interval
        self.enable_streaming = enable_streaming
        self.timeout = timeout

        self._transport = Transport(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            http_client=http_client,
        )
        self._cache = RulesetCache()
        self._events = EventBatcher(self._transport)
        self._streaming = SSESubscriber(
            transport=self._transport,
            on_ruleset_updated=self._on_stream_update,
        )

        self._fetch_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._has_warned_uninitialized = False
        self._consecutive_failures = 0
        self._polling_thread: threading.Thread | None = None

        if self.mode == "in_process":
            # Initial fetch (blocking with timeout)
            self._fetch_and_update_ruleset(is_initial=True)

            # Start background poller
            self._polling_thread = threading.Thread(
                target=self._polling_loop,
                name="flagops-ruleset-poller",
                daemon=True,
            )
            self._polling_thread.start()

            if self.enable_streaming:
                self._streaming.start()
        else:
            # Remote mode is immediately ready
            self._ready_event.set()

    # ──────────────────────────────────────────────────────────────────────────
    # BACKGROUND WORKERS
    # ──────────────────────────────────────────────────────────────────────────

    def _on_stream_update(self, payload: dict[str, Any] | None = None) -> None:
        """Callback invoked when SSE receives a ruleset_updated event."""
        if payload and isinstance(payload, dict) and "rulesetVersion" in payload:
            incoming_ver = int(payload["rulesetVersion"])
            current_rs = self._cache.get()
            if current_rs and current_rs.ruleset_version >= incoming_ver:
                logger.debug(
                    "Skipping duplicate fetch: cached version (%d) >= incoming (%d)",
                    current_rs.ruleset_version,
                    incoming_ver,
                )
                return
        self._fetch_and_update_ruleset()

    def _fetch_and_update_ruleset(self, is_initial: bool = False) -> bool:
        """Fetch ruleset from server and update local cache.

        Never raises exceptions; updates consecutive failure count and logs warnings.
        Thread-safe: uses _fetch_lock to avoid concurrent duplicate requests.
        """
        if not self._fetch_lock.acquire(blocking=True, timeout=3.0):
            return False

        try:
            status, payload, new_etag = self._transport.fetch_ruleset(
                etag=self._cache.get_etag()
            )

            if status == 304:
                # Cache is fresh
                self._consecutive_failures = 0
                self._ready_event.set()
                return True

            if status == 200 and payload:
                ruleset = parse_ruleset(payload)
                self._cache.update(ruleset, etag=new_etag)
                self._consecutive_failures = 0
                self._ready_event.set()
                return True

            return False
        except Exception as exc:
            self._consecutive_failures += 1

            if self._cache.is_initialized():
                # Fail-safe: keep existing cache
                logger.warning(
                    f"Ruleset polling failed ({self._consecutive_failures}x): {exc}. "
                    "Using last cached ruleset."
                )
            else:
                # Never loaded yet: warn once
                if not self._has_warned_uninitialized:
                    logger.warning(
                        f"Initial ruleset fetch failed: {exc}. SDK will use fallback default values."
                    )
                    self._has_warned_uninitialized = True
            return False
        finally:
            self._fetch_lock.release()

    def _polling_loop(self) -> None:
        """Background thread polling /eval/v1/ruleset with ETag and exponential backoff."""
        while not self._stop_event.is_set():
            # If healthy: poll every polling_interval. If error: backoff
            if self._consecutive_failures > 0:
                sleep_time = calculate_backoff_delay(self._consecutive_failures)
            else:
                sleep_time = self.polling_interval

            if self._stop_event.wait(timeout=sleep_time):
                break

            self._fetch_and_update_ruleset()

    # ──────────────────────────────────────────────────────────────────────────
    # EVALUATION API (FAIL-SAFE: NEVER RAISES)
    # ──────────────────────────────────────────────────────────────────────────

    def get_evaluation(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: Any = None,
    ) -> EvaluationResult:
        """Evaluate a flag and return full EvaluationResult including reason code."""
        norm_context = _to_evaluation_context(context)
        raw_dict = (
            context
            if isinstance(context, dict)
            else (context.attributes if isinstance(context, EvaluationContext) else {})
        )

        try:
            if self.mode == "remote":
                res_dict = self._transport.evaluate_remote(flag_key, raw_dict)
                reason_val = res_dict.get("reason", Reason.DEFAULT)
                err_code = res_dict.get("error_code")
                res = EvaluationResult(
                    flag_key=flag_key,
                    value=res_dict.get("value", default),
                    variant=res_dict.get("variant", ""),
                    reason=Reason(reason_val) if reason_val in Reason._value2member_map_ else reason_val,
                    error_code=ErrorCode(err_code) if err_code in ErrorCode._value2member_map_ else err_code,
                    flag_metadata=res_dict.get("flag_metadata"),
                )
            else:
                ruleset = self._cache.get()
                if ruleset is None:
                    # Ruleset not loaded yet
                    if not self._has_warned_uninitialized:
                        logger.warning(
                            "Ruleset has not been loaded yet. Evaluation returning default value."
                        )
                        self._has_warned_uninitialized = True

                    res = EvaluationResult(
                        flag_key=flag_key,
                        value=default,
                        variant="",
                        reason=Reason.ERROR,
                        error_code=ErrorCode.GENERAL_ERROR,
                        error_message="Ruleset not loaded",
                    )
                else:
                    res = evaluate(
                        ruleset=ruleset,
                        context=norm_context,
                        flag_key=flag_key,
                        default_value=default,
                    )

            # Track evaluation event
            self._events.track(
                flag_key=flag_key,
                value=res.value,
                variant=res.variant,
                reason=str(res.reason),
                context=raw_dict,
            )
            return res

        except Exception as exc:
            logger.warning(
                f"Unexpected error evaluating flag '{flag_key}': {exc}. Returning default value."
            )
            fallback = EvaluationResult(
                flag_key=flag_key,
                value=default,
                variant="",
                reason=Reason.ERROR,
                error_code=ErrorCode.GENERAL_ERROR,
                error_message=str(exc),
            )
            self._events.track(
                flag_key=flag_key,
                value=default,
                variant="",
                reason=str(Reason.ERROR),
                context=raw_dict,
            )
            return fallback

    def is_enabled(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: bool = False,
    ) -> bool:
        """Check if a boolean feature flag is enabled."""
        result = self.get_evaluation(flag_key, context=context, default=default)
        return bool(result.value)

    def get_boolean(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: bool = False,
    ) -> bool:
        """Evaluate a boolean flag value."""
        result = self.get_evaluation(flag_key, context=context, default=default)
        return bool(result.value)

    def get_string(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: str = "",
    ) -> str:
        """Evaluate a string flag variation value."""
        result = self.get_evaluation(flag_key, context=context, default=default)
        if result.value is None:
            return default
        return str(result.value)

    def get_number(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: int | float = 0,
    ) -> int | float:
        """Evaluate a numeric flag variation value."""
        result = self.get_evaluation(flag_key, context=context, default=default)
        if isinstance(result.value, (int, float)) and not isinstance(result.value, bool):
            return result.value
        try:
            val_str = str(result.value)
            return float(val_str) if "." in val_str else int(val_str)
        except (ValueError, TypeError):
            return default

    def get_json(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: Any = None,
    ) -> Any:
        """Evaluate a JSON flag variation value."""
        result = self.get_evaluation(flag_key, context=context, default=default)
        return result.value if result.value is not None else default

    def get_variant(
        self,
        flag_key: str,
        context: dict[str, Any] | EvaluationContext | None = None,
        default: str = "",
    ) -> str:
        """Retrieve the matched variant key."""
        result = self.get_evaluation(flag_key, context=context, default=default)
        return result.variant if result.variant else default

    def get_config(self, namespace: str) -> dict[str, Any]:
        """Fetch published key-value configurations for a namespace.

        Never raises exceptions; returns empty dict on failure.
        """
        try:
            return self._transport.fetch_config(namespace)
        except Exception as exc:
            logger.warning(f"Error reading config namespace '{namespace}': {exc}")
            return {}

    # ──────────────────────────────────────────────────────────────────────────
    # LIFECYCLE MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def wait_for_ready(self, timeout: float = 5.0) -> bool:
        """Block until the SDK has loaded ruleset or timeout expires."""
        return self._ready_event.wait(timeout=timeout)

    @property
    def is_ready(self) -> bool:
        """Check if the client has loaded its ruleset or is ready for evaluation."""
        return self._ready_event.is_set()

    def close(self) -> None:
        """Shut down the SDK: stop polling, streaming, flush events, and close connections."""
        self._stop_event.set()

        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=2.0)

        self._streaming.stop()
        self._events.close()
        self._transport.close()
        logger.info("FlagOps client shut down successfully.")

    def __enter__(self) -> "FlagOpsClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
