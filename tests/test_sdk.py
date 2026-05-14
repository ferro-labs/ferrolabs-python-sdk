"""
ferrolabsai SDK test suite.

Tests use pytest-httpx to mock the HTTP layer — no real gateway needed.
Run: pytest tests/ -v
"""

from __future__ import annotations

import json

import httpx
import pytest
from pytest_httpx import HTTPXMock

from ferrolabsai import AsyncFerroClient, FerroClient
from ferrolabsai.exceptions import (
    FerroAPIError,
    FerroAuthError,
    FerroNotFoundError,
    FerroRateLimitError,
    FerroServerError,
)

BASE_URL = "http://localhost:8080"
API_KEY = "sk-ferro-testkey123"


@pytest.fixture
def client():
    return FerroClient(api_key=API_KEY, base_url=BASE_URL)


@pytest.fixture
def async_client():
    return AsyncFerroClient(api_key=API_KEY, base_url=BASE_URL)


# ------------------------------------------------------------------
# Client instantiation
# ------------------------------------------------------------------


class TestClientInit:
    def test_requires_api_key(self):
        import os

        os.environ.pop("FERRO_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        with pytest.raises(FerroAuthError):
            FerroClient()

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("FERRO_API_KEY", "sk-ferro-envkey")
        c = FerroClient()
        assert c.api_key == "sk-ferro-envkey"

    def test_falls_back_to_openai_env(self, monkeypatch):
        monkeypatch.delenv("FERRO_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-compat")
        c = FerroClient()
        assert c.api_key == "sk-openai-compat"

    def test_strips_trailing_slash(self):
        c = FerroClient(api_key=API_KEY, base_url="https://localhost:8080/")
        assert c.base_url == "https://localhost:8080"

    def test_rejects_negative_max_retries(self):
        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            FerroClient(api_key=API_KEY, max_retries=-1)

    def test_async_rejects_negative_max_retries(self):
        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            AsyncFerroClient(api_key=API_KEY, max_retries=-1)

    @pytest.mark.parametrize("client_cls", [FerroClient, AsyncFerroClient])
    def test_accepts_zero_max_retries(self, client_cls):
        client = client_cls(api_key=API_KEY, max_retries=0)
        assert client.max_retries == 0

    @pytest.mark.parametrize("client_cls", [FerroClient, AsyncFerroClient])
    @pytest.mark.parametrize("invalid_value", [1.5, True])
    def test_rejects_non_integer_max_retries(self, client_cls, invalid_value):
        with pytest.raises(TypeError, match="max_retries must be an integer"):
            client_cls(api_key=API_KEY, max_retries=invalid_value)

    def test_has_expected_namespaces(self, client):
        assert hasattr(client, "chat")
        assert hasattr(client.chat, "completions")
        assert hasattr(client, "embeddings")
        assert hasattr(client, "images")
        assert hasattr(client, "models")
        assert hasattr(client, "admin")
        # Admin sub-resources mirror the OSS gateway /admin/* surface.
        assert hasattr(client.admin, "keys")
        assert hasattr(client.admin, "config")
        assert hasattr(client.admin, "logs")
        assert hasattr(client.admin, "providers")
        assert hasattr(client.admin, "plugins")


# ------------------------------------------------------------------
# Chat completions
# ------------------------------------------------------------------

COMPLETION_RESPONSE = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello from Ferro!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "cost_usd": 0.000075,
    },
}


