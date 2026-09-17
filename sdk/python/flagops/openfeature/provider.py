"""OpenFeature Provider for FlagOps.

Adheres strictly to CNCF OpenFeature Specification:
- Extends openfeature.provider.AbstractProvider
- Provides full type resolution: boolean, string, integer, float, object
- Standardized ErrorCode and Reason mapping
- Seamless EvaluationContext translation (targeting_key -> bucketing_key)
- Robust fail-safe design: never throws exceptions, always returns default values
- Wraps FlagOpsClient internally without duplicating evaluation logic
"""

from typing import Any, Mapping, Union
import logging

from openfeature.provider import AbstractProvider, Metadata
from openfeature.flag_evaluation import FlagResolutionDetails, Reason as OFReason
from openfeature.exception import ErrorCode as OFErrorCode
from openfeature.event import ProviderEventDetails
from openfeature.evaluation_context import EvaluationContext as OFEvaluationContext

from flagops.client import FlagOpsClient
from flagops.engine.types import (
    ErrorCode as FlagOpsErrorCode,
    EvaluationContext as FlagOpsEvaluationContext,
    EvaluationResult,
    Reason as FlagOpsReason,
)

logger = logging.getLogger("flagops.openfeature")

# Reason mapping: FlagOps Reason -> OpenFeature Reason
_REASON_MAP: dict[str, OFReason] = {
    FlagOpsReason.TARGETING_MATCH.value: OFReason.TARGETING_MATCH,
    FlagOpsReason.SPLIT.value: OFReason.SPLIT,
    FlagOpsReason.DEFAULT.value: OFReason.DEFAULT,
    FlagOpsReason.DISABLED.value: OFReason.DISABLED,
    FlagOpsReason.ERROR.value: OFReason.ERROR,
    FlagOpsReason.STATIC.value: OFReason.STATIC,
    FlagOpsReason.CACHED.value: OFReason.CACHED,
}

# ErrorCode mapping: FlagOps ErrorCode -> OpenFeature ErrorCode
_ERROR_CODE_MAP: dict[str, OFErrorCode] = {
    FlagOpsErrorCode.FLAG_NOT_FOUND.value: OFErrorCode.FLAG_NOT_FOUND,
    FlagOpsErrorCode.TYPE_MISMATCH.value: OFErrorCode.TYPE_MISMATCH,
    FlagOpsErrorCode.PARSE_ERROR.value: OFErrorCode.PARSE_ERROR,
    FlagOpsErrorCode.GENERAL_ERROR.value: OFErrorCode.GENERAL,
    FlagOpsErrorCode.INVALID_CONTEXT.value: OFErrorCode.INVALID_CONTEXT,
    FlagOpsErrorCode.TARGETING_KEY_MISSING.value: OFErrorCode.TARGETING_KEY_MISSING,
}


def _map_reason(reason: FlagOpsReason | str | None) -> OFReason:
    """Map FlagOps evaluation reason to OpenFeature standard Reason."""
    if not reason:
        return OFReason.UNKNOWN
    val = reason.value if isinstance(reason, FlagOpsReason) else str(reason)
    return _REASON_MAP.get(val, OFReason.UNKNOWN)


def _map_error_code(error_code: FlagOpsErrorCode | str | None) -> OFErrorCode:
    """Map FlagOps error code to OpenFeature standard ErrorCode."""
    if not error_code:
        return OFErrorCode.GENERAL
    val = error_code.value if isinstance(error_code, FlagOpsErrorCode) else str(error_code)
    return _ERROR_CODE_MAP.get(val, OFErrorCode.GENERAL)


