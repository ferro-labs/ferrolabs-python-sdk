"""Ferro Labs AI Gateway — exception hierarchy."""

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


class FerroRateLimitError(FerroAPIError):
    """429 — rate limit or quota exceeded."""


class FerroNotFoundError(FerroAPIError):
    """404 — resource not found."""


class FerroServerError(FerroAPIError):
    """5xx — gateway or upstream provider error."""


class FerroConnectionError(FerroError):
    """Cannot connect to the gateway (network error, timeout, etc.)."""


class FerroStreamError(FerroError):
    """Error while consuming a streaming response."""
