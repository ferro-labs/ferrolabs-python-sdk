"""Synchronous chat completions resource."""

from __future__ import annotations

import json
from typing import Any, Iterator, overload

from typing_extensions import Literal

from ..types import ChatCompletion, ChatCompletionChunk


class Completions:
    def __init__(self, client: Any) -> None:
        self._client = client

    @overload
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[False] = False,
        **kwargs: Any,
    ) -> ChatCompletion: ...

    @overload
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[True],
        **kwargs: Any,
    ) -> Iterator[ChatCompletionChunk]: ...

    def create(
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
        # Ferro-specific extras
        template_id: str | None = None,
        template_variables: dict[str, Any] | None = None,
        route_tag: str | None = None,
        user: str | None = None,
        **kwargs: Any,
    ) -> ChatCompletion | Iterator[ChatCompletionChunk]:
        """
        Create a chat completion. OpenAI-compatible with Ferro extras.

        Args:
            model: Model name. Ferro auto-routes to the correct provider.
                   E.g. "gpt-4o" → OpenAI, "claude-3-5-sonnet-20241022" → Anthropic.
            messages: List of message dicts with "role" and "content".
            stream: If True, returns an iterator of ChatCompletionChunk objects.
            template_id: Use a server-side prompt template (Ferro-specific).
            template_variables: Variables for the template (Ferro-specific).
            route_tag: Override routing strategy for this request (Ferro-specific).
            user: End-user identifier for per-user tracking (Ferro-specific).

        Returns:
            ChatCompletion or Iterator[ChatCompletionChunk] if stream=True.

        Example::

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
            )
            print(response.content)

            # Streaming
            for chunk in client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                stream=True,
            ):
                print(chunk.choices[0].delta.content or "", end="", flush=True)
        """
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        # Standard OpenAI params
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

        # Ferro-specific
        if template_id is not None:
            body["template_id"] = template_id
        if template_variables is not None:
            body["template_variables"] = template_variables
        if route_tag is not None:
            body["x_route_tag"] = route_tag

        body.update(kwargs)

        if stream:
            return self._stream("/v1/chat/completions", body)

        data = self._client._request("POST", "/v1/chat/completions", json=body)
        return ChatCompletion.from_dict(data)

    def _stream(self, path: str, body: dict[str, Any]) -> Iterator[ChatCompletionChunk]:
        """Yields parsed ChatCompletionChunk objects from an SSE stream."""
        for line in self._client._stream_request(path, body):
            if line.startswith("data: "):
                payload = line[6:].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk_data = json.loads(payload)
                    yield ChatCompletionChunk.from_dict(chunk_data)
                except json.JSONDecodeError:
                    continue