def _to_flagops_context(of_ctx: Any) -> FlagOpsEvaluationContext:
    """Convert OpenFeature EvaluationContext to FlagOps EvaluationContext."""
    if of_ctx is None:
        return FlagOpsEvaluationContext(targeting_key="", attributes={})
    if isinstance(of_ctx, FlagOpsEvaluationContext):
        return of_ctx

    # Extract targeting_key and attributes from OpenFeature EvaluationContext or dict
    if isinstance(of_ctx, OFEvaluationContext) or hasattr(of_ctx, "targeting_key"):
        targeting_key = str(of_ctx.targeting_key or "")
        attrs = dict(getattr(of_ctx, "attributes", {}) or {})
    elif isinstance(of_ctx, dict):
        targeting_key = str(of_ctx.get("targeting_key") or of_ctx.get("targetingKey") or of_ctx.get("userId") or "")
        attrs = {k: v for k, v in of_ctx.items() if k not in ("targeting_key", "targetingKey", "userId")}
    else:
        targeting_key = ""
        attrs = {}

    # Map targeting_key into attributes for bucketing_key lookup
    if targeting_key:
        if "targetingKey" not in attrs:
            attrs["targetingKey"] = targeting_key
        if "targeting_key" not in attrs:
            attrs["targeting_key"] = targeting_key

    return FlagOpsEvaluationContext(targeting_key=targeting_key, attributes=attrs)


