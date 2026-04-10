"""Embeddings resource."""

from __future__ import annotations

from typing import Any

from ..types import EmbeddingResponse


class Embeddings:
    def __init__(self, client: Any) -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        input: str | list[str],
        encoding_format: str | None = None,
        dimensions: int | None = None,
        user: str | None = None,
    ) -> EmbeddingResponse:
        """
        Create embeddings for one or more input strings.

        Args:
            model: Embedding model. E.g. "text-embedding-3-small", "text-embedding-ada-002".
                   Ferro routes to the correct provider automatically.
            input: String or list of strings to embed.
            encoding_format: "float" (default) or "base64".
            dimensions: Number of dimensions for models that support it.

        Example::

            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=["Hello world", "Ferro is fast"],
            )
            vectors = [d.embedding for d in response.data]
        """
        body: dict[str, Any] = {"model": model, "input": input}
        if encoding_format is not None:
            body["encoding_format"] = encoding_format
        if dimensions is not None:
            body["dimensions"] = dimensions
        if user is not None:
            body["user"] = user

        data = self._client._request("POST", "/v1/embeddings", json=body)
        return EmbeddingResponse.from_dict(data)
