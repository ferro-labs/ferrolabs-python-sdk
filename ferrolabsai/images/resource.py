"""Image generation resource."""

from __future__ import annotations

from typing import Any

from ..types import ImageResponse


class Images:
    def __init__(self, client: Any) -> None:
        self._client = client

    def generate(
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
        """
        Generate images from a text prompt.

        Args:
            model: Image model. E.g. "dall-e-3", "dall-e-2".
            prompt: Text description of the desired image.
            n: Number of images to generate (1–10).
            size: "256x256", "512x512", "1024x1024", "1792x1024", "1024x1792".
            quality: "standard" or "hd" (dall-e-3 only).
            response_format: "url" (default) or "b64_json".

        Example::

            response = client.images.generate(
                model="dall-e-3",
                prompt="A futuristic AI gateway routing requests across the cosmos",
                size="1024x1024",
            )
            print(response.data[0].url)
        """
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

        data = self._client._request("POST", "/v1/images/generations", json=body)
        return ImageResponse.from_dict(data)
