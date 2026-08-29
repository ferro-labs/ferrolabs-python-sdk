"""Image generation resource."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..types import ImageResponse

if TYPE_CHECKING:
    from ..client import FerroClient

PATH = "/v1/images/generations"


def build_body(model: str, prompt: str, **optional: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "prompt": prompt}
    body.update({k: v for k, v in optional.items() if v is not None})
    return body


class Images:
    def __init__(self, client: FerroClient) -> None:
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
        return ImageResponse.from_dict(self._client._request("POST", PATH, json=body))
