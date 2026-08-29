"""Ferro Labs AI Gateway — exception hierarchy.

Status → exception mapping (ai-gateway error envelope ``{"error": {message, type, code}}``):

    401 → FerroAuthError            402 → FerroBudgetExceededError
    403 → FerroPermissionError      404 → FerroNotFoundError
    429 → FerroRateLimitError       5xx → FerroServerError
    other non-2xx → FerroAPIError
"""

from __future__ import annotations


class FerroError(Exception):
    """Base exception for all ferrolabsai errors."""


class FerroAPIError(FerroError):
    """Raised when the gateway returns a non-2xx HTTP response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, "
            f"status_code={self.status_code}, code={self.code!r})"
        )


class FerroAuthError(FerroAPIError):
    """401 — invalid or missing API key."""


class FerroBudgetExceededError(FerroAPIError):
    """402 ``insufficient_quota`` — the key's spend limit is exhausted."""


class FerroPermissionError(FerroAPIError):
    """403 ``insufficient_scope`` — the key lacks the scope for this route."""


class FerroRateLimitError(FerroAPIError):
    """429 — rate limit exceeded. ``retry_after`` mirrors the ``Retry-After`` header (seconds)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = 429,
        code: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, code=code, request_id=request_id)
        self.retry_after = retry_after


class FerroNotFoundError(FerroAPIError):
    """404 — resource not found."""


class FerroServerError(FerroAPIError):
    """5xx — gateway or upstream provider error."""


class FerroConnectionError(FerroError):
    """Cannot connect to the gateway (network error, timeout) after all retries."""


class FerroStreamError(FerroError):
    """Error while consuming a streaming response (malformed frame or a gateway
    error frame such as ``stream_error`` / ``stream_timeout``)."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
