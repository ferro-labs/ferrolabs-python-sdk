"""Retry policy: status/exception retries are idempotent-only except 429 and connect
failures."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from ferrolabsai.client import _should_retry
from ferrolabsai.exceptions import FerroConnectionError, FerroServerError

from .conftest import BASE_URL, COMPLETION_RESPONSE

CHAT_URL = f"{BASE_URL}/v1/chat/completions"
CAPABILITIES_URL = f"{BASE_URL}/v1/capabilities"
KEY_URL = f"{BASE_URL}/admin/keys/k1"
ERROR_BODY = {"error": {"message": "x"}}
MESSAGES = [{"role": "user", "content": "Hi"}]


class TestShouldRetry:
    @pytest.mark.parametrize(
        ("method", "status", "expected"),
        [
            ("POST", 500, False),
            ("POST", 408, False),
            ("POST", 429, True),
            ("GET", 500, True),
            ("PUT", 503, True),
            ("DELETE", 502, True),
            ("GET", 400, False),
            ("get", 500, True),
        ],
    )
    def test_status(self, method, status, expected):
        assert _should_retry(method, status=status) is expected

    @pytest.mark.parametrize(
        ("method", "exc", "expected"),
        [
            ("POST", httpx.ConnectError("refused"), True),
            ("POST", httpx.ConnectTimeout("slow"), True),
            ("POST", httpx.ReadTimeout("slow"), False),
            ("POST", httpx.WriteTimeout("slow"), False),
            ("POST", httpx.PoolTimeout("slow"), False),
            ("GET", httpx.ReadTimeout("slow"), True),
            ("GET", httpx.PoolTimeout("slow"), True),
            ("GET", RuntimeError("other"), False),
        ],
    )
    def test_exception(self, method, exc, expected):
        assert _should_retry(method, exc=exc) is expected


class TestRequestRetryPolicy:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch):
        monkeypatch.setattr("ferrolabsai.client.time.sleep", lambda _s: None)

        async def fake_sleep(_delay: float) -> None:
            pass

        monkeypatch.setattr("ferrolabsai.client.asyncio.sleep", fake_sleep)

    def test_post_500_is_not_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 2
        httpx_mock.add_response(method="POST", url=CHAT_URL, status_code=500, json=ERROR_BODY)
        with pytest.raises(FerroServerError):
            client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert len(httpx_mock.get_requests()) == 1

    def test_post_429_is_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 1
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=429,
            json=ERROR_BODY,
            headers={"Retry-After": "0"},
        )
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        response = client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert response.id == "chatcmpl-abc123"
        assert len(httpx_mock.get_requests()) == 2

    def test_get_500_is_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 1
        httpx_mock.add_response(
            method="GET", url=CAPABILITIES_URL, status_code=500, json=ERROR_BODY
        )
        httpx_mock.add_response(method="GET", url=CAPABILITIES_URL, json={"providers": {}})
        assert client.capabilities() == {"providers": {}}
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.parametrize(("method", "status"), [("PUT", 503), ("DELETE", 502)])
    def test_put_and_delete_5xx_are_retried(self, client, httpx_mock: HTTPXMock, method, status):
        client.max_retries = 1
        httpx_mock.add_response(method=method, url=KEY_URL, status_code=status, json=ERROR_BODY)
        httpx_mock.add_response(method=method, url=KEY_URL, json={"ok": True})
        assert client._request(method, "/admin/keys/k1") == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2

    def test_post_read_timeout_is_not_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 2
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="POST", url=CHAT_URL)
        with pytest.raises(FerroConnectionError, match="timed out"):
            client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert len(httpx_mock.get_requests()) == 1

    def test_get_read_timeout_is_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 1
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="GET", url=CAPABILITIES_URL)
        httpx_mock.add_response(method="GET", url=CAPABILITIES_URL, json={"providers": {}})
        assert client.capabilities() == {"providers": {}}
        assert len(httpx_mock.get_requests()) == 2

    def test_post_connect_error_is_retried(self, client, httpx_mock: HTTPXMock):
        client.max_retries = 1
        httpx_mock.add_exception(httpx.ConnectError("refused"), method="POST", url=CHAT_URL)
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        response = client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert response.id == "chatcmpl-abc123"
        assert len(httpx_mock.get_requests()) == 2

    async def test_async_post_500_is_not_retried(self, async_client, httpx_mock: HTTPXMock):
        async_client.max_retries = 2
        httpx_mock.add_response(method="POST", url=CHAT_URL, status_code=500, json=ERROR_BODY)
        with pytest.raises(FerroServerError):
            await async_client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert len(httpx_mock.get_requests()) == 1

    async def test_async_post_429_is_retried(self, async_client, httpx_mock: HTTPXMock):
        async_client.max_retries = 1
        httpx_mock.add_response(
            method="POST",
            url=CHAT_URL,
            status_code=429,
            json=ERROR_BODY,
            headers={"Retry-After": "0"},
        )
        httpx_mock.add_response(method="POST", url=CHAT_URL, json=COMPLETION_RESPONSE)
        response = await async_client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert response.id == "chatcmpl-abc123"
        assert len(httpx_mock.get_requests()) == 2

    async def test_async_post_read_timeout_is_not_retried(
        self, async_client, httpx_mock: HTTPXMock
    ):
        async_client.max_retries = 2
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), method="POST", url=CHAT_URL)
        with pytest.raises(FerroConnectionError, match="timed out"):
            await async_client.chat.completions.create(model="gpt-4o", messages=MESSAGES)
        assert len(httpx_mock.get_requests()) == 1
