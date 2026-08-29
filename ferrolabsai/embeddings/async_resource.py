"""Async embeddings resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..types import EmbeddingResponse
from .resource import PATH, build_body

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncEmbeddings:
    def __init__(self, client: AsyncFerroClient) -> None:
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
        """See :meth:`ferrolabsai.embeddings.resource.Embeddings.create`."""
        body = build_body(model, input, encoding_format, dimensions, user)
        return EmbeddingResponse.from_dict(await self._client._request("POST", PATH, json=body))
