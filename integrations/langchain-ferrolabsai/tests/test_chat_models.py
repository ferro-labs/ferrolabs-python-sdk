"""Tests for FerroChatModel."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel
from pytest_httpx import HTTPXMock

from langchain_ferrolabsai import FerroChatModel

from .conftest import BASE_URL, GATEWAY_HEADERS, TRACE_ID, make_chat_completion, sse_chunks

CHAT_URL = f"{BASE_URL}/v1/chat/completions"


def _build_chat(**overrides) -> FerroChatModel:
    kwargs = {"model": "gpt-4o", "base_url": BASE_URL, "api_key": "sk-ferro-test"}
    kwargs.update(overrides)
    return FerroChatModel(**kwargs)  # type: ignore[arg-type]


class TestBasicGeneration:
    def test_invoke_returns_ai_message_with_content(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, json=make_chat_completion(content="hi there")
        )
        result = _build_chat().invoke([HumanMessage(content="Hello")])
        assert isinstance(result, AIMessage)
        assert result.content == "hi there"

    def test_response_metadata_is_exactly_what_the_gateway_provides(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, json=make_chat_completion(), headers=GATEWAY_HEADERS
        )
        result = _build_chat().invoke([HumanMessage(content="Hello")])
        expected = {
            "model": "gpt-4o",
            "id": "cmpl-1",
            "trace_id": TRACE_ID,
            "provider": "openai",
            "gateway_overhead_ms": 1.5,
        }
        # LangChain adds generation_info (finish_reason) on top; every gateway field is exact.
        assert {k: result.response_metadata[k] for k in expected} == expected

    def test_response_metadata_strips_absent_fields(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=make_chat_completion())
        result = _build_chat().invoke([HumanMessage(content="Hello")])
        assert "trace_id" not in result.response_metadata
        assert "gateway_overhead_ms" not in result.response_metadata
        assert result.response_metadata["provider"] == "openai"

    def test_invoke_attaches_usage_metadata(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=make_chat_completion())
        result = _build_chat().invoke([HumanMessage(content="Hello")])
        assert result.usage_metadata == {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}


class TestMessageConversion:
    def test_system_human_messages_serialized_correctly(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=make_chat_completion())
        _build_chat().invoke([SystemMessage(content="be terse"), HumanMessage(content="hi")])
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["messages"] == [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ]

    def test_tool_messages_carry_tool_call_id(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=make_chat_completion())
        _build_chat().invoke(
            [
                HumanMessage(content="what is 1+1"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "c1", "name": "add", "args": {"a": 1, "b": 1}}],
                ),
                ToolMessage(content="2", tool_call_id="c1"),
            ]
        )
        tool_msg = json.loads(httpx_mock.get_requests()[0].content)["messages"][-1]
        assert tool_msg == {"role": "tool", "tool_call_id": "c1", "content": "2"}


class TestRequestParams:
    def test_sends_auth_header(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=make_chat_completion())
        _build_chat(api_key="sk-ferro-prod").invoke([HumanMessage(content="hi")])
        assert httpx_mock.get_requests()[0].headers["Authorization"] == "Bearer sk-ferro-prod"

    def test_forwards_sampling_params_user_and_model_kwargs(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=make_chat_completion())
        chat = _build_chat(
            temperature=0.2, max_tokens=64, user="user-123", model_kwargs={"seed": 7}
        )
        chat.invoke([HumanMessage(content="hi")])
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 64
        assert body["user"] == "user-123"
        assert body["seed"] == 7
        for dead in ("route_tag", "x_route_tag", "template_id", "template_variables"):
            assert dead not in body

    def test_dead_gateway_fields_are_not_model_fields(self):
        chat = _build_chat()
        for dead in ("route_tag", "template_id", "template_variables"):
            assert dead not in type(chat).model_fields


class TestToolBinding:
    def test_bind_tools_forwards_openai_tool_schema(self, httpx_mock: HTTPXMock):
        @tool
        def add(a: int, b: int) -> int:
            """Add two integers."""
            return a + b

        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=make_chat_completion(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "add", "arguments": '{"a":1,"b":2}'},
                    }
                ],
            ),
        )
        result = _build_chat().bind_tools([add]).invoke([HumanMessage(content="add 1 and 2")])
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["tools"][0]["type"] == "function"
        assert body["tools"][0]["function"]["name"] == "add"
        assert result.tool_calls == [
            {"id": "call_1", "name": "add", "args": {"a": 1, "b": 2}, "type": "tool_call"}
        ]


class TestStreaming:
    def test_stream_yields_chunks_with_trace_id(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            content=sse_chunks("Hel", "lo"),
            headers={"Content-Type": "text/event-stream", **GATEWAY_HEADERS},
        )
        chunks = list(_build_chat().stream([HumanMessage(content="hi")]))
        assert "".join(c.content for c in chunks) == "Hello"
        assert chunks[0].response_metadata["trace_id"] == TRACE_ID

    def test_stream_yields_tool_call_chunks(self, httpx_mock: HTTPXMock):
        frames = [
            {
                "id": "1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "add", "arguments": '{"a":1'},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [{"index": 0, "function": {"arguments": ',"b":2}'}}]
                        },
                        "finish_reason": None,
                    }
                ],
            },
        ]
        sse_body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            content=sse_body.encode("utf-8"),
            headers={"Content-Type": "text/event-stream"},
        )
        chunks = list(_build_chat().stream([HumanMessage(content="add 1 and 2")]))
        tool_chunks = [tc for chunk in chunks for tc in chunk.tool_call_chunks]
        assert tool_chunks[0]["id"] == "call_1"
        assert tool_chunks[0]["name"] == "add"
        assert tool_chunks[0]["args"] == '{"a":1'
        assert tool_chunks[1]["args"] == ',"b":2}'


class TestAsync:
    async def test_ainvoke(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=make_chat_completion(content="async hi"),
            headers=GATEWAY_HEADERS,
        )
        result = await _build_chat().ainvoke([HumanMessage(content="hi")])
        assert result.content == "async hi"
        assert result.response_metadata["trace_id"] == TRACE_ID
        assert result.usage_metadata["total_tokens"] == 8

    async def test_astream(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            content=sse_chunks("a", "b", "c"),
            headers={"Content-Type": "text/event-stream", **GATEWAY_HEADERS},
        )
        chunks = [c async for c in _build_chat().astream([HumanMessage(content="hi")])]
        assert "".join(c.content for c in chunks) == "abc"
        assert chunks[0].response_metadata["trace_id"] == TRACE_ID
        assert json.loads(httpx_mock.get_requests()[0].content)["stream"] is True


class Answer(BaseModel):
    city: str
    population: int


class TestStructuredOutput:
    def test_pydantic_schema_uses_json_schema_response_format(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=make_chat_completion(content='{"city": "Paris", "population": 2100000}'),
        )
        structured = _build_chat().with_structured_output(Answer)
        result = structured.invoke([HumanMessage(content="Biggest city in France?")])
        assert result == Answer(city="Paris", population=2100000)
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["name"] == "Answer"
        assert "city" in body["response_format"]["json_schema"]["schema"]["properties"]

    def test_dict_schema_returns_dict(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, json=make_chat_completion(content='{"ok": true}')
        )
        schema = {"title": "Flag", "type": "object", "properties": {"ok": {"type": "boolean"}}}
        result = _build_chat().with_structured_output(schema).invoke("ready?")
        assert result == {"ok": True}
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["response_format"]["json_schema"] == {"name": "Flag", "schema": schema}

    def test_include_raw(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, json=make_chat_completion(content="not json")
        )
        result = _build_chat().with_structured_output(Answer, include_raw=True).invoke("?")
        assert isinstance(result["raw"], AIMessage)
        assert result["parsed"] is None
        assert result["parsing_error"] is not None


class TestIdentity:
    def test_llm_type(self):
        assert _build_chat()._llm_type == "ferro-labs-chat"

    def test_identifying_params_include_model(self):
        params = _build_chat(temperature=0.5)._identifying_params
        assert params["model"] == "gpt-4o"
        assert params["temperature"] == 0.5


class TestApiKeyHandling:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("FERRO_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        chat = FerroChatModel(model="gpt-4o", base_url=BASE_URL)  # no api_key
        with pytest.raises(Exception):
            chat.invoke([HumanMessage(content="hi")])
