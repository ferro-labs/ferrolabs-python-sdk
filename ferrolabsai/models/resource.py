"""Model catalog resource.

The gateway serves exactly one catalog route, ``GET /v1/models``, and ignores
its query string. ``GET /v1/models/{id}`` is *not* a native route — it falls
through to the ``/v1/*`` pass-through and is forwarded upstream with the
operator's credential — so every lookup and filter here is client-side over
that one fetch.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from ..exceptions import FerroNotFoundError
from ..types import ModelInfo

if TYPE_CHECKING:
    from ..client import FerroClient

PATH = "/v1/models"


def parse_catalog(data: dict[str, Any]) -> builtins.list[ModelInfo]:
    return [ModelInfo.from_dict(m) for m in data.get("data", [])]


def filter_models(
    models: builtins.list[ModelInfo], provider: str | None, capability: str | None
) -> builtins.list[ModelInfo]:
    return [
        m
        for m in models
        if (provider is None or m.owned_by == provider)
        and (capability is None or capability in m.capabilities)
    ]


def find_model(models: builtins.list[ModelInfo], model_id: str) -> ModelInfo:
    for m in models:
        if m.id == model_id:
            return m
    raise FerroNotFoundError(
        f"Model {model_id!r} is not in the gateway catalog",
        status_code=404,
        code="model_not_found",
    )


def search_models(models: builtins.list[ModelInfo], query: str) -> builtins.list[ModelInfo]:
    needle = query.lower()
    return [m for m in models if needle in m.id.lower()]


class Models:
    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def _fetch(self) -> builtins.list[ModelInfo]:
        return parse_catalog(self._client._request("GET", PATH))

    def list(
        self,
        *,
        provider: str | None = None,
        capability: str | None = None,
    ) -> builtins.list[ModelInfo]:
        """
        List the models the gateway can route to (``GET /v1/models``).

        Args:
            provider: Keep only models whose ``owned_by`` matches, e.g. "openai".
            capability: Keep only models whose ``capabilities`` include this, e.g.
                "vision", "function_calling", "streaming", "reasoning".

        Filters are applied client-side — the gateway ignores query parameters.

        Example::

            models = client.models.list()
            claude_models = client.models.list(provider="anthropic")
            vision_models = client.models.list(capability="vision")
        """
        return filter_models(self._fetch(), provider, capability)

    def retrieve(self, model_id: str) -> ModelInfo:
        """
        Look one model up in the catalog. Raises :class:`FerroNotFoundError`
        (``code="model_not_found"``) locally; never calls ``/v1/models/{id}``.

        Example::

            info = client.models.retrieve("gpt-4o")
            print(f"Context window: {info.context_window}")
        """
        return find_model(self._fetch(), model_id)

    def search(self, query: str) -> builtins.list[ModelInfo]:
        """Case-insensitive substring match on model id, e.g. ``search("claude")``."""
        return search_models(self._fetch(), query)
