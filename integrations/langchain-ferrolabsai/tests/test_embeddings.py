"""Tests for FerroEmbeddings."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock

from langchain_ferrolabsai import FerroEmbeddings

from .conftest import BASE_URL, make_embedding_response


def _build(**overrides) -> FerroEmbeddings:
    kwargs = {
        "model": "text-embedding-3-small",
        "base_url": BASE_URL,
        "api_key": "sk-ferro-test",
    }
    kwargs.update(overrides)
    return FerroEmbeddings(**kwargs)  # type: ignore[arg-type]


class TestEmbedDocuments:
    def test_returns_vector_per_input(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=make_embedding_response(vectors=[[0.1, 0.2], [0.3, 0.4]]),
        )
        embed = _build()
        result = embed.embed_documents(["hello", "world"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_preserves_input_order_when_gateway_returns_out_of_order(self, httpx_mock: HTTPXMock):
        # Simulate the gateway returning data with index 1 before index 0.
        out_of_order = {
            "object": "list",
            "model": "text-embedding-3-small",
            "data": [
                {"index": 1, "embedding": [0.3, 0.4], "object": "embedding"},
                {"index": 0, "embedding": [0.1, 0.2], "object": "embedding"},
            ],
        }
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=out_of_order,
        )
        embed = _build()
        result = embed.embed_documents(["a", "b"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_empty_input_returns_empty_list_without_request(self, httpx_mock: HTTPXMock):
        # No httpx_mock response registered — would error if a request was made.
        embed = _build()
        assert embed.embed_documents([]) == []
        assert httpx_mock.get_requests() == []

    def test_forwards_optional_params(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=make_embedding_response(vectors=[[0.0]]),
        )
        embed = _build(dimensions=512, encoding_format="float", user="u1")
        embed.embed_documents(["x"])
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["dimensions"] == 512
        assert body["encoding_format"] == "float"
        assert body["user"] == "u1"


class TestEmbedQuery:
    def test_returns_single_vector(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=make_embedding_response(vectors=[[0.9, 0.8, 0.7]]),
        )
        embed = _build()
        assert embed.embed_query("hello") == [0.9, 0.8, 0.7]

    def test_sends_single_string_input(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=make_embedding_response(vectors=[[0.0]]),
        )
        embed = _build()
        embed.embed_query("hello")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["input"] == "hello"
