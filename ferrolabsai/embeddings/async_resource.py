"""Async embeddings resource."""

from __future__ import annotations

from typing import Any

from ..types import EmbeddingResponse


class AsyncEmbeddings:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def create(
        self,
        *,
        model: str,
        input: str | list[str],
        encoding_format: str | None = None,
        dimensions: int | None = None,
        user: str | None = None,
    ) -> EmbeddingResponse:
        body: dict[str, Any] = {"model": model, "input": input}
        if encoding_format is not None:
            body["encoding_format"] = encoding_format
        if dimensions is not None:
            body["dimensions"] = dimensions
        if user is not None:
            body["user"] = user
        data = await self._client._request("POST", "/v1/embeddings", json=body)
        return EmbeddingResponse.from_dict(data)
