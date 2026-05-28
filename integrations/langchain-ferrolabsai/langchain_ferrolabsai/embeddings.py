"""FerroEmbeddings — LangChain ``Embeddings`` backed by Ferro Labs AI Gateway.

A single ``FerroEmbeddings`` instance routes to any embeddings-capable
provider the gateway knows about by model name (e.g.
``"text-embedding-3-small"``, ``"voyage-3"``, ``"cohere.embed-english-v3"``).
"""

from __future__ import annotations

from typing import Any

from ferrolabsai import FerroClient
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr


class FerroEmbeddings(BaseModel, Embeddings):
    """LangChain embeddings adapter for the Ferro gateway.

    Example::

        from langchain_ferrolabsai import FerroEmbeddings

        embed = FerroEmbeddings(model="text-embedding-3-small", api_key="sk-ferro-...")
        vectors = embed.embed_documents(["hello", "world"])
        query_vec = embed.embed_query("hello")
    """

    model: str = Field(..., description="Embeddings model routed by the gateway.")
    base_url: str | None = None
    api_key: SecretStr | None = None
    timeout: float = 120.0
    max_retries: int = 2
    dimensions: int | None = None
    encoding_format: str | None = None
    user: str | None = None
    default_headers: dict[str, str] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    _client_instance: FerroClient | None = PrivateAttr(default=None)

    def _get_client(self) -> FerroClient:
        if self._client_instance is None:
            self._client_instance = FerroClient(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                default_headers=self.default_headers,
            )
        return self._client_instance

    def _build_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": self.model}
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        if self.encoding_format is not None:
            kwargs["encoding_format"] = self.encoding_format
        if self.user is not None:
            kwargs["user"] = self.user
        return kwargs

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._get_client().embeddings.create(input=texts, **self._build_kwargs())
        # Preserve input order by sorting on `index` — the gateway / provider
        # may return data out of order.
        ordered = sorted(response.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]

    def embed_query(self, text: str) -> list[float]:
        response = self._get_client().embeddings.create(input=text, **self._build_kwargs())
        if not response.data:
            return []
        return response.data[0].embedding
