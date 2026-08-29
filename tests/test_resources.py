"""Embeddings, images, model catalog, and the Responses API."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ferrolabsai.exceptions import FerroNotFoundError
from ferrolabsai.types import ModelInfo, Response

from .conftest import BASE_URL, EMBEDDING_RESPONSE, IMAGE_RESPONSE, MODELS_RESPONSE, TRACE_ID

MODELS_URL = f"{BASE_URL}/v1/models"


class TestEmbeddings:
    def test_create(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=EMBEDDING_RESPONSE,
            headers={"X-Request-ID": TRACE_ID},
        )
        response = client.embeddings.create(
            model="text-embedding-3-small", input=["Hello", "world"], dimensions=3
        )
        assert len(response.data) == 2
        assert response.data[0].embedding == [0.1, 0.2, 0.3]
        assert response.model == "text-embedding-3-small"
        assert response.trace_id == TRACE_ID
        assert json.loads(httpx_mock.get_requests()[0].content)["dimensions"] == 3

    async def test_async_create(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/v1/embeddings", json=EMBEDDING_RESPONSE
        )
        response = await async_client.embeddings.create(model="text-embedding-3-small", input="Hi")
        assert response.data[1].embedding == [0.4, 0.5, 0.6]
        assert json.loads(httpx_mock.get_requests()[0].content)["input"] == "Hi"


class TestImages:
    def test_generate(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/v1/images/generations", json=IMAGE_RESPONSE
        )
        image = client.images.generate(model="dall-e-3", prompt="A gateway", size="1024x1024")
        assert image.data[0].url == "https://example.com/image.png"
        assert image.data[0].revised_prompt == "A polished prompt"
        assert json.loads(httpx_mock.get_requests()[0].content)["size"] == "1024x1024"

    async def test_async_generate(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/v1/images/generations", json=IMAGE_RESPONSE
        )
        image = await async_client.images.generate(model="dall-e-3", prompt="A gateway")
        assert image.created == 1700000000


class TestModels:
    """The gateway serves only GET /v1/models and ignores its query string;
    every lookup and filter is client-side over that one catalog fetch."""

    def test_list_returns_enriched_model_info(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        models = client.models.list()
        assert len(models) == 3
        gpt = models[0]
        assert isinstance(gpt, ModelInfo)
        assert gpt.id == "gpt-4o"
        assert gpt.owned_by == "openai"
        assert gpt.provider == "openai"
        assert gpt.mode == "chat"
        assert gpt.context_window == 128000
        assert gpt.max_output_tokens == 16384
        assert gpt.capabilities == ["vision", "function_calling", "streaming"]
        assert gpt.status == "active"
        assert gpt.deprecated is False
        assert models[1].deprecated is True
        assert models[2].capabilities == []
        assert not hasattr(gpt, "input_cost_per_token")

    def test_list_filters_client_side(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        assert [m.id for m in client.models.list(provider="anthropic")] == [
            "claude-3-5-sonnet-20241022"
        ]
        assert [m.id for m in client.models.list(capability="vision")] == ["gpt-4o"]
        assert all(str(r.url) == MODELS_URL for r in httpx_mock.get_requests())

    def test_retrieve_is_a_client_side_lookup(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        assert client.models.retrieve("gpt-4o").context_window == 128000
        assert [str(r.url) for r in httpx_mock.get_requests()] == [MODELS_URL]

    def test_retrieve_unknown_raises_locally(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        with pytest.raises(FerroNotFoundError) as exc_info:
            client.models.retrieve("nonexistent-model")
        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "model_not_found"
        assert [str(r.url) for r in httpx_mock.get_requests()] == [MODELS_URL]

    def test_search_is_case_insensitive_substring(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        assert [m.id for m in client.models.search("CLAUDE")] == ["claude-3-5-sonnet-20241022"]

    async def test_async_models(self, async_client, httpx_mock: HTTPXMock):
        for _ in range(3):
            httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
        assert len(await async_client.models.list()) == 3
        assert (await async_client.models.retrieve("gpt-4o")).owned_by == "openai"
        assert [m.id for m in await async_client.models.search("embedding")] == [
            "text-embedding-3-small"
        ]
        with pytest.raises(FerroNotFoundError):
            httpx_mock.add_response(method="GET", url=MODELS_URL, json=MODELS_RESPONSE)
            await async_client.models.retrieve("nope")


RESPONSE_BODY = {
    "id": "resp_1",
    "object": "response",
    "created_at": 1700000000,
    "status": "completed",
    "model": "gpt-4o",
    "output": [{"type": "message", "content": [{"type": "output_text", "text": "hi"}]}],
    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
}


class TestResponses:
    def test_create(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/responses",
            json=RESPONSE_BODY,
            headers={"X-Request-ID": TRACE_ID, "X-Gateway-Provider": "openai"},
        )
        response = client.responses.create(model="gpt-4o", input="hi")
        assert isinstance(response, Response)
        assert response.id == "resp_1"
        assert response.status == "completed"
        assert response.output[0]["type"] == "message"
        assert response.usage == {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        assert response.trace_id == TRACE_ID
        assert response.provider == "openai"
        assert response.raw["model"] == "gpt-4o"
        assert json.loads(httpx_mock.get_requests()[0].content) == {
            "model": "gpt-4o",
            "input": "hi",
        }

    def test_retrieve_and_delete(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{BASE_URL}/v1/responses/resp_1", json=RESPONSE_BODY
        )
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/v1/responses/resp_1",
            json={"id": "resp_1", "object": "response", "deleted": True},
        )
        assert client.responses.retrieve("resp_1").id == "resp_1"
        assert client.responses.delete("resp_1")["deleted"] is True

    async def test_async_create_retrieve_delete(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=f"{BASE_URL}/v1/responses", json=RESPONSE_BODY)
        httpx_mock.add_response(
            method="GET", url=f"{BASE_URL}/v1/responses/resp_1", json=RESPONSE_BODY
        )
        httpx_mock.add_response(
            method="DELETE", url=f"{BASE_URL}/v1/responses/resp_1", json={"deleted": True}
        )
        assert (await async_client.responses.create(model="gpt-4o", input="hi")).id == "resp_1"
        assert (await async_client.responses.retrieve("resp_1")).model == "gpt-4o"
        assert await async_client.responses.delete("resp_1") == {"deleted": True}
