"""Synchronous chat completions resource."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from ..streaming import Stream
from ..types import ChatCompletion

if TYPE_CHECKING:
    from ..client import FerroClient

PATH = "/v1/chat/completions"


def build_body(
    model: str, messages: list[dict[str, Any]], stream: bool, **optional: Any
) -> dict[str, Any]:
    """OpenAI-shaped request body; ``None`` optionals are omitted."""
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
    body.update({k: v for k, v in optional.items() if v is not None})
    return body


class Completions:
    def __init__(self, client: FerroClient) -> None:
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
    ) -> Stream: ...

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_completion_tokens: int | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        stop: str | list[str] | None = None,
        seed: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        parallel_tool_calls: bool | None = None,
        response_format: dict[str, Any] | None = None,
        stream_options: dict[str, Any] | None = None,
        user: str | None = None,
        **kwargs: Any,
    ) -> ChatCompletion | Stream:
        """
        Create a chat completion (OpenAI-compatible).

        Args:
            model: Model name. The gateway routes it to the right provider, e.g.
                "gpt-4o" → OpenAI, "claude-3-5-sonnet-20241022" → Anthropic.
            messages: List of message dicts with "role" and "content".
            stream: If True, returns a :class:`~ferrolabsai.Stream` of chunks that
                also carries ``trace_id`` / ``provider`` from the response headers.
            max_completion_tokens: Supersedes ``max_tokens`` (both are accepted).
            stream_options: e.g. ``{"include_usage": True}`` to receive a terminal
                chunk with ``usage`` (only honoured when ``stream=True``).
            response_format: e.g. ``{"type": "json_object"}`` or a ``json_schema`` spec.
            **kwargs: Any other OpenAI parameter is forwarded verbatim.

        Example::

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
            )
            print(response.content, response.provider, response.trace_id)

            # Streaming
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                print(chunk.choices[0].delta.content or "", end="", flush=True)
        """
        body = build_body(
            model,
            messages,
            stream,
            temperature=temperature,
            max_tokens=max_tokens,
            max_completion_tokens=max_completion_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
            seed=seed,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            response_format=response_format,
            stream_options=stream_options,
            user=user,
            **kwargs,
        )
        if stream:
            return Stream(self._client._open_stream(PATH, body))
        return ChatCompletion.from_dict(self._client._request("POST", PATH, json=body))