class TestChatCompletions:
    def test_basic_create(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert response.id == "chatcmpl-abc123"
        assert response.model == "gpt-4o"
        assert response.content == "Hello from Ferro!"
        assert response.usage.cost_usd == 0.000075

    def test_sends_correct_headers(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )
        client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
        )
        request = httpx_mock.get_requests()[0]
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        assert request.headers["content-type"] == "application/json"

    def test_passes_optional_params(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )
        client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
            max_tokens=100,
            user="user_123",
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 100
        assert body["user"] == "user_123"

    def test_ferro_template_id_forwarded(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )
        client.chat.completions.create(
            model="gpt-4o",
            messages=[],
            template_id="tmpl_support",
            template_variables={"plan": "pro"},
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["template_id"] == "tmpl_support"
        assert body["template_variables"] == {"plan": "pro"}

    def test_streaming_returns_iterator(self, client, httpx_mock: HTTPXMock):
        sse_data = (
            'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"gpt-4o",'
            '"choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
            'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"gpt-4o",'
            '"choices":[{"index":0,"delta":{"content":" world"},"finish_reason":"stop"}]}\n\n'
            "data: [DONE]\n\n"
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            content=sse_data.encode(),
        )
        chunks = list(
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
                stream=True,
            )
        )
        assert len(chunks) == 2
        assert chunks[0].choices[0].delta.content == "Hello"
        assert chunks[1].choices[0].delta.content == " world"
        assert chunks[1].choices[0].finish_reason == "stop"


# ------------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------------

EMBEDDING_RESPONSE = {
    "object": "list",
    "data": [
        {"index": 0, "object": "embedding", "embedding": [0.1, 0.2, 0.3]},
        {"index": 1, "object": "embedding", "embedding": [0.4, 0.5, 0.6]},
    ],
    "model": "text-embedding-3-small",
    "usage": {"prompt_tokens": 8, "total_tokens": 8},
}

IMAGE_RESPONSE = {
    "created": 1700000000,
    "data": [
        {
            "url": "https://example.com/image.png",
            "revised_prompt": "A polished image prompt",
        }
    ],
}


class TestEmbeddings:
    def test_create(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/embeddings",
            json=EMBEDDING_RESPONSE,
        )
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=["Hello", "world"],
        )
        assert len(response.data) == 2
        assert response.data[0].embedding == [0.1, 0.2, 0.3]
        assert response.model == "text-embedding-3-small"


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------

MODELS_RESPONSE = {
    "data": [
        {
            "id": "gpt-4o",
            "object": "model",
            "owned_by": "openai",
            "context_window": 128000,
            "input_cost_per_token": 0.0000025,
            "output_cost_per_token": 0.00001,
        },
        {
            "id": "claude-3-5-sonnet-20241022",
            "object": "model",
            "owned_by": "anthropic",
            "context_window": 200000,
        },
    ]
}


class TestModels:
    def test_list(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/v1/models",
            json=MODELS_RESPONSE,
        )
        models = client.models.list()
        assert len(models) == 2
        assert models[0].id == "gpt-4o"
        assert models[0].provider == "openai"
        assert models[0].context_window == 128000

    def test_retrieve(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/v1/models/gpt-4o",
            json=MODELS_RESPONSE["data"][0],
        )
        model = client.models.retrieve("gpt-4o")
        assert model.id == "gpt-4o"
        assert model.input_cost_per_token == 0.0000025


# ------------------------------------------------------------------
# Admin — Keys
# ------------------------------------------------------------------


