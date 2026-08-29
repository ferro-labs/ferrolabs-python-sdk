"""Moderations resource (``POST /v1/moderations``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import FerroClient

PATH = "/v1/moderations"


def build_body(input: str | list[str], model: str | None, **kwargs: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"input": input, **kwargs}
    if model is not None:
        body["model"] = model
    return body


class Moderations:
    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def create(
        self, *, input: str | list[str], model: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """``POST /v1/moderations`` — returns the provider's ``{id, model, results[]}`` JSON."""
        return self._client._request("POST", PATH, json=build_body(input, model, **kwargs))
