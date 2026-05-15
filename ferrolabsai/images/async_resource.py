"""Async image generation resource."""

from __future__ import annotations

from typing import Any

from ..types import ImageResponse


class AsyncImages:
    def __init__(self, client: Any) -> None:
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
        body: dict[str, Any] = {"model": model, "prompt": prompt}
        if n is not None:
            body["n"] = n
        if size is not None:
            body["size"] = size
        if quality is not None:
            body["quality"] = quality
        if response_format is not None:
            body["response_format"] = response_format
        if style is not None:
            body["style"] = style
        if user is not None:
            body["user"] = user

        data = await self._client._request("POST", "/v1/images/generations", json=body)
        return ImageResponse.from_dict(data)