class TestAdminKeys:
    def test_create_key(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/admin/keys",
            json={
                "id": "key_abc",
                "name": "test-key",
                "key": "fgw_fullkeyvalue",
                "scopes": ["admin"],
                "active": True,
                "created_at": "2026-04-01T00:00:00Z",
            },
        )
        key = client.admin.keys.create(name="test-key", scopes=["admin"])
        assert key.key == "fgw_fullkeyvalue"
        assert key.name == "test-key"
        assert key.scopes == ["admin"]

    def test_revoke_key(self, client, httpx_mock: HTTPXMock):
        # OSS revoke is POST /admin/keys/{id}/revoke (record kept for audit)
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/admin/keys/key_abc/revoke",
            status_code=204,
            content=b"",
        )
        client.admin.keys.revoke("key_abc")  # should not raise

    def test_delete_key(self, client, httpx_mock: HTTPXMock):
        # delete() permanently removes the key record
        httpx_mock.add_response(
            method="DELETE",
            url=f"{BASE_URL}/admin/keys/key_abc",
            status_code=204,
            content=b"",
        )
        client.admin.keys.delete("key_abc")  # should not raise

    def test_rotate_key(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/admin/keys/key_abc/rotate",
            json={
                "id": "key_abc",
                "name": "prod",
                "key": "fgw_newkeyvalue",
                "scopes": ["admin"],
                "active": True,
                "created_at": "2026-04-01T00:00:00Z",
            },
        )
        rotated = client.admin.keys.rotate("key_abc")
        assert rotated.key == "fgw_newkeyvalue"
        assert rotated.id == "key_abc"

    def test_list_keys(self, client, httpx_mock: HTTPXMock):
        # OSS returns a bare JSON array from GET /admin/keys
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/keys",
            json=[
                {
                    "id": "key_1",
                    "name": "prod",
                    "scopes": ["admin"],
                    "active": True,
                    "usage_count": 12,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ],
        )
        keys = client.admin.keys.list()
        assert len(keys) == 1
        assert keys[0].id == "key_1"
        assert keys[0].usage_count == 12

    def test_keys_usage(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/keys/usage?limit=10&offset=0&sort=usage",
            json={
                "data": [{"id": "key_1", "name": "prod", "usage_count": 100, "active": True}],
                "summary": {
                    "total_keys": 1,
                    "active_keys": 1,
                    "total_usage": 100,
                    "returned_keys": 1,
                },
                "filters": {"limit": 10, "offset": 0, "sort": "usage", "active": "", "since": ""},
            },
        )
        result = client.admin.keys.usage(limit=10)
        assert result["summary"]["total_usage"] == 100


class TestAdminConfig:
    def test_get_config(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/config",
            json={
                "strategy": {"mode": "fallback"},
                "targets": [
                    {"virtual_key": "openai", "weight": 1},
                    {"virtual_key": "anthropic", "weight": 1},
                ],
                "plugins": [],
            },
        )
        cfg = client.admin.config.get()
        assert cfg.strategy == {"mode": "fallback"}
        assert len(cfg.targets) == 2

    def test_update_config(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="PUT",
            url=f"{BASE_URL}/admin/config",
            json={"status": "updated"},
        )
        result = client.admin.config.update(
            {
                "strategy": {"mode": "single"},
                "targets": [{"virtual_key": "openai"}],
            }
        )
        assert result["status"] == "updated"

    def test_history(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/config/history",
            json={
                "data": [
                    {
                        "version": 1,
                        "updated_at": "2026-04-01T00:00:00Z",
                        "config": {"strategy": {"mode": "single"}, "targets": []},
                    },
                    {
                        "version": 2,
                        "updated_at": "2026-04-02T00:00:00Z",
                        "config": {"strategy": {"mode": "fallback"}, "targets": []},
                    },
                ],
                "summary": {"total_versions": 2},
            },
        )
        history = client.admin.config.history()
        assert len(history) == 2
        assert history[0].version == 1
        assert history[1].config.strategy == {"mode": "fallback"}

    def test_rollback(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/admin/config/rollback/1",
            json={"status": "rolled_back", "rolled_back_to": 1, "current_history_size": 3},
        )
        result = client.admin.config.rollback(1)
        assert result["status"] == "rolled_back"
        assert result["rolled_back_to"] == 1


class TestAdminLogs:
    def test_list_logs(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/logs?limit=10&offset=0",
            json={
                "data": [{"trace_id": "t1", "model": "gpt-4o", "provider": "openai"}],
                "summary": {"total_entries": 1, "returned_entries": 1},
                "filters": {"limit": 10, "offset": 0, "stage": "", "model": "", "provider": ""},
            },
        )
        result = client.admin.logs.list(limit=10)
        assert result["summary"]["total_entries"] == 1
        assert result["data"][0]["trace_id"] == "t1"

    def test_logs_stats(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/logs/stats",
            json={"total": 42, "errors": 1},
        )
        stats = client.admin.logs.stats()
        assert stats["total"] == 42


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


