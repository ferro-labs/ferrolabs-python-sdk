"""Model catalog resource — query 2,500+ models with pricing and capabilities."""

from __future__ import annotations

import builtins
from typing import Any

from ..types import ModelInfo


class Models:
    def __init__(self, client: Any) -> None:
        self._client = client

    def list(
        self,
        *,
        provider: str | None = None,
        capability: str | None = None,
    ) -> builtins.list[ModelInfo]:
        """
        List all available models in the gateway's model catalog.

        Args:
            provider: Filter by provider name. E.g. "openai", "anthropic", "groq".
            capability: Filter by capability. E.g. "chat", "embeddings", "vision",
                "function_calling".

        Returns:
            List of ModelInfo objects with pricing, context windows, and capabilities.

        Example::

            # List all models
            models = client.models.list()

            # Only Anthropic models
            claude_models = client.models.list(provider="anthropic")

            # Only models with vision capability
            vision_models = client.models.list(capability="vision")
        """
        params: dict[str, Any] = {}
        if provider is not None:
            params["provider"] = provider
        if capability is not None:
            params["capability"] = capability

        data = self._client._request("GET", "/v1/models", params=params or None)
        raw_models = data.get("data", data) if isinstance(data, dict) else data
        return [ModelInfo.from_dict(m) for m in raw_models]

    def retrieve(self, model_id: str) -> ModelInfo:
        """
        Get details for a specific model by ID.

        Example::

            info = client.models.retrieve("gpt-4o")
            print(f"Context window: {info.context_window}")
            print(f"Input cost: ${info.input_cost_per_token:.8f}/token")
        """
        data = self._client._request("GET", f"/v1/models/{model_id}")
        return ModelInfo.from_dict(data)

    def search(self, query: str) -> builtins.list[ModelInfo]:
        """
        Search the model catalog by name or description.

        Example::

            results = client.models.search("claude")
        """
        params = {"search": query}
        data = self._client._request("GET", "/v1/models", params=params)
        raw_models = data.get("data", data) if isinstance(data, dict) else data
        return [ModelInfo.from_dict(m) for m in raw_models]
