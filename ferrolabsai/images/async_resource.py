"""Async image generation resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..types import ImageResponse
from .resource import PATH, build_body

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncImages:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        n: int | None = None,
        size: str | None = None,
        quality: str | None = None,
        response_format: str | None = None,
        style: str | None = None,
        user: str | None = None,
    ) -> ImageResponse:
        """See :meth:`ferrolabsai.images.resource.Images.generate`."""
        body = build_body(
            model,
            prompt,
            n=n,
            size=size,
            quality=quality,
            response_format=response_format,
            style=style,
            user=user,
        )
        return ImageResponse.from_dict(await self._client._request("POST", PATH, json=body))
