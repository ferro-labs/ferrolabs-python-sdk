"""Async chat completions resource."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..types import ChatCompletion, ChatCompletionChunk


class AsyncCompletions:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        stop: str | list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        template_id: str | None = None,
        template_variables: dict[str, Any] | None = None,
        route_tag: str | None = None,
        user: str | None = None,
        **kwargs: Any,
    ) -> ChatCompletion | AsyncIterator[ChatCompletionChunk]:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}

        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if top_p is not None:
            body["top_p"] = top_p
        if frequency_penalty is not None:
            body["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            body["presence_penalty"] = presence_penalty
        if stop is not None:
            body["stop"] = stop
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if user is not None:
            body["user"] = user
        if template_id is not None:
            body["template_id"] = template_id
        if template_variables is not None:
            body["template_variables"] = template_variables
        if route_tag is not None:
            body["x_route_tag"] = route_tag

        body.update(kwargs)

        if stream:
            return self._stream("/v1/chat/completions", body)

        data = await self._client._request("POST", "/v1/chat/completions", json=body)
        return ChatCompletion.from_dict(data)

    async def _stream(self, path: str, body: dict[str, Any]) -> AsyncIterator[ChatCompletionChunk]:
        async with self._client._http.stream("POST", path, json=body) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                await response.aread()
                from ..client import _raise_api_error

                _raise_api_error(e)
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        yield ChatCompletionChunk.from_dict(json.loads(payload))
                    except json.JSONDecodeError:
                        continue
