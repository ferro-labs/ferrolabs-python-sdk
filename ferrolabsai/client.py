"""
FerroClient — drop-in replacement for the OpenAI Python client.
Points at any Ferro Labs AI Gateway instance (self-hosted or FerroCloud).
"""

from __future__ import annotations

import os
from typing import Any, Iterator, Literal, cast, overload

import httpx

from .admin.resource import Admin
from .completions.resource import Completions
from .embeddings.resource import Embeddings
from .exceptions import FerroAuthError, FerroConnectionError
from .images.resource import Images
from .models.resource import Models

DEFAULT_BASE_URL = "https://api.ferrolabs.ai"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 2


class FerroClient:
    """
    Primary client for Ferro Labs AI Gateway.

    Drop-in compatible with the OpenAI Python SDK for chat/embeddings/images.
    Adds gateway-specific features: admin API, model catalog, prompt templates,
    cost tracking, and guardrail management.

    Usage::

        from ferrolabsai import FerroClient

        client = FerroClient(api_key="sk-ferro-...")

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
        self.api_key = (
            api_key or os.environ.get("FERRO_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )
        if not self.api_key:
            raise FerroAuthError(
                "No API key provided. Pass api_key=... or set FERRO_API_KEY env var."
            )

        self.base_url = (base_url or os.environ.get("FERRO_BASE_URL") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.timeout = timeout
        self.max_retries = max_retries

        self._default_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"ferrolabsai-python/{self._version()}",
            **(default_headers or {}),
        }

        self._http = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._default_headers,
        )

        # Resource namespaces — mirrors OpenAI SDK layout
        self.chat = _ChatNamespace(self)
        self.embeddings = Embeddings(self)
        self.images = Images(self)
        self.models = Models(self)
        self.admin = Admin(self)

    # ------------------------------------------------------------------
    # Internal HTTP helpers used by all resource classes
    # ------------------------------------------------------------------

    @overload
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = ...,
        params: dict[str, Any] | None = ...,
        stream: Literal[False] = ...,
    ) -> dict[str, Any]: ...
    @overload
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = ...,
        params: dict[str, Any] | None = ...,
        stream: Literal[True],
    ) -> httpx.Response: ...
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | httpx.Response:
        url = path if path.startswith("http") else path
        attempt = 0
        last_exc: Exception | None = None

        while attempt <= self.max_retries:
            try:
                req = self._http.build_request(
                    method,
                    url,
                    json=json,
                    params=params,
                )
                response = self._http.send(req, stream=stream)
                response.raise_for_status()
                if stream:
                    return response
                if response.status_code == 204 or not response.content:
                    return {}
                return cast("dict[str, Any]", response.json())
            except httpx.HTTPStatusError as e:
                _raise_api_error(e)
            except httpx.ConnectError as e:
                last_exc = FerroConnectionError(
                    f"Cannot reach {self.base_url}. Is the gateway running? ({e})"
                )
                attempt += 1
            except httpx.TimeoutException as e:
                last_exc = FerroConnectionError(f"Request timed out after {self.timeout}s: {e}")
                attempt += 1

        raise last_exc  # type: ignore

    def _stream_request(self, path: str, json: Any) -> Iterator[str]:
        """Yields raw SSE lines for streaming completions."""
        with self._http.stream("POST", path, json=json) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield line

    @staticmethod
    def _version() -> str:
        try:
            from importlib.metadata import version

            return version("ferrolabsai")
        except Exception:
            return "0.1.0"

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

        async with AsyncFerroClient(api_key="sk-ferro-...") as client:
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
    ) -> None:
        self.api_key = (
            api_key or os.environ.get("FERRO_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )
        if not self.api_key:
            raise FerroAuthError(
                "No API key provided. Pass api_key=... or set FERRO_API_KEY env var."
            )

        self.base_url = (base_url or os.environ.get("FERRO_BASE_URL") or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.timeout = timeout
        self.max_retries = max_retries

        self._default_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"ferrolabsai-python/{FerroClient._version()}",
            **(default_headers or {}),
        }

        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._default_headers,
        )

        from .embeddings.async_resource import AsyncEmbeddings

        self.chat = _AsyncChatNamespace(self)
        self.embeddings = AsyncEmbeddings(self)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self.max_retries:
            try:
                response = await self._http.request(method, path, json=json, params=params)
                response.raise_for_status()
                return cast("dict[str, Any]", response.json())
            except httpx.HTTPStatusError as e:
                _raise_api_error(e)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exc = FerroConnectionError(str(e))
                attempt += 1
        raise last_exc  # type: ignore

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncFerroClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()


class _AsyncChatNamespace:
    def __init__(self, client: AsyncFerroClient) -> None:
        from .completions.async_resource import AsyncCompletions

        self.completions = AsyncCompletions(client)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _raise_api_error(e: httpx.HTTPStatusError) -> None:
    from .exceptions import (
        FerroAPIError,
        FerroAuthError,
        FerroNotFoundError,
        FerroRateLimitError,
        FerroServerError,
    )

    status = e.response.status_code
    try:
        body = e.response.json()
        message = body.get("error", {}).get("message") or body.get("message") or str(e)
        code = body.get("error", {}).get("code") or body.get("code")
    except Exception:
        message = e.response.text or str(e)
        code = None

    if status == 401:
        raise FerroAuthError(message) from e
    if status == 429:
        raise FerroRateLimitError(message) from e
    if status == 404:
        raise FerroNotFoundError(message) from e
    if status >= 500:
        raise FerroServerError(message, status_code=status) from e
    raise FerroAPIError(message, status_code=status, code=code) from e
