"""FerroChatModel — LangChain ``BaseChatModel`` backed by Ferro Labs AI Gateway.

A single ``FerroChatModel`` instance can address any of the gateway's 30+
providers by name (e.g. ``"gpt-4o"``, ``"claude-3-5-sonnet-20241022"``,
``"gemini-1.5-flash"``) without changing the model class.

Every response surfaces ``trace_id`` (the Ferro request ID propagated via the
``x-trace-id`` header — frozen contract since ``ai-gateway v1.1.0``) in
``response_metadata``. That value is the join key for any downstream
observability bridge plugin (LangSmith, Langfuse, Phoenix, …) that ships in
``ferro-labs/ai-gateway-plugins``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Any

from ferrolabsai import ChatCompletion, FerroClient
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field, PrivateAttr, SecretStr

from ._messages import messages_to_ferro_dicts


class FerroChatModel(BaseChatModel):
    """Chat model that talks to the Ferro Labs AI Gateway.

    Example::

        from langchain_ferrolabsai import FerroChatModel
        from langchain_core.messages import HumanMessage

        chat = FerroChatModel(model="gpt-4o", api_key="sk-ferro-...")
        response = chat.invoke([HumanMessage(content="Hello")])
        print(response.content)
        print(response.response_metadata["trace_id"])  # Ferro request ID
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

    # Ferro-specific extras
    route_tag: str | None = Field(
        default=None,
        description="Override the gateway's routing strategy for this caller.",
    )
    template_id: str | None = None
    template_variables: dict[str, Any] | None = None
    user: str | None = None

    default_headers: dict[str, str] | None = None
    model_kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    _client_instance: FerroClient | None = PrivateAttr(default=None)

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

    def _get_client(self) -> FerroClient:
        if self._client_instance is None:
            self._client_instance = FerroClient(
                api_key=self.api_key.get_secret_value() if self.api_key else None,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                default_headers=self.default_headers,
            )
        return self._client_instance

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
        if self.route_tag is not None:
            params["route_tag"] = self.route_tag
        if self.template_id is not None:
            params["template_id"] = self.template_id
        if self.template_variables is not None:
            params["template_variables"] = self.template_variables
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
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = delta.content or ""
            ai_chunk = AIMessageChunk(
                content=content,
                tool_call_chunks=_extract_tool_call_chunks(delta.tool_calls),
            )
            generation_chunk = ChatGenerationChunk(
                message=ai_chunk,
                generation_info={"finish_reason": chunk.choices[0].finish_reason}
                if chunk.choices[0].finish_reason
                else None,
            )
            if run_manager is not None:
                run_manager.on_llm_new_token(content, chunk=generation_chunk)
            yield generation_chunk

    # ------------------------------------------------------------------
    # Tool binding (LangGraph / agent support)
    # ------------------------------------------------------------------

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool | Any],
        *,
        tool_choice: Any | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        formatted = [convert_to_openai_tool(t) for t in tools]
        bind_kwargs: dict[str, Any] = {"tools": formatted}
        if tool_choice is not None:
            bind_kwargs["tool_choice"] = tool_choice
        bind_kwargs.update(kwargs)
        return super().bind(**bind_kwargs)


# ---------------------------------------------------------------------------
# Response mapping
# ---------------------------------------------------------------------------


def _completion_to_chat_result(response: ChatCompletion) -> ChatResult:
    """Convert a Ferro ``ChatCompletion`` into a LangChain ``ChatResult``."""
    if not response.choices:
        empty = AIMessage(
            content="",
            response_metadata=_response_metadata(response),
        )
        return ChatResult(generations=[ChatGeneration(message=empty)])

    choice = response.choices[0]
    tool_calls = _extract_tool_calls(choice.message.tool_calls)
    ai_message = AIMessage(
        content=choice.message.content or "",
        tool_calls=tool_calls,
        response_metadata=_response_metadata(response),
        usage_metadata=_usage_metadata(response),
    )
    generation = ChatGeneration(
        message=ai_message,
        generation_info={"finish_reason": choice.finish_reason} if choice.finish_reason else None,
    )
    return ChatResult(
        generations=[generation],
        llm_output={
            "model": response.model,
            "trace_id": response.trace_id,
            "provider": response.provider,
        },
    )


def _response_metadata(response: ChatCompletion) -> dict[str, Any]:
    """The Ferro-specific surface every consumer (incl. v1.2 observability bridges) reads."""
    metadata: dict[str, Any] = {
        "model": response.model,
        "id": response.id,
        # ``trace_id`` is the canonical join key. Frozen via x-trace-id since
        # ai-gateway v1.1.0; mirrored by every Ferro observability bridge plugin.
        "trace_id": response.trace_id,
        "provider": response.provider,
        "latency_ms": response.latency_ms,
    }
    if response.usage is not None:
        metadata["cost_usd"] = response.usage.cost_usd
        metadata["cache_hit"] = response.usage.cache_hit
    return {k: v for k, v in metadata.items() if v is not None}


def _usage_metadata(response: ChatCompletion) -> dict[str, int] | None:
    if response.usage is None:
        return None
    return {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }


def _extract_tool_call_chunks(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Map OpenAI streaming tool-call deltas to LangChain chunk shape."""
    if not raw:
        return []
    result: list[dict[str, Any]] = []
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
        result.append(chunk)
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
