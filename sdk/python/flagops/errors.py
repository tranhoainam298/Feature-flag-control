"""Internal error types for FlagOps Python SDK.

These exceptions are strictly for internal SDK flow control and logging.
They MUST NEVER be raised to client applications calling evaluation or config methods.
"""


class FlagOpsSDKError(Exception):
    """Base exception for FlagOps SDK internal errors."""

    pass


class TransportError(FlagOpsSDKError):
    """Raised when an HTTP transport network request fails or times out."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RulesetParseError(FlagOpsSDKError):
    """Raised when the server response cannot be deserialized into a valid Ruleset."""

    pass