class TestErrorHandling:
    def test_401_raises_auth_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=401,
            json={"error": {"message": "Invalid API key", "code": "invalid_api_key"}},
        )
        with pytest.raises(FerroAuthError) as exc_info:
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert "Invalid API key" in str(exc_info.value)

    def test_429_raises_rate_limit_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=429,
            json={"error": {"message": "Rate limit exceeded"}},
        )
        with pytest.raises(FerroRateLimitError):
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )

    def test_404_raises_not_found(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/v1/models/nonexistent-model",
            status_code=404,
            json={"error": {"message": "Model not found"}},
        )
        with pytest.raises(FerroNotFoundError):
            client.models.retrieve("nonexistent-model")


# ------------------------------------------------------------------
# Context manager
# ------------------------------------------------------------------


class TestContextManager:
    def test_sync_context_manager(self):
        with FerroClient(api_key=API_KEY) as c:
            assert c.api_key == API_KEY

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncFerroClient(api_key=API_KEY) as c:
            assert c.api_key == API_KEY


# ------------------------------------------------------------------
# P0-1: Streaming error handling routes through _raise_api_error
# ------------------------------------------------------------------


class TestStreamingErrorHandling:
    def test_sync_stream_raises_ferro_error_not_httpx(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=401,
            json={"error": {"message": "Invalid API key"}},
        )
        with pytest.raises(FerroAuthError, match="Invalid API key"):
            list(
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Hi"}],
                    stream=True,
                )
            )

    def test_sync_stream_429_raises_rate_limit(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=429,
            json={"error": {"message": "Rate limit exceeded"}},
        )
        with pytest.raises(FerroRateLimitError):
            list(
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Hi"}],
                    stream=True,
                )
            )

    def test_sync_stream_500_raises_server_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=500,
            json={"error": {"message": "Internal error"}},
        )
        with pytest.raises(FerroServerError):
            list(
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Hi"}],
                    stream=True,
                )
            )


# ------------------------------------------------------------------
# P0-2: Async completions has parity params
# ------------------------------------------------------------------


class TestAsyncCompletionsParams:
    @pytest.mark.asyncio
    async def test_forwards_frequency_presence_penalty(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )
        await async_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            frequency_penalty=0.5,
            presence_penalty=0.3,
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["frequency_penalty"] == 0.5
        assert body["presence_penalty"] == 0.3

    @pytest.mark.asyncio
    async def test_forwards_route_tag(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )
        await async_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
            route_tag="fast",
        )
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["x_route_tag"] == "fast"


# ------------------------------------------------------------------
# P0-3: BYOC http_client merges auth headers
# ------------------------------------------------------------------


class TestBYOCHttpClient:
    def test_sync_byoc_merges_headers(self):
        custom = httpx.Client(base_url=BASE_URL)
        client = FerroClient(api_key=API_KEY, base_url=BASE_URL, http_client=custom)
        assert client._http is custom
        assert "Authorization" in custom.headers
        assert custom.headers["Authorization"] == f"Bearer {API_KEY}"
        custom.close()

    def test_async_byoc_merges_headers(self):
        custom = httpx.AsyncClient(base_url=BASE_URL)
        client = AsyncFerroClient(api_key=API_KEY, base_url=BASE_URL, http_client=custom)
        assert client._http is custom
        assert "Authorization" in custom.headers
        assert custom.headers["Authorization"] == f"Bearer {API_KEY}"


# ------------------------------------------------------------------
# P1-4: AsyncFerroClient has all namespaces
# ------------------------------------------------------------------


class TestAsyncClientNamespaces:
    def test_has_all_namespaces(self):
        client = AsyncFerroClient(api_key=API_KEY)
        assert hasattr(client, "chat")
        assert hasattr(client.chat, "completions")
        assert hasattr(client, "embeddings")
        assert hasattr(client, "images")
        assert hasattr(client, "models")
        assert hasattr(client, "admin")


