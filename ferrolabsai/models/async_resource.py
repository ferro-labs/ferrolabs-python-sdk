"""Async model catalog resource."""

from __future__ import annotations

import builtins
from typing import Any

from ..types import ModelInfo


class AsyncModels:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def list(
        self,
        *,
        provider: str | None = None,
        capability: str | None = None,
    ) -> builtins.list[ModelInfo]:
        params: dict[str, Any] = {}
        if provider is not None:
            params["provider"] = provider
        if capability is not None:
            params["capability"] = capability

        data = await self._client._request("GET", "/v1/models", params=params or None)
        raw_models = data.get("data", data) if isinstance(data, dict) else data
        return [ModelInfo.from_dict(m) for m in raw_models]

    async def retrieve(self, model_id: str) -> ModelInfo:
        data = await self._client._request("GET", f"/v1/models/{model_id}")
        return ModelInfo.from_dict(data)

    async def search(self, query: str) -> builtins.list[ModelInfo]:
        data = await self._client._request("GET", "/v1/models", params={"search": query})
        raw_models = data.get("data", data) if isinstance(data, dict) else data
        return [ModelInfo.from_dict(m) for m in raw_models]
