"""Async Responses API resource — see ``responses/resource.py``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..types import Response
from .resource import PATH

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncResponses:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def create(self, **params: Any) -> Response:
        return Response.from_dict(await self._client._request("POST", PATH, json=params))

    async def retrieve(self, response_id: str) -> Response:
        return Response.from_dict(await self._client._request("GET", f"{PATH}/{response_id}"))

    async def delete(self, response_id: str) -> dict[str, Any]:
        return await self._client._request("DELETE", f"{PATH}/{response_id}")
