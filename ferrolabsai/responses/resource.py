"""Responses API resource (OpenAI-style ``/v1/responses``).

``POST /v1/responses`` is model-routed, governed, and priced like chat.
The id sub-routes (``GET`` / ``DELETE /v1/responses/{id}``) carry no model
and pin to the gateway's ``responses_target``; without one configured the
gateway answers 501 ``not_implemented``. Streaming (``stream=True``) is not
wrapped in 0.3.0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..types import Response

if TYPE_CHECKING:
    from ..client import FerroClient

PATH = "/v1/responses"


class Responses:
    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def create(self, **params: Any) -> Response:
        """``POST /v1/responses`` — parameters are forwarded verbatim, e.g.
        ``create(model="gpt-4o", input="Hello", instructions="Be brief")``."""
        return Response.from_dict(self._client._request("POST", PATH, json=params))

    def retrieve(self, response_id: str) -> Response:
        """``GET /v1/responses/{id}`` — 501 unless the gateway sets ``responses_target``."""
        return Response.from_dict(self._client._request("GET", f"{PATH}/{response_id}"))

    def delete(self, response_id: str) -> dict[str, Any]:
        """``DELETE /v1/responses/{id}`` — 501 unless the gateway sets ``responses_target``."""
        return self._client._request("DELETE", f"{PATH}/{response_id}")