class FlagOpsProvider(AbstractProvider):
    """OpenFeature Provider implementation wrapping FlagOpsClient."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:8000",
        client: FlagOpsClient | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize FlagOpsProvider.

        Args:
            api_key: Environment API Key (fo_srv_... or fo_cli_...).
            base_url: Base URL of FlagOps server.
            client: Optional pre-configured FlagOpsClient instance.
            **kwargs: Extra parameters passed to FlagOpsClient constructor if client not provided.
        """
        super().__init__()
        if client is not None:
            self._client = client
        elif api_key is not None:
            self._client = FlagOpsClient(api_key=api_key, base_url=base_url, **kwargs)
        else:
            raise ValueError("Either api_key or client must be provided to FlagOpsProvider")

    @property
    def is_ready(self) -> bool:
        """Return True if the underlying FlagOps client is initialized."""
        return self._client.is_ready

    def get_metadata(self) -> Metadata:
        """Return provider metadata identifying FlagOps."""
        return Metadata(name="FlagOps")

    def initialize(self, evaluation_context: OFEvaluationContext | None = None) -> None:
        """Initialize provider lifecycle according to OpenFeature spec."""
        if self._client.is_ready:
            self.emit_provider_ready(ProviderEventDetails())
        else:
            # Wait briefly for ruleset fetch
            ready = self._client.wait_for_ready(timeout=self._client.timeout)
            if ready:
                self.emit_provider_ready(ProviderEventDetails())
            else:
                self.emit_provider_error(ProviderEventDetails(message="FlagOps client initialization timed out"))

    def shutdown(self) -> None:
        """Shutdown underlying FlagOps client connections and background workers."""
        self._client.close()

    # ──────────────────────────────────────────────────────────────────────────
    # RESOLVER CORE
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve(
        self,
        flag_key: str,
        default_value: Any,
        expected_type: str,
        evaluation_context: Any = None,
    ) -> FlagResolutionDetails:
        """Generic resolver handling fail-safe checks, type verification, and reason mapping."""
        # 1. Provider readiness check
        if not self.is_ready:
            return FlagResolutionDetails(
                value=default_value,
                error_code=OFErrorCode.PROVIDER_NOT_READY,
                reason=OFReason.ERROR,
                error_message="FlagOps provider is not ready",
            )

        try:
            # Convert OpenFeature context to FlagOps context
            fo_ctx = _to_flagops_context(evaluation_context)

            # Check flag metadata in cache if available to detect type mismatch early
            ruleset = self._client._cache.get()
            flag_setting = ruleset.get_flag(flag_key) if ruleset else None

            if flag_setting is not None:
                # Type validation against declared flag type
                if not self._is_type_compatible(flag_setting.flag_type, expected_type):
                    return FlagResolutionDetails(
                        value=default_value,
                        error_code=OFErrorCode.TYPE_MISMATCH,
                        reason=OFReason.ERROR,
                        error_message=(
                            f"Flag '{flag_key}' has type '{flag_setting.flag_type}', "
                            f"cannot resolve as '{expected_type}'"
                        ),
                    )

            # Evaluate via FlagOpsClient (fail-safe: never raises)
            res: EvaluationResult = self._client.get_evaluation(
                flag_key=flag_key,
                context=fo_ctx,
                default=default_value,
            )

            # 2. Flag not found
            if res.error_code == FlagOpsErrorCode.FLAG_NOT_FOUND or (
                res.reason == FlagOpsReason.ERROR and "not found" in str(res.error_message or "").lower()
            ):
                return FlagResolutionDetails(
                    value=default_value,
                    error_code=OFErrorCode.FLAG_NOT_FOUND,
                    reason=OFReason.ERROR,
                    error_message=f"Flag '{flag_key}' not found",
                )

            # 3. Value-level type verification
            val = res.value
            if not self._is_value_type_compatible(val, expected_type):
                return FlagResolutionDetails(
                    value=default_value,
                    error_code=OFErrorCode.TYPE_MISMATCH,
                    reason=OFReason.ERROR,
                    error_message=(
                        f"Evaluation of '{flag_key}' returned value of type "
                        f"'{type(val).__name__}', expected '{expected_type}'"
                    ),
                )

            # Coerce number to int or float if needed
            if expected_type == "integer" and isinstance(val, (int, float)):
                val = int(val)
            elif expected_type == "float" and isinstance(val, (int, float)):
                val = float(val)

            # Map reason and return resolution details
            of_reason = _map_reason(res.reason)
            return FlagResolutionDetails(
                value=val,
                variant=res.variant or None,
                reason=of_reason,
                flag_metadata=res.flag_metadata or {},
            )

        except Exception as exc:
            logger.warning(f"Unexpected error resolving flag '{flag_key}': {exc}")
            return FlagResolutionDetails(
                value=default_value,
                error_code=OFErrorCode.GENERAL,
                reason=OFReason.ERROR,
                error_message=str(exc),
            )

    @staticmethod
    def _is_type_compatible(flag_type: str, expected_type: str) -> bool:
        """Check if flag schema type is compatible with requested resolver type."""
        ft = (flag_type or "").lower()
        if expected_type == "boolean":
            return ft in ("boolean", "bool")
        elif expected_type == "string":
            return ft in ("string", "str")
        elif expected_type in ("integer", "float"):
            return ft in ("number", "integer", "float", "int")
        elif expected_type == "object":
            return ft in ("json", "object")
        return True

    @staticmethod
    def _is_value_type_compatible(value: Any, expected_type: str) -> bool:
        """Check if evaluated runtime value matches expected OpenFeature type."""
        if expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "integer":
            if isinstance(value, bool):
                return False
            if isinstance(value, int):
                return True
            if isinstance(value, float) and value.is_integer():
                return True
            return False
        elif expected_type == "float":
            if isinstance(value, bool):
                return False
            return isinstance(value, (int, float))
        elif expected_type == "object":
            return isinstance(value, (dict, list))
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # 5 TYPED RESOLVERS (OPENFEATURE SPEC)
    # ──────────────────────────────────────────────────────────────────────────

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: OFEvaluationContext | None = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details."""
        return self._resolve(flag_key, default_value, "boolean", evaluation_context)

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: OFEvaluationContext | None = None,
    ) -> FlagResolutionDetails[str]:
        """Resolve string flag details."""
        return self._resolve(flag_key, default_value, "string", evaluation_context)

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: OFEvaluationContext | None = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve integer flag details."""
        return self._resolve(flag_key, default_value, "integer", evaluation_context)

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: OFEvaluationContext | None = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve float flag details."""
        return self._resolve(flag_key, default_value, "float", evaluation_context)

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[dict, list],
        evaluation_context: OFEvaluationContext | None = None,
    ) -> FlagResolutionDetails[Union[dict, list]]:
        """Resolve object (dict or list) flag details."""
        return self._resolve(flag_key, default_value, "object", evaluation_context)
