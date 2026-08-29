"""Async chat completions resource."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from ..streaming import AsyncStream
from ..types import ChatCompletion
from .resource import PATH, build_body

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncCompletions:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    @overload
    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[False] = False,
        **kwargs: Any,
    ) -> ChatCompletion: ...

    @overload
    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[True],
        **kwargs: Any,
    ) -> AsyncStream: ...

    async def create(
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
    ) -> ChatCompletion | AsyncStream:
        """Async variant of :meth:`ferrolabsai.completions.resource.Completions.create`.

        With ``stream=True`` the awaited result is an :class:`~ferrolabsai.AsyncStream`::

            stream = await client.chat.completions.create(..., stream=True)
            async for chunk in stream:
                ...
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
            return AsyncStream(await self._client._open_stream(PATH, body))
        return ChatCompletion.from_dict(await self._client._request("POST", PATH, json=body))
