"""Async model catalog resource — see ``models/resource.py`` for the client-side lookup rules."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from ..types import ModelInfo
from .resource import PATH, filter_models, find_model, parse_catalog, search_models

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncModels:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def _fetch(self) -> builtins.list[ModelInfo]:
        return parse_catalog(await self._client._request("GET", PATH))

    async def list(
        self,
        *,
        provider: str | None = None,
        capability: str | None = None,
    ) -> builtins.list[ModelInfo]:
        return filter_models(await self._fetch(), provider, capability)

    async def retrieve(self, model_id: str) -> ModelInfo:
        return find_model(await self._fetch(), model_id)

    async def search(self, query: str) -> builtins.list[ModelInfo]:
        return search_models(await self._fetch(), query)
