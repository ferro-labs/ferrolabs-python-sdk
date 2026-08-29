"""
FerroClient — drop-in replacement for the OpenAI Python client.
Points at any self-hosted Ferro Labs AI Gateway instance (ai-gateway ≥ v1.4.0).
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, NoReturn, cast

import httpx

from ._version import __version__
from .admin.async_resource import AsyncAdmin
from .admin.resource import Admin
from .completions.async_resource import AsyncCompletions
from .completions.resource import Completions
from .embeddings.async_resource import AsyncEmbeddings
from .embeddings.resource import Embeddings
from .exceptions import (
    FerroAPIError,
    FerroAuthError,
    FerroBudgetExceededError,
    FerroConnectionError,
    FerroNotFoundError,
    FerroPermissionError,
    FerroRateLimitError,
    FerroServerError,
)
from .images.async_resource import AsyncImages
from .images.resource import Images
from .models.async_resource import AsyncModels
from .models.resource import Models
from .moderations.async_resource import AsyncModerations
from .moderations.resource import Moderations
from .responses.async_resource import AsyncResponses
from .responses.resource import Responses

DEFAULT_BASE_URL: str = "http://localhost:8080"
DEFAULT_TIMEOUT: float = 120.0
DEFAULT_MAX_RETRIES: int = 2
DEFAULT_RETRY_BACKOFF_BASE: float = 0.5
DEFAULT_RETRY_BACKOFF_MAX: float = 8.0
RETRY_AFTER_MAX: float = 30.0  # same cap the gateway applies to its own upstream retries
RETRYABLE_STATUSES: frozenset[int] = frozenset({408, 429})  # plus every 5xx
IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})

# Only inference bodies get header metadata (trace_id, provider, gateway_overhead_ms)
# merged in; catalog, probe, and admin bodies are returned untouched.
_INFERENCE_PREFIXES = (
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/embeddings",
    "/v1/images/generations",
    "/v1/responses",
    "/v1/rerank",
    "/v1/moderations",
)
# /health and /readyz answer 503 with a JSON body when degraded; that is an answer, not an error.
_PROBE_STATUSES = (503,)


def _validate_max_retries(max_retries: object) -> int:
    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise TypeError("max_retries must be an integer")
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    return max_retries


def _resolve_credentials(api_key: str | None, base_url: str | None) -> tuple[str, str]:
    key = api_key or os.environ.get("FERRO_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise FerroAuthError("No API key provided. Pass api_key=... or set FERRO_API_KEY env var.")
    url = (base_url or os.environ.get("FERRO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return key, url


def _default_headers(api_key: str, extra: dict[str, str] | None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": f"ferrolabsai-python/{__version__}",
        **(extra or {}),
    }


# ------------------------------------------------------------------
# Retry policy (shared by sync and async; streaming is never retried)
# ------------------------------------------------------------------


def _should_retry(method: str, *, status: int | None = None, exc: Exception | None = None) -> bool:
    """Whether a failed attempt may be re-sent.

    A 429 means the gateway did not process the request, and a connect error or
    connect timeout means the request never left, so those retry for every
    method. Any other retryable status (408/5xx) or timeout (read/write/pool)
    leaves a non-idempotent request ambiguous — a POST may already have been
    processed — so those retry only for idempotent methods.
    """
    idempotent = method.upper() in IDEMPOTENT_METHODS
    if status is not None:
        if status == 429:
            return True
        return idempotent and (status in RETRYABLE_STATUSES or status >= 500)
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    return idempotent and isinstance(exc, httpx.TimeoutException)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """``Retry-After`` in seconds, or None when absent / not a number (HTTP-date form)."""
    value = response.headers.get("retry-after")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _retry_delay(attempt: int, retry_after: float | None = None) -> float:
    """Delay before the 1-based retry ``attempt``: honour Retry-After (capped), else
    capped exponential backoff with full jitter."""
    if retry_after is not None:
        return min(retry_after, RETRY_AFTER_MAX)
    delay = min(DEFAULT_RETRY_BACKOFF_BASE * float(2 ** (attempt - 1)), DEFAULT_RETRY_BACKOFF_MAX)
    return random.uniform(0, delay)


def _connection_error(exc: Exception, base_url: str, timeout: float) -> FerroConnectionError:
    if isinstance(exc, httpx.TimeoutException):
        return FerroConnectionError(f"Request timed out after {timeout}s: {exc}")
    return FerroConnectionError(f"Cannot reach {base_url}. Is the gateway running? ({exc})")


class FerroClient:
    """
    Primary client for Ferro Labs AI Gateway.

    Drop-in compatible with the OpenAI Python SDK for chat/embeddings/images,
    plus the gateway's own surface: model catalog, capabilities, health probes,
    Responses API, rerank, moderations, and the ``/admin/*`` API.

    Usage::

        from ferrolabsai import FerroClient

        client = FerroClient(api_key="fgw_...")

        # OpenAI-compatible
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Or route to any provider by model name
        response = client.chat.completions.create(
            model="claude-3-5-sonnet-20241022",  # Ferro auto-routes to Anthropic
            messages=[{"role": "user", "content": "Hello"}],
        )
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: dict[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key, self.base_url = _resolve_credentials(api_key, base_url)
        self.timeout = timeout
        self.max_retries = _validate_max_retries(max_retries)
        self._default_headers = _default_headers(self.api_key, default_headers)

        if http_client is not None:
            http_client.headers.update(self._default_headers)
            self._http = http_client
        else:
            self._http = httpx.Client(
                base_url=self.base_url, timeout=timeout, headers=self._default_headers
            )

        # Resource namespaces — mirrors OpenAI SDK layout
        self.chat = _ChatNamespace(self)
        self.embeddings = Embeddings(self)
        self.images = Images(self)
        self.models = Models(self)
        self.responses = Responses(self)
        self.moderations = Moderations(self)
        self.admin = Admin(self)

    # ------------------------------------------------------------------
    # Gateway-level endpoints
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """``GET /health`` — ``{status, version, commit, built, providers}``; 503 body when
        degraded (e.g. ``{"status": "no_providers"}``) is returned, not raised."""
        return self._request("GET", "/health", allow=_PROBE_STATUSES)

    def ready(self) -> dict[str, Any]:
        """``GET /readyz`` — 200 ``{status: "ready", providers, targets, mcp_servers}`` or the
        503 ``{status: "not_ready", reason}`` body."""
        return self._request("GET", "/readyz", allow=_PROBE_STATUSES)

    def live(self) -> dict[str, Any]:
        """``GET /livez`` — ``{"status": "ok"}``."""
        return self._request("GET", "/livez")

    def capabilities(self) -> dict[str, Any]:
        """``GET /v1/capabilities`` — per-provider parameter support matrix
        (``forward`` / ``translate`` / ``unsupported``) for the configured targets."""
        return self._request("GET", "/v1/capabilities")

    def rerank(
        self,
        *,
        model: str,
        query: str,
        documents: list[str],
        top_n: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """``POST /v1/rerank`` (Cohere v2 shape) — returns the provider's JSON."""
        body: dict[str, Any] = {"model": model, "query": query, "documents": documents, **kwargs}
        if top_n is not None:
            body["top_n"] = top_n
        return self._request("POST", "/v1/rerank", json=body)

    # ------------------------------------------------------------------
    # Internal HTTP helpers used by all resource classes
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        allow: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                response = self._http.request(method, path, json=json, params=params)
                if response.status_code not in allow:
                    response.raise_for_status()
                return _parse_body(response, path)
            except httpx.HTTPStatusError as e:
                if attempt >= self.max_retries or not _should_retry(
                    method, status=e.response.status_code
                ):
                    _raise_api_error(e)
                delay = _retry_delay(attempt + 1, _retry_after_seconds(e.response))
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt >= self.max_retries or not _should_retry(method, exc=e):
                    raise _connection_error(e, self.base_url, self.timeout) from e
                delay = _retry_delay(attempt + 1)
            attempt += 1
            time.sleep(delay)

    def _open_stream(self, path: str, json: Any) -> httpx.Response:
        """POST and return the live response for SSE consumption (no retries)."""
        request = self._http.build_request(
            "POST", path, json=json, headers={"Accept": "text/event-stream"}
        )
        try:
            response = self._http.send(request, stream=True)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise _connection_error(e, self.base_url, self.timeout) from e
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            response.read()
            response.close()
            _raise_api_error(e)
        return response

    @staticmethod
    def _version() -> str:
        return __version__

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> FerroClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class _ChatNamespace:
    """Provides client.chat.completions to mirror OpenAI SDK layout."""

    def __init__(self, client: FerroClient) -> None:
        self.completions = Completions(client)


# ------------------------------------------------------------------
# Async client
# ------------------------------------------------------------------


class AsyncFerroClient:
    """
    Async version of FerroClient using httpx.AsyncClient.

    Usage::

        from ferrolabsai import AsyncFerroClient

        async with AsyncFerroClient(api_key="fgw_...") as client:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
            )
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: dict[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key, self.base_url = _resolve_credentials(api_key, base_url)
        self.timeout = timeout
        self.max_retries = _validate_max_retries(max_retries)
        self._default_headers = _default_headers(self.api_key, default_headers)

        if http_client is not None:
            http_client.headers.update(self._default_headers)
            self._http = http_client
        else:
            self._http = httpx.AsyncClient(
                base_url=self.base_url, timeout=timeout, headers=self._default_headers
            )

        self.chat = _AsyncChatNamespace(self)
        self.embeddings = AsyncEmbeddings(self)
        self.images = AsyncImages(self)
        self.models = AsyncModels(self)
        self.responses = AsyncResponses(self)
        self.moderations = AsyncModerations(self)
        self.admin = AsyncAdmin(self)

    async def health(self) -> dict[str, Any]:
        """See :meth:`FerroClient.health`."""
        return await self._request("GET", "/health", allow=_PROBE_STATUSES)

    async def ready(self) -> dict[str, Any]:
        """See :meth:`FerroClient.ready`."""
        return await self._request("GET", "/readyz", allow=_PROBE_STATUSES)

    async def live(self) -> dict[str, Any]:
        """See :meth:`FerroClient.live`."""
        return await self._request("GET", "/livez")

    async def capabilities(self) -> dict[str, Any]:
        """See :meth:`FerroClient.capabilities`."""
        return await self._request("GET", "/v1/capabilities")

    async def rerank(
        self,
        *,
        model: str,
        query: str,
        documents: list[str],
        top_n: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """See :meth:`FerroClient.rerank`."""
        body: dict[str, Any] = {"model": model, "query": query, "documents": documents, **kwargs}
        if top_n is not None:
            body["top_n"] = top_n
        return await self._request("POST", "/v1/rerank", json=body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        allow: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                response = await self._http.request(method, path, json=json, params=params)
                if response.status_code not in allow:
                    response.raise_for_status()
                return _parse_body(response, path)
            except httpx.HTTPStatusError as e:
                if attempt >= self.max_retries or not _should_retry(
                    method, status=e.response.status_code
                ):
                    _raise_api_error(e)
                delay = _retry_delay(attempt + 1, _retry_after_seconds(e.response))
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt >= self.max_retries or not _should_retry(method, exc=e):
                    raise _connection_error(e, self.base_url, self.timeout) from e
                delay = _retry_delay(attempt + 1)
            attempt += 1
            await asyncio.sleep(delay)

    async def _open_stream(self, path: str, json: Any) -> httpx.Response:
        request = self._http.build_request(
            "POST", path, json=json, headers={"Accept": "text/event-stream"}
        )
        try:
            response = await self._http.send(request, stream=True)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise _connection_error(e, self.base_url, self.timeout) from e
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await response.aread()
            await response.aclose()
            _raise_api_error(e)
        return response

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncFerroClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()


class _AsyncChatNamespace:
    def __init__(self, client: AsyncFerroClient) -> None:
        self.completions = AsyncCompletions(client)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_body(response: httpx.Response, path: str) -> dict[str, Any]:
    if response.status_code == 204 or not response.content:
        return {}
    data = cast("dict[str, Any]", response.json())
    if path.startswith(_INFERENCE_PREFIXES):
        return _with_response_metadata(data, response)
    return data


def _header_float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _with_response_metadata(data: dict[str, Any], response: httpx.Response) -> dict[str, Any]:
    """Merge the gateway's response headers into an inference body.

    ``X-Request-ID`` → ``trace_id``; ``X-Gateway-Provider`` → ``provider`` (the
    non-streaming chat body carries ``provider`` itself, which wins);
    ``X-Gateway-Overhead-Ms`` → ``gateway_overhead_ms``. Returns a new dict.
    """
    extra: dict[str, Any] = {}
    trace_id = response.headers.get("x-request-id")
    if trace_id and "trace_id" not in data:
        extra["trace_id"] = trace_id
    provider = response.headers.get("x-gateway-provider")
    if provider and "provider" not in data:
        extra["provider"] = provider
    overhead = _header_float(response.headers.get("x-gateway-overhead-ms"))
    if overhead is not None and "gateway_overhead_ms" not in data:
        extra["gateway_overhead_ms"] = overhead
    return {**data, **extra} if extra else data


def _raise_api_error(e: httpx.HTTPStatusError) -> NoReturn:
    """Map the gateway error envelope ``{"error": {message, type, code}}`` to an exception."""
    status = e.response.status_code
    request_id = e.response.headers.get("x-request-id")
    try:
        body = e.response.json()
        error = body.get("error") if isinstance(body, dict) else None
        error = error if isinstance(error, dict) else {}
        message = error.get("message") or body.get("message") or str(e)
        code = error.get("code") or body.get("code")
        request_id = request_id or body.get("request_id") or body.get("trace_id")
    except Exception:
        message = e.response.text or str(e)
        code = None

    kwargs: dict[str, Any] = {"status_code": status, "code": code, "request_id": request_id}
    if status == 401:
        raise FerroAuthError(message, **kwargs) from e
    if status == 402:
        raise FerroBudgetExceededError(message, **kwargs) from e
    if status == 403:
        raise FerroPermissionError(message, **kwargs) from e
    if status == 404:
        raise FerroNotFoundError(message, **kwargs) from e
    if status == 429:
        raise FerroRateLimitError(
            message, retry_after=_retry_after_seconds(e.response), **kwargs
        ) from e
    if status >= 500:
        raise FerroServerError(message, **kwargs) from e
    raise FerroAPIError(message, **kwargs) from e
