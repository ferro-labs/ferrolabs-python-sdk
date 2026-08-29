"""FerroChatModel — LangChain ``BaseChatModel`` backed by Ferro Labs AI Gateway.

A single ``FerroChatModel`` instance can address any of the gateway's 30
providers by name (e.g. ``"gpt-4o"``, ``"claude-3-5-sonnet-20241022"``,
``"gemini-2.5-flash"``) without changing the model class.

``response_metadata`` carries exactly what the gateway provides: ``model``,
``id``, ``trace_id`` (the ``X-Request-ID`` response header — the join key for
the gateway's request log and observability exporters), ``provider`` (body
field), and ``gateway_overhead_ms`` (``X-Gateway-Overhead-Ms`` header).
Absent values are stripped.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator, Sequence
from operator import itemgetter
from typing import TYPE_CHECKING, Any, cast

from ferrolabsai import AsyncFerroClient, ChatCompletion, ChatCompletionChunk, FerroClient
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable, RunnableMap, RunnablePassthrough
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr

from ._messages import messages_to_ferro_dicts

if TYPE_CHECKING:
    from langchain_core.messages import ToolCallChunk


class FerroChatModel(BaseChatModel):
    """Chat model that talks to the Ferro Labs AI Gateway.

    Example::

        from langchain_ferrolabsai import FerroChatModel
        from langchain_core.messages import HumanMessage

        chat = FerroChatModel(model="gpt-4o", api_key="fgw_...")
        response = chat.invoke([HumanMessage(content="Hello")])
        print(response.content)
        print(response.response_metadata["trace_id"])  # gateway X-Request-ID
    """

    model: str = Field(..., description="Model name routed by the gateway.")
    base_url: str | None = Field(
        default=None,
        description="Gateway URL. Defaults to FERRO_BASE_URL env var or http://localhost:8080.",
    )
    api_key: SecretStr | None = Field(
        default=None,
        description="API key. Defaults to FERRO_API_KEY env var.",
    )
    timeout: float = 120.0
    max_retries: int = 2

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: list[str] | None = None
    user: str | None = None

    default_headers: dict[str, str] | None = None
    model_kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    _client_instance: FerroClient | None = PrivateAttr(default=None)
    _async_client_instance: AsyncFerroClient | None = PrivateAttr(default=None)

    # ------------------------------------------------------------------
    # LangChain identification
    # ------------------------------------------------------------------

    @property
    def _llm_type(self) -> str:
        return "ferro-labs-chat"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    # ------------------------------------------------------------------
    # Client access
    # ------------------------------------------------------------------

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key.get_secret_value() if self.api_key else None,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "default_headers": self.default_headers,
        }

    def _get_client(self) -> FerroClient:
        if self._client_instance is None:
            self._client_instance = FerroClient(**self._client_kwargs())
        return self._client_instance

    def _get_async_client(self) -> AsyncFerroClient:
        if self._async_client_instance is None:
            self._async_client_instance = AsyncFerroClient(**self._client_kwargs())
        return self._async_client_instance

    # ------------------------------------------------------------------
    # Request payload assembly
    # ------------------------------------------------------------------

    def _build_request_params(
        self,
        stop: list[str] | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"model": self.model}
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.frequency_penalty is not None:
            params["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            params["presence_penalty"] = self.presence_penalty
        effective_stop = stop if stop is not None else self.stop
        if effective_stop:
            params["stop"] = effective_stop
        if self.user is not None:
            params["user"] = self.user
        # model_kwargs first so explicit per-call kwargs win.
        params.update(self.model_kwargs)
        params.update(kwargs)
        return params

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        params = self._build_request_params(stop, **kwargs)
        response = self._get_client().chat.completions.create(
            messages=messages_to_ferro_dicts(messages),
            **params,
        )
        return _completion_to_chat_result(response)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        params = self._build_request_params(stop, **kwargs)
        response = await self._get_async_client().chat.completions.create(
            messages=messages_to_ferro_dicts(messages),
            **params,
        )
        return _completion_to_chat_result(response)

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        params = self._build_request_params(stop, **kwargs)
        stream = self._get_client().chat.completions.create(
            messages=messages_to_ferro_dicts(messages),
            stream=True,
            **params,
        )
        first = True
        for chunk in stream:
            generation_chunk = _chunk_to_generation(chunk, first)
            if generation_chunk is None:
                continue
            first = False
            if run_manager is not None:
                run_manager.on_llm_new_token(
                    cast("str", generation_chunk.message.content), chunk=generation_chunk
                )
            yield generation_chunk

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        params = self._build_request_params(stop, **kwargs)
        stream = await self._get_async_client().chat.completions.create(
            messages=messages_to_ferro_dicts(messages),
            stream=True,
            **params,
        )
        first = True
        async for chunk in stream:
            generation_chunk = _chunk_to_generation(chunk, first)
            if generation_chunk is None:
                continue
            first = False
            if run_manager is not None:
                await run_manager.on_llm_new_token(
                    cast("str", generation_chunk.message.content), chunk=generation_chunk
                )
            yield generation_chunk

    # ------------------------------------------------------------------
    # Tool binding (LangGraph / agent support) and structured output
    # ------------------------------------------------------------------

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool | Any],
        *,
        tool_choice: Any | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        formatted = [convert_to_openai_tool(t) for t in tools]
        bind_kwargs: dict[str, Any] = {"tools": formatted}
        if tool_choice is not None:
            bind_kwargs["tool_choice"] = tool_choice
        bind_kwargs.update(kwargs)
        return cast("Runnable[LanguageModelInput, AIMessage]", super().bind(**bind_kwargs))

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        """Constrain the model to ``schema`` via OpenAI-style
        ``response_format={"type": "json_schema", ...}`` and parse the reply.

        ``schema`` is a pydantic ``BaseModel`` subclass (parsed into an instance)
        or a JSON-schema dict (parsed into a dict). With ``include_raw=True`` the
        output is ``{"raw": AIMessage, "parsed": ..., "parsing_error": ...}``.
        """
        parser: Runnable[Any, Any]
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            name, json_schema = schema.__name__, schema.model_json_schema()
            parser = PydanticOutputParser(pydantic_object=schema)
        elif isinstance(schema, dict):
            name, json_schema = str(schema.get("title", "output")), schema
            parser = JsonOutputParser()
        else:
            raise TypeError("schema must be a pydantic BaseModel subclass or a JSON-schema dict")
        llm = self.bind(
            response_format={
                "type": "json_schema",
                "json_schema": {"name": name, "schema": json_schema},
            },
            **kwargs,
        )
        if not include_raw:
            return cast("Runnable[LanguageModelInput, dict[str, Any] | BaseModel]", llm | parser)
        parse = RunnablePassthrough.assign(
            parsed=itemgetter("raw") | parser, parsing_error=lambda _: None
        )
        fallback = RunnablePassthrough.assign(parsed=lambda _: None)
        chain = RunnableMap(raw=llm) | parse.with_fallbacks(
            [fallback], exception_key="parsing_error"
        )
        return cast("Runnable[LanguageModelInput, dict[str, Any] | BaseModel]", chain)


# ---------------------------------------------------------------------------
# Response mapping
# ---------------------------------------------------------------------------


def _completion_to_chat_result(response: ChatCompletion) -> ChatResult:
    """Convert a Ferro ``ChatCompletion`` into a LangChain ``ChatResult``."""
    metadata = _response_metadata(response)
    if not response.choices:
        empty = AIMessage(content="", response_metadata=metadata)
        return ChatResult(generations=[ChatGeneration(message=empty)])

    choice = response.choices[0]
    ai_message = AIMessage(
        content=choice.message.content or "",
        tool_calls=_extract_tool_calls(choice.message.tool_calls),
        response_metadata=metadata,
        usage_metadata=_usage_metadata(response),
    )
    generation = ChatGeneration(
        message=ai_message,
        generation_info={"finish_reason": choice.finish_reason} if choice.finish_reason else None,
    )
    # LangChain merges llm_output into response_metadata; keep them identical.
    return ChatResult(generations=[generation], llm_output=metadata)


def _response_metadata(response: ChatCompletion) -> dict[str, Any]:
    """Exactly the fields ai-gateway provides; ``None`` values are stripped."""
    metadata: dict[str, Any] = {
        "model": response.model,
        "id": response.id,
        "trace_id": response.trace_id,
        "provider": response.provider,
        "gateway_overhead_ms": response.gateway_overhead_ms,
    }
    return {k: v for k, v in metadata.items() if v is not None}


def _usage_metadata(response: ChatCompletion | ChatCompletionChunk) -> UsageMetadata | None:
    if response.usage is None:
        return None
    return UsageMetadata(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
    )


def _chunk_to_generation(chunk: ChatCompletionChunk, first: bool) -> ChatGenerationChunk | None:
    """Map one SSE chunk to a ``ChatGenerationChunk``. The terminal usage-only chunk
    becomes an empty message carrying ``usage_metadata`` (so it survives chunk
    aggregation); a chunk with neither choices nor usage yields ``None``. Stream
    metadata rides on the first chunk."""
    if not chunk.choices:
        usage = _usage_metadata(chunk)
        if usage is None:
            return None
        return ChatGenerationChunk(message=AIMessageChunk(content="", usage_metadata=usage))
    choice = chunk.choices[0]
    metadata = {k: v for k, v in (("trace_id", chunk.trace_id), ("provider", chunk.provider)) if v}
    ai_chunk = AIMessageChunk(
        content=choice.delta.content or "",
        tool_call_chunks=_extract_tool_call_chunks(choice.delta.tool_calls),
        response_metadata=metadata if first else {},
    )
    return ChatGenerationChunk(
        message=ai_chunk,
        generation_info={"finish_reason": choice.finish_reason} if choice.finish_reason else None,
    )


def _extract_tool_call_chunks(raw: list[dict[str, Any]] | None) -> list[ToolCallChunk]:
    """Map OpenAI streaming tool-call deltas to LangChain chunk shape."""
    if not raw:
        return []
    result: list[ToolCallChunk] = []
    for call in raw:
        function = call.get("function", {}) or {}
        chunk: dict[str, Any] = {"type": "tool_call_chunk"}
        if call.get("id") is not None:
            chunk["id"] = call.get("id")
        if call.get("index") is not None:
            chunk["index"] = call.get("index")
        if function.get("name") is not None:
            chunk["name"] = function.get("name")
        if function.get("arguments") is not None:
            chunk["args"] = function.get("arguments")
        result.append(cast("ToolCallChunk", chunk))
    return result


def _extract_tool_calls(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Map OpenAI-style tool calls to LangChain's expected shape."""
    if not raw:
        return []
    result: list[dict[str, Any]] = []
    for call in raw:
        function = call.get("function", {})
        args_raw = function.get("arguments", "{}")
        if isinstance(args_raw, str):
            try:
                args: Any = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                args = {"_raw": args_raw}
        else:
            args = args_raw
        result.append(
            {
                "id": call.get("id", ""),
                "name": function.get("name", ""),
                "args": args,
                "type": "tool_call",
            }
        )
    return result
