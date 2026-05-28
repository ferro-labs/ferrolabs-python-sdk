"""Tests for FerroChatModel."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pytest_httpx import HTTPXMock

from langchain_ferrolabsai import FerroChatModel

from .conftest import BASE_URL, make_chat_completion


def _build_chat(**overrides) -> FerroChatModel:
    kwargs = {"model": "gpt-4o", "base_url": BASE_URL, "api_key": "sk-ferro-test"}
    kwargs.update(overrides)
    return FerroChatModel(**kwargs)  # type: ignore[arg-type]


class TestBasicGeneration:
    def test_invoke_returns_ai_message_with_content(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(content="hi there"),
        )
        chat = _build_chat()
        result = chat.invoke([HumanMessage(content="Hello")])
        assert isinstance(result, AIMessage)
        assert result.content == "hi there"

    def test_invoke_surfaces_trace_id_in_response_metadata(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(trace_id="my-trace-xyz"),
        )
        chat = _build_chat()
        result = chat.invoke([HumanMessage(content="Hello")])
        # trace_id is the join key for v1.2 observability bridges — MUST be present.
        assert result.response_metadata["trace_id"] == "my-trace-xyz"
        assert result.response_metadata["provider"] == "openai"
        assert result.response_metadata["latency_ms"] == 42
        assert result.response_metadata["cost_usd"] == 0.000123

    def test_invoke_surfaces_header_only_gateway_metadata(self, httpx_mock: HTTPXMock):
        body = make_chat_completion(trace_id="body-trace", provider="body-provider")
        body.pop("x_ferro_trace_id")
        body.pop("x_ferro_provider")
        body.pop("x_ferro_latency_ms")
        body["usage"].pop("cost_usd")
        body["usage"].pop("provider")
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=body,
            headers={
                "X-Request-ID": "header-trace",
                "x-ferro-provider": "openai",
                "x-ferro-latency-ms": "42",
                "x-ferro-cost-usd": "0.000123",
            },
        )
        chat = _build_chat()
        result = chat.invoke([HumanMessage(content="Hello")])
        assert result.response_metadata["trace_id"] == "header-trace"
        assert result.response_metadata["provider"] == "openai"
        assert result.response_metadata["latency_ms"] == 42
        assert result.response_metadata["cost_usd"] == 0.000123

    def test_invoke_attaches_usage_metadata(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(),
        )
        chat = _build_chat()
        result = chat.invoke([HumanMessage(content="Hello")])
        assert result.usage_metadata == {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
        }


class TestMessageConversion:
    def test_system_human_messages_serialized_correctly(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(),
        )
        chat = _build_chat()
        chat.invoke([SystemMessage(content="be terse"), HumanMessage(content="hi")])

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["messages"] == [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ]

    def test_tool_messages_carry_tool_call_id(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(),
        )
        chat = _build_chat()
        chat.invoke(
            [
                HumanMessage(content="what is 1+1"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "c1", "name": "add", "args": {"a": 1, "b": 1}}],
                ),
                ToolMessage(content="2", tool_call_id="c1"),
            ]
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        tool_msg = body["messages"][-1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "c1"
        assert tool_msg["content"] == "2"


class TestRequestParams:
    def test_sends_auth_header(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(),
        )
        chat = _build_chat(api_key="sk-ferro-prod")
        chat.invoke([HumanMessage(content="hi")])
        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer sk-ferro-prod"

    def test_forwards_temperature_and_max_tokens(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(),
        )
        chat = _build_chat(temperature=0.2, max_tokens=64)
        chat.invoke([HumanMessage(content="hi")])
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 64

    def test_forwards_ferro_extras(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=make_chat_completion(),
        )
        chat = _build_chat(
            route_tag="premium",
            template_id="customer-support",
            template_variables={"tone": "friendly"},
            user="user-123",
        )
        chat.invoke([HumanMessage(content="hi")])
        body = json.loads(httpx_mock.get_requests()[0].content)
        # Ferro forwards `route_tag` as `x_route_tag` internally; we just
        # check the field round-trips through the SDK's request builder.
        assert body.get("x_route_tag") == "premium"
        assert body["template_id"] == "customer-support"
        assert body["template_variables"] == {"tone": "friendly"}
        assert body["user"] == "user-123"


class TestToolBinding:
    def test_bind_tools_forwards_openai_tool_schema(self, httpx_mock: HTTPXMock):
        @tool
        def add(a: int, b: int) -> int:
            """Add two integers."""
            return a + b

        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
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
        chat = _build_chat().bind_tools([add])
        result = chat.invoke([HumanMessage(content="add 1 and 2")])

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["tools"][0]["type"] == "function"
        assert body["tools"][0]["function"]["name"] == "add"

        assert result.tool_calls == [
            {"id": "call_1", "name": "add", "args": {"a": 1, "b": 2}, "type": "tool_call"}
        ]


class TestStreaming:
    def test_stream_yields_chunks(self, httpx_mock: HTTPXMock):
        sse_body = (
            'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4o",'
            '"choices":[{"index":0,"delta":{"role":"assistant","content":"Hel"},"finish_reason":null}]}\n\n'
            'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4o",'
            '"choices":[{"index":0,"delta":{"content":"lo"},"finish_reason":null}]}\n\n'
            'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4o",'
            '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            content=sse_body.encode("utf-8"),
            headers={"Content-Type": "text/event-stream"},
        )
        chat = _build_chat()
        chunks = list(chat.stream([HumanMessage(content="hi")]))
        assert "".join(c.content for c in chunks) == "Hello"

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
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": ',"b":2}'}}
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            },
        ]
        sse_body = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)
        sse_body += "data: [DONE]\n\n"
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            content=sse_body.encode("utf-8"),
            headers={"Content-Type": "text/event-stream"},
        )
        chat = _build_chat()
        chunks = list(chat.stream([HumanMessage(content="add 1 and 2")]))
        tool_chunks = [tc for chunk in chunks for tc in chunk.tool_call_chunks]
        assert tool_chunks[0]["id"] == "call_1"
        assert tool_chunks[0]["name"] == "add"
        assert tool_chunks[0]["args"] == '{"a":1'
        assert tool_chunks[1]["args"] == ',"b":2}'



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
        # FerroClient construction happens lazily on first call.
        with pytest.raises(Exception):
            chat.invoke([HumanMessage(content="hi")])
