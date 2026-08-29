"""Chat completions: request body, non-streaming parsing, and SSE streaming."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ferrolabsai.exceptions import FerroAuthError, FerroRateLimitError, FerroStreamError
from ferrolabsai.streaming import AsyncStream, Stream

from .conftest import BASE_URL, COMPLETION_RESPONSE, TRACE_ID, chunk, sse

CHAT_URL = f"{BASE_URL}/v1/chat/completions"
MESSAGES = [{"role": "user", "content": "Hi"}]


class TestCreate:
    def test_basic_create(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        response = client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert response.id == "chatcmpl-abc123"
        assert response.model == "gpt-4o"
        assert response.content == "Hello from Ferro!"
        assert response.provider == "openai"
        assert response.usage.total_tokens == 15
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body == {"model": "gpt-4o", "messages": MESSAGES, "stream": False}

    def test_passes_optional_params(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        client.chat.completions.create(
            model="gpt-4o",
            messages=MESSAGES,
            temperature=0.7,
            max_tokens=100,
            max_completion_tokens=200,
            parallel_tool_calls=False,
            response_format={"type": "json_object"},
            seed=42,
            user="user_123",
            extra_field="passthrough",
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 100
        assert body["max_completion_tokens"] == 200
        assert body["parallel_tool_calls"] is False
        assert body["response_format"] == {"type": "json_object"}
        assert body["seed"] == 42
        assert body["user"] == "user_123"
        assert body["extra_field"] == "passthrough"

    def test_no_ferro_field_translation(self, client, httpx_mock: HTTPXMock):
        # route_tag/template_* were never read by the gateway; the SDK no longer
        # rewrites them (route_tag -> x_route_tag). Unknown kwargs pass through verbatim.
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        client.chat.completions.create(model="gpt-4o", messages=MESSAGES, route_tag="x")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["route_tag"] == "x"
        assert "x_route_tag" not in body

    def test_parses_gateway_body_extensions(self, client, httpx_mock: HTTPXMock):
        body = json.loads(json.dumps(COMPLETION_RESPONSE))
        body["provider_metadata"] = {"openai": {"system_fingerprint": "fp_1"}}
        body["choices"][0]["message"]["reasoning_content"] = "thinking..."
        body["usage"].update(
            {"reasoning_tokens": 3, "cache_read_tokens": 2, "cache_write_tokens": 1}
        )
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=body)
        response = client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert response.provider_metadata == {"openai": {"system_fingerprint": "fp_1"}}
        assert response.choices[0].message.reasoning_content == "thinking..."
        assert response.usage.reasoning_tokens == 3
        assert response.usage.cache_read_tokens == 2
        assert response.usage.cache_write_tokens == 1

    async def test_async_forwards_params(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=MESSAGES,
            frequency_penalty=0.5,
            presence_penalty=0.3,
            stream_options={"include_usage": True},
        )
        assert response.content == "Hello from Ferro!"
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["frequency_penalty"] == 0.5
        assert body["presence_penalty"] == 0.3
        assert body["stream_options"] == {"include_usage": True}


class TestStreaming:
    def test_sync_stream_yields_chunks_with_metadata(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            content=sse(chunk("Hello"), chunk(" world")),
            headers={"X-Request-ID": TRACE_ID, "X-Gateway-Provider": "openai"},
        )
        stream = client.chat.completions.create(model="gpt-4o", messages=MESSAGES, stream=True)
        assert isinstance(stream, Stream)
        assert stream.trace_id == TRACE_ID
        assert stream.provider == "openai"
        chunks = list(stream)
        assert [c.choices[0].delta.content for c in chunks] == ["Hello", " world"]
        assert chunks[0].trace_id == TRACE_ID
        assert chunks[0].provider == "openai"
        assert chunks[0].usage is None
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["stream"] is True

    def test_sync_stream_terminal_usage_chunk(self, client, httpx_mock: HTTPXMock):
        usage = {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
            "reasoning_tokens": 1,
        }
        terminal = chunk(usage=usage)
        terminal["choices"] = []
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse(chunk("x"), terminal))
        chunks = list(
            client.chat.completions.create(
                model="gpt-4o",
                messages=MESSAGES,
                stream=True,
                stream_options={"include_usage": True},
            )
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["stream_options"] == {"include_usage": True}
        assert chunks[-1].choices == []
        assert chunks[-1].usage.total_tokens == 3
        assert chunks[-1].usage.reasoning_tokens == 1

    def test_sync_stream_reasoning_content(self, client, httpx_mock: HTTPXMock):
        frame = chunk()
        frame["choices"][0]["delta"]["reasoning_content"] = "hmm"
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse(frame))
        chunks = list(
            client.chat.completions.create(model="gpt-4o", messages=MESSAGES, stream=True)
        )
        assert chunks[0].choices[0].delta.reasoning_content == "hmm"

    def test_sync_stream_context_manager_closes_response(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse(chunk("a"), chunk("b")))
        with client.chat.completions.create(model="gpt-4o", messages=MESSAGES, stream=True) as s:
            assert next(s).choices[0].delta.content == "a"
        assert s.response.is_closed

    @pytest.mark.parametrize(("status", "exc"), [(401, FerroAuthError), (429, FerroRateLimitError)])
    def test_sync_stream_http_errors_raise_before_iteration(
        self, client, httpx_mock: HTTPXMock, status, exc
    ):
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, status_code=status, json={"error": {"message": "denied"}}
        )
        with pytest.raises(exc, match="denied"):
            client.chat.completions.create(model="gpt-4o", messages=MESSAGES, stream=True)

    def test_sync_stream_malformed_chunk(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse("{not valid json}"))
        with pytest.raises(FerroStreamError, match="Malformed SSE chunk"):
            list(client.chat.completions.create(model="gpt-4o", messages=MESSAGES, stream=True))

    def test_sync_stream_error_frame(self, client, httpx_mock: HTTPXMock):
        error = {
            "error": {
                "message": "upstream hung up",
                "type": "stream_error",
                "code": "stream_timeout",
            }
        }
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse(chunk("a"), error))
        stream = client.chat.completions.create(model="gpt-4o", messages=MESSAGES, stream=True)
        assert next(stream).choices[0].delta.content == "a"
        with pytest.raises(FerroStreamError, match="upstream hung up") as exc_info:
            next(stream)
        assert exc_info.value.code == "stream_timeout"

    async def test_async_stream_happy_path(self, async_client, httpx_mock: HTTPXMock):
        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        terminal = chunk(usage=usage)
        terminal["choices"] = []
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            content=sse(chunk("Hel"), chunk("lo"), terminal),
            headers={"X-Request-ID": TRACE_ID},
        )
        stream = await async_client.chat.completions.create(
            model="gpt-4o", messages=MESSAGES, stream=True, stream_options={"include_usage": True}
        )
        assert isinstance(stream, AsyncStream)
        assert stream.trace_id == TRACE_ID
        chunks = [c async for c in stream]
        assert "".join(c.choices[0].delta.content for c in chunks[:2]) == "Hello"
        assert chunks[-1].usage.total_tokens == 2
        assert chunks[0].trace_id == TRACE_ID

    async def test_async_stream_http_error(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, status_code=401, json={"error": {"message": "Invalid"}}
        )
        with pytest.raises(FerroAuthError, match="Invalid"):
            await async_client.chat.completions.create(
                model="gpt-4o", messages=MESSAGES, stream=True
            )

    async def test_async_stream_malformed_chunk(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse("{not valid json}"))
        stream = await async_client.chat.completions.create(
            model="gpt-4o", messages=MESSAGES, stream=True
        )
        with pytest.raises(FerroStreamError, match="Malformed SSE chunk"):
            async for _ in stream:
                pass

    async def test_async_stream_error_frame(self, async_client, httpx_mock: HTTPXMock):
        error = {"error": {"message": "boom", "type": "stream_error", "code": "stream_error"}}
        httpx_mock.add_response(method="POST", url=CHAT_URL, content=sse(error))
        stream = await async_client.chat.completions.create(
            model="gpt-4o", messages=MESSAGES, stream=True
        )
        with pytest.raises(FerroStreamError) as exc_info:
            async with stream:
                async for _ in stream:
                    pass
        assert exc_info.value.code == "stream_error"
        assert stream.response.is_closed
