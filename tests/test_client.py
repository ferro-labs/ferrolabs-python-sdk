"""Client construction, retries, error mapping, and response-header metadata."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

import ferrolabsai
from ferrolabsai import AsyncFerroClient, FerroClient
from ferrolabsai.exceptions import (
    FerroAPIError,
    FerroAuthError,
    FerroBudgetExceededError,
    FerroConnectionError,
    FerroNotFoundError,
    FerroPermissionError,
    FerroRateLimitError,
    FerroServerError,
)

from .conftest import API_KEY, BASE_URL, COMPLETION_RESPONSE, TRACE_ID

CHAT_URL = f"{BASE_URL}/v1/chat/completions"
CAPABILITIES_URL = f"{BASE_URL}/v1/capabilities"


def _chat(client: FerroClient):
    return client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": "Hi"}]
    )


class TestClientInit:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("FERRO_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(FerroAuthError):
            FerroClient()

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("FERRO_API_KEY", "sk-ferro-envkey")
        assert FerroClient().api_key == "sk-ferro-envkey"

    def test_falls_back_to_openai_env(self, monkeypatch):
        monkeypatch.delenv("FERRO_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-compat")
        assert FerroClient().api_key == "sk-openai-compat"

    def test_strips_trailing_slash(self):
        c = FerroClient(api_key=API_KEY, base_url="https://localhost:8080/")
        assert c.base_url == "https://localhost:8080"

    @pytest.mark.parametrize("client_cls", [FerroClient, AsyncFerroClient])
    def test_rejects_negative_max_retries(self, client_cls):
        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            client_cls(api_key=API_KEY, max_retries=-1)

    @pytest.mark.parametrize("client_cls", [FerroClient, AsyncFerroClient])
    @pytest.mark.parametrize("invalid_value", [1.5, True])
    def test_rejects_non_integer_max_retries(self, client_cls, invalid_value):
        with pytest.raises(TypeError, match="max_retries must be an integer"):
            client_cls(api_key=API_KEY, max_retries=invalid_value)

    @pytest.mark.parametrize("client_cls", [FerroClient, AsyncFerroClient])
    def test_has_expected_namespaces(self, client_cls):
        c = client_cls(api_key=API_KEY)
        for name in ("chat", "embeddings", "images", "models", "admin", "responses", "moderations"):
            assert hasattr(c, name), name
        assert hasattr(c.chat, "completions")
        for name in ("keys", "config", "logs", "providers", "plugins", "audit"):
            assert hasattr(c.admin, name), name

    def test_sends_auth_and_user_agent(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        _chat(client)
        request = httpx_mock.get_requests()[0]
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["user-agent"] == f"ferrolabsai-python/{ferrolabsai.__version__}"

    def test_version_matches_pyproject(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        match = re.search(r'^version = "([^"]+)"', pyproject.read_text(), re.MULTILINE)
        assert match and match.group(1) == ferrolabsai.__version__

    def test_sync_byoc_merges_headers(self):
        custom = httpx.Client(base_url=BASE_URL)
        c = FerroClient(api_key=API_KEY, base_url=BASE_URL, http_client=custom)
        assert c._http is custom
        assert custom.headers["Authorization"] == f"Bearer {API_KEY}"
        custom.close()

    def test_async_byoc_merges_headers(self):
        custom = httpx.AsyncClient(base_url=BASE_URL)
        c = AsyncFerroClient(api_key=API_KEY, base_url=BASE_URL, http_client=custom)
        assert c._http is custom
        assert custom.headers["Authorization"] == f"Bearer {API_KEY}"

    def test_sync_context_manager(self):
        with FerroClient(api_key=API_KEY) as c:
            assert c.api_key == API_KEY

    async def test_async_context_manager(self):
        async with AsyncFerroClient(api_key=API_KEY) as c:
            assert c.api_key == API_KEY


class TestResponseMetadata:
    """Only the headers the gateway really sets are read (see docs/architecture.md)."""

    def test_headers_populate_inference_bodies(self, client, httpx_mock: HTTPXMock):
        body = {k: v for k, v in COMPLETION_RESPONSE.items() if k != "provider"}
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=body,
            headers={
                "X-Request-ID": TRACE_ID,
                "X-Gateway-Provider": "openai",
                "X-Gateway-Overhead-Ms": "1.250",
            },
        )
        response = _chat(client)
        assert response.trace_id == TRACE_ID
        assert response.provider == "openai"
        assert response.gateway_overhead_ms == 1.25
        assert not hasattr(response, "latency_ms")
        assert not hasattr(response.usage, "cost_usd")

    def test_body_provider_wins_over_header(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=COMPLETION_RESPONSE,
            headers={"X-Request-ID": TRACE_ID, "X-Gateway-Provider": "other"},
        )
        assert _chat(client).provider == "openai"

    def test_legacy_ferro_headers_are_ignored(self, client, httpx_mock: HTTPXMock):
        body = {k: v for k, v in COMPLETION_RESPONSE.items() if k != "provider"}
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=body,
            headers={"x-trace-id": "legacy", "x-request-id": TRACE_ID},
        )
        response = _chat(client)
        assert response.trace_id == TRACE_ID
        assert response.provider is None

    async def test_async_headers_populate_inference_bodies(
        self, async_client, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            json=COMPLETION_RESPONSE,
            headers={"X-Request-ID": TRACE_ID, "X-Gateway-Overhead-Ms": "3"},
        )
        response = await async_client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "Hi"}]
        )
        assert response.trace_id == TRACE_ID
        assert response.gateway_overhead_ms == 3.0

    def test_non_inference_bodies_are_not_touched(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/admin/dashboard",
            json={"providers": {"enabled": 1}},
            headers={"X-Request-ID": TRACE_ID, "X-Gateway-Provider": "openai"},
        )
        assert client.admin.dashboard() == {"providers": {"enabled": 1}}


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("status", "code", "exc"),
        [
            (401, "invalid_api_key", FerroAuthError),
            (402, "insufficient_quota", FerroBudgetExceededError),
            (403, "insufficient_scope", FerroPermissionError),
            (404, "model_not_found", FerroNotFoundError),
            (429, "rate_limit_exceeded", FerroRateLimitError),
            (502, "upstream_error", FerroServerError),
            (400, "invalid_request", FerroAPIError),
        ],
    )
    def test_status_maps_to_exception(self, client, httpx_mock: HTTPXMock, status, code, exc):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=status,
            json={"error": {"message": "nope", "type": "x", "code": code}},
            headers={"X-Request-ID": TRACE_ID},
        )
        with pytest.raises(exc) as exc_info:
            _chat(client)
        assert exc_info.value.status_code == status
        assert exc_info.value.code == code
        assert exc_info.value.request_id == TRACE_ID
        assert "nope" in str(exc_info.value)

    def test_rate_limit_carries_retry_after(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=429,
            json={"error": {"message": "slow down"}},
            headers={"Retry-After": "7"},
        )
        with pytest.raises(FerroRateLimitError) as exc_info:
            _chat(client)
        assert exc_info.value.retry_after == 7.0

    def test_request_id_from_body_trace_id(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=400,
            json={"error": {"message": "Bad request"}, "trace_id": "trace-xyz"},
        )
        with pytest.raises(FerroAPIError) as exc_info:
            _chat(client)
        assert exc_info.value.request_id == "trace-xyz"


class TestRetries:
    @pytest.fixture(autouse=True)
    def _no_jitter(self, monkeypatch):
        # Full jitter picks uniformly from [0, delay]; pin it to the upper bound.
        monkeypatch.setattr("ferrolabsai.client.random.uniform", lambda _lo, hi: hi)

    def test_sync_retries_connect_errors_with_backoff(
        self, monkeypatch, client, httpx_mock: HTTPXMock
    ):
        sleeps: list[float] = []
        monkeypatch.setattr("ferrolabsai.client.time.sleep", sleeps.append)
        client.max_retries = 2
        httpx_mock.add_exception(httpx.ConnectError("refused"), method="POST", url=CHAT_URL)
        httpx_mock.add_exception(httpx.ConnectTimeout("slow"), method="POST", url=CHAT_URL)
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        assert _chat(client).id == "chatcmpl-abc123"
        assert sleeps == [0.5, 1.0]

    def test_sync_retry_exhaustion_raises_connection_error(
        self, monkeypatch, client, httpx_mock: HTTPXMock
    ):
        monkeypatch.setattr("ferrolabsai.client.time.sleep", lambda _s: None)
        client.max_retries = 1
        httpx_mock.add_exception(httpx.ConnectError("refused"), method="POST", url=CHAT_URL)
        httpx_mock.add_exception(httpx.ConnectError("refused"), method="POST", url=CHAT_URL)
        with pytest.raises(FerroConnectionError, match="Cannot reach"):
            _chat(client)
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.parametrize("status", [408, 429, 500, 503])
    def test_sync_retries_retryable_statuses(
        self, monkeypatch, client, httpx_mock: HTTPXMock, status
    ):
        sleeps: list[float] = []
        monkeypatch.setattr("ferrolabsai.client.time.sleep", sleeps.append)
        client.max_retries = 1
        httpx_mock.add_response(
            method="GET", url=CAPABILITIES_URL, status_code=status, json={"error": {"message": "x"}}
        )
        httpx_mock.add_response(method="GET", url=CAPABILITIES_URL, json={"providers": {}})
        assert client.capabilities() == {"providers": {}}
        assert sleeps == [0.5]

    def test_sync_honours_retry_after_capped(self, monkeypatch, client, httpx_mock: HTTPXMock):
        sleeps: list[float] = []
        monkeypatch.setattr("ferrolabsai.client.time.sleep", sleeps.append)
        client.max_retries = 2
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=429,
            json={"error": {"message": "x"}},
            headers={"Retry-After": "2"},
        )
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=429,
            json={"error": {"message": "x"}},
            headers={"Retry-After": "600"},
        )
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        _chat(client)
        assert sleeps == [2.0, 30.0]

    def test_sync_does_not_retry_client_errors(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 2
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, status_code=400, json={"error": {"message": "bad"}}
        )
        with pytest.raises(FerroAPIError):
            _chat(client)
        assert len(httpx_mock.get_requests()) == 1

    def test_sync_raises_after_last_retryable_status(
        self, monkeypatch, client, httpx_mock: HTTPXMock
    ):
        monkeypatch.setattr("ferrolabsai.client.time.sleep", lambda _s: None)
        client.max_retries = 1
        for _ in range(2):
            httpx_mock.add_response(
                method="GET",
                url=CAPABILITIES_URL,
                status_code=503,
                json={"error": {"message": "x"}},
            )
        with pytest.raises(FerroServerError):
            client.capabilities()

    def test_streaming_is_never_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 2
        httpx_mock.add_response(
            method="POST", url=CHAT_URL, status_code=429, json={"error": {"message": "x"}}
        )
        with pytest.raises(FerroRateLimitError):
            client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": "Hi"}], stream=True
            )
        assert len(httpx_mock.get_requests()) == 1

    async def test_async_retries_with_backoff(
        self, monkeypatch, async_client, httpx_mock: HTTPXMock
    ):
        sleeps: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        monkeypatch.setattr("ferrolabsai.client.asyncio.sleep", fake_sleep)
        async_client.max_retries = 2
        httpx_mock.add_exception(httpx.ConnectError("refused"), method="POST", url=CHAT_URL)
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=429,
            json={"error": {"message": "x"}},
            headers={"Retry-After": "3"},
        )
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        response = await async_client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "Hi"}]
        )
        assert response.id == "chatcmpl-abc123"
        assert sleeps == [0.5, 3.0]

    async def test_async_retry_exhaustion_raises_connection_error(
        self, monkeypatch, async_client, httpx_mock: HTTPXMock
    ):
        async def fake_sleep(_delay: float) -> None:
            pass

        monkeypatch.setattr("ferrolabsai.client.asyncio.sleep", fake_sleep)
        async_client.max_retries = 1
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="GET", url=CAPABILITIES_URL)
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="GET", url=CAPABILITIES_URL)
        with pytest.raises(FerroConnectionError, match="timed out"):
            await async_client.capabilities()
        assert len(httpx_mock.get_requests()) == 2


class TestGatewayEndpoints:
    @pytest.mark.parametrize(
        ("method", "path", "status", "body"),
        [
            ("health", "/health", 200, {"status": "ok", "version": "1.4.5"}),
            ("health", "/health", 503, {"status": "no_providers"}),
            ("ready", "/readyz", 200, {"status": "ready", "targets": []}),
            ("ready", "/readyz", 503, {"status": "not_ready", "reason": "x"}),
            ("live", "/livez", 200, {"status": "ok"}),
        ],
    )
    def test_probes_return_json_on_200_and_503(
        self, client, httpx_mock: HTTPXMock, method, path, status, body
    ):
        httpx_mock.add_response(
            method="GET", url=f"{BASE_URL}{path}", status_code=status, json=body
        )
        assert getattr(client, method)() == body

    async def test_async_probes(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{BASE_URL}/health", status_code=503, json={"status": "degraded"}
        )
        assert await async_client.health() == {"status": "degraded"}

    def test_capabilities(self, client, httpx_mock: HTTPXMock):
        caps = {"providers": {"openai": {"tools": "forward"}}, "image_response_formats": {}}
        httpx_mock.add_response(method="GET", url=f"{BASE_URL}/v1/capabilities", json=caps)
        assert client.capabilities() == caps

    def test_rerank(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/v1/rerank", json={"results": [{"index": 1}]}
        )
        result = client.rerank(model="rerank-v3", query="q", documents=["a", "b"], top_n=1)
        assert result["results"][0]["index"] == 1
        import json

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body == {"model": "rerank-v3", "query": "q", "documents": ["a", "b"], "top_n": 1}

    async def test_async_rerank_and_capabilities(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=f"{BASE_URL}/v1/rerank", json={"results": []})
        httpx_mock.add_response(method="GET", url=f"{BASE_URL}/v1/capabilities", json={})
        assert await async_client.rerank(model="m", query="q", documents=[]) == {"results": []}
        assert await async_client.capabilities() == {}

    def test_moderations(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/v1/moderations", json={"results": [{"flagged": False}]}
        )
        result = client.moderations.create(input="hello", model="omni-moderation-latest")
        assert result["results"][0]["flagged"] is False
        import json

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body == {"input": "hello", "model": "omni-moderation-latest"}

    async def test_async_moderations(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{BASE_URL}/v1/moderations", json={"results": []}
        )
        assert await async_client.moderations.create(input=["a"]) == {"results": []}