class TestAsyncResources:
    @pytest.mark.asyncio
    async def test_models_list_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/v1/models",
            json=MODELS_RESPONSE,
        )
        models = await async_client.models.list()
        assert len(models) == 2
        assert models[0].id == "gpt-4o"

    @pytest.mark.asyncio
    async def test_models_search_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/v1/models?search=claude",
            json={"data": [MODELS_RESPONSE["data"][1]]},
        )
        models = await async_client.models.search("claude")
        assert len(models) == 1
        assert models[0].provider == "anthropic"

    @pytest.mark.asyncio
    async def test_images_generate_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/images/generations",
            json=IMAGE_RESPONSE,
        )
        image = await async_client.images.generate(
            model="dall-e-3",
            prompt="A gateway",
            size="1024x1024",
        )
        assert image.data[0].url == "https://example.com/image.png"
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["size"] == "1024x1024"

    @pytest.mark.asyncio
    async def test_admin_health_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/health",
            json={"status": "ok"},
        )
        health = await async_client.admin.health()
        assert health["status"] == "ok"

    @pytest.mark.asyncio
    async def test_admin_keys_list_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/keys",
            json=[
                {
                    "id": "key_1",
                    "name": "prod",
                    "scopes": ["admin"],
                    "active": True,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ],
        )
        keys = await async_client.admin.keys.list()
        assert keys[0].id == "key_1"

    @pytest.mark.asyncio
    async def test_admin_config_history_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/config/history",
            json={
                "data": [
                    {
                        "version": 1,
                        "updated_at": "2026-04-01T00:00:00Z",
                        "config": {"strategy": {"mode": "single"}, "targets": []},
                    }
                ]
            },
        )
        history = await async_client.admin.config.history()
        assert history[0].version == 1

    @pytest.mark.asyncio
    async def test_admin_providers_list_is_awaitable(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/providers",
            json={"data": [{"name": "openai"}]},
        )
        providers = await async_client.admin.providers.list()
        assert providers == [{"name": "openai"}]


class TestRetryBackoff:
    def test_sync_retries_use_backoff(self, monkeypatch, client, httpx_mock: HTTPXMock):
        sleeps: list[float] = []
        monkeypatch.setattr("ferrolabsai.client.time.sleep", sleeps.append)
        client.max_retries = 1
        httpx_mock.add_exception(
            httpx.ConnectError("connection refused"),
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert response.id == "chatcmpl-abc123"
        assert sleeps == [0.5]

    @pytest.mark.asyncio
    async def test_async_retries_use_backoff(
        self,
        monkeypatch,
        async_client,
        httpx_mock: HTTPXMock,
    ):
        sleeps: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        monkeypatch.setattr("ferrolabsai.client.asyncio.sleep", fake_sleep)
        async_client.max_retries = 1
        httpx_mock.add_exception(
            httpx.ConnectError("connection refused"),
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            json=COMPLETION_RESPONSE,
        )

        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert response.id == "chatcmpl-abc123"
        assert sleeps == [0.5]


# ------------------------------------------------------------------
# P1-7: request_id populated from response headers
# ------------------------------------------------------------------


class TestRequestIdPropagation:
    def test_request_id_from_header(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=500,
            json={"error": {"message": "Server error"}},
            headers={"x-request-id": "req-abc-123"},
        )
        with pytest.raises(FerroServerError) as exc_info:
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert exc_info.value.request_id == "req-abc-123"

    def test_request_id_from_body_trace_id(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/v1/chat/completions",
            status_code=400,
            json={"error": {"message": "Bad request"}, "trace_id": "trace-xyz"},
        )
        with pytest.raises(FerroAPIError) as exc_info:
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )
        assert exc_info.value.request_id == "trace-xyz"
