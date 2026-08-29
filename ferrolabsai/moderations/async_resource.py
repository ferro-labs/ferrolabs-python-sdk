"""Async moderations resource — see ``moderations/resource.py``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .resource import PATH, build_body

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncModerations:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def create(
        self, *, input: str | list[str], model: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await self._client._request("POST", PATH, json=build_body(input, model, **kwargs))
