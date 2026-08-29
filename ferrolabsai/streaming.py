"""SSE stream wrappers for ``chat.completions.create(stream=True)``.

The wrapper keeps the HTTP response so header metadata (``X-Request-ID`` →
``trace_id``, ``X-Gateway-Provider`` → ``provider``) is available on the
stream object and copied onto every chunk. Streaming requests are never
retried: by the time the caller iterates, bytes may already have been read.

Wire format (ai-gateway ``providers/core/chat.go``): ``data: {chunk}`` frames,
``usage`` only on the terminal chunk when ``stream_options.include_usage`` was
sent, ``data: [DONE]`` terminator, and mid-stream errors as a
``{"error": {message, type, code}}`` frame.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import replace

import httpx

from .exceptions import FerroStreamError
from .types import ChatCompletionChunk

DONE = "[DONE]"


def _payload(line: str) -> str | None:
    """Payload of one ``data:`` line, or ``None`` for comments/blank/other fields."""
    if not line.startswith("data:"):
        return None
    return line[5:].strip()


def _parse_chunk(payload: str, trace_id: str | None, provider: str | None) -> ChatCompletionChunk:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise FerroStreamError(
            f"Malformed SSE chunk in streaming response: {payload[:200]!r}"
        ) from e
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        raise FerroStreamError(error.get("message") or "stream error", code=error.get("code"))
    return replace(ChatCompletionChunk.from_dict(data), trace_id=trace_id, provider=provider)


class Stream:
    """Iterator of :class:`ChatCompletionChunk` over a live SSE response.

    Attributes:
        response: The underlying ``httpx.Response`` (closed when exhausted or on ``close()``).
        trace_id: ``X-Request-ID`` of the stream (32 hex chars on ai-gateway ≥ 1.4).
        provider: ``X-Gateway-Provider`` when the gateway sets it (not on SSE as of v1.4.5).
    """

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.trace_id: str | None = response.headers.get("x-request-id")
        self.provider: str | None = response.headers.get("x-gateway-provider")
        self._chunks = self._iter()

    def __iter__(self) -> Iterator[ChatCompletionChunk]:
        return self

    def __next__(self) -> ChatCompletionChunk:
        return next(self._chunks)

    def _iter(self) -> Iterator[ChatCompletionChunk]:
        try:
            for line in self.response.iter_lines():
                payload = _payload(line)
                if payload is None:
                    continue
                if payload == DONE:
                    return
                yield _parse_chunk(payload, self.trace_id, self.provider)
        finally:
            self.response.close()

    def close(self) -> None:
        self.response.close()

    def __enter__(self) -> Stream:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncStream:
    """Async counterpart of :class:`Stream` (``async for chunk in stream``)."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.trace_id: str | None = response.headers.get("x-request-id")
        self.provider: str | None = response.headers.get("x-gateway-provider")
        self._chunks = self._iter()

    def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        return self

    async def __anext__(self) -> ChatCompletionChunk:
        return await self._chunks.__anext__()

    async def _iter(self) -> AsyncIterator[ChatCompletionChunk]:
        try:
            async for line in self.response.aiter_lines():
                payload = _payload(line)
                if payload is None:
                    continue
                if payload == DONE:
                    return
                yield _parse_chunk(payload, self.trace_id, self.provider)
        finally:
            await self.response.aclose()

    async def aclose(self) -> None:
        await self.response.aclose()

    async def __aenter__(self) -> AsyncStream:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
