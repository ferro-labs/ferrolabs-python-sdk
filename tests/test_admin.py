"""Admin API — /admin/* parity with ai-gateway v1.4.x."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from .conftest import BASE_URL

ADMIN = f"{BASE_URL}/admin"

KEY = {
    "id": "key_abc",
    "name": "test-key",
    "scopes": ["admin"],
    "active": True,
    "usage_count": 12,
    "created_at": "2026-04-01T00:00:00Z",
}


class TestKeys:
    def test_create(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", url=f"{ADMIN}/keys", json={**KEY, "key": "fgw_full"})
        key = client.admin.keys.create(
            name="test-key", scopes=["admin"], expires_at="2027-01-01T00:00:00Z"
        )
        assert key.key == "fgw_full"
        assert key.scopes == ["admin"]
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body == {
            "name": "test-key",
            "scopes": ["admin"],
            "expires_at": "2027-01-01T00:00:00Z",
        }

    def test_list_accepts_bare_array(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/keys", json=[KEY])
        keys = client.admin.keys.list()
        assert keys[0].id == "key_abc"
        assert keys[0].usage_count == 12

    def test_retrieve_masks_key(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/keys/key_abc", json={**KEY, "key": "fgw_ab12...cd34"}
        )
        key = client.admin.keys.retrieve("key_abc")
        assert key.id == "key_abc"
        assert key.key == "fgw_ab12...cd34"

    def test_update(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="PUT",
            url=f"{ADMIN}/keys/key_abc",
            json={**KEY, "name": "renamed", "active": False},
        )
        key = client.admin.keys.update("key_abc", name="renamed", active=False)
        assert key.name == "renamed"
        assert key.active is False
        assert json.loads(httpx_mock.get_requests()[0].content) == {
            "name": "renamed",
            "active": False,
        }

    @pytest.mark.parametrize(
        ("method", "http_method", "path"),
        [("revoke", "POST", "/keys/key_abc/revoke"), ("delete", "DELETE", "/keys/key_abc")],
    )
    def test_revoke_and_delete_accept_204(
        self, client, httpx_mock: HTTPXMock, method, http_method, path
    ):
        httpx_mock.add_response(
            method=http_method, url=f"{ADMIN}{path}", status_code=204, content=b""
        )
        assert getattr(client.admin.keys, method)("key_abc") is None

    def test_rotate(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST", url=f"{ADMIN}/keys/key_abc/rotate", json={**KEY, "key": "fgw_new"}
        )
        assert client.admin.keys.rotate("key_abc").key == "fgw_new"

    def test_usage(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{ADMIN}/keys/usage?limit=10&offset=0&sort=usage&active=true",
            json={"data": [], "summary": {"total_usage": 100}},
        )
        assert client.admin.keys.usage(limit=10, active=True)["summary"]["total_usage"] == 100

    async def test_async_keys(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/keys", json=[KEY])
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/keys/key_abc", json=KEY)
        httpx_mock.add_response(method="PUT", url=f"{ADMIN}/keys/key_abc", json=KEY)
        httpx_mock.add_response(
            method="POST", url=f"{ADMIN}/keys/key_abc/revoke", status_code=204, content=b""
        )
        httpx_mock.add_response(
            method="DELETE", url=f"{ADMIN}/keys/key_abc", status_code=204, content=b""
        )
        assert (await async_client.admin.keys.list())[0].id == "key_abc"
        assert (await async_client.admin.keys.retrieve("key_abc")).name == "test-key"
        assert (await async_client.admin.keys.update("key_abc", name="x")).id == "key_abc"
        await async_client.admin.keys.revoke("key_abc")
        await async_client.admin.keys.delete("key_abc")


class TestConfig:
    def test_get(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{ADMIN}/config",
            json={
                "strategy": {"mode": "fallback"},
                "targets": [{"virtual_key": "openai"}],
                "mcp_servers": [],
            },
        )
        cfg = client.admin.config.get()
        assert cfg.strategy == {"mode": "fallback"}
        assert cfg.targets == [{"virtual_key": "openai"}]
        assert cfg.raw["mcp_servers"] == []

    @pytest.mark.parametrize(("method", "http_method"), [("create", "POST"), ("update", "PUT")])
    def test_create_and_update(self, client, httpx_mock: HTTPXMock, method, http_method):
        httpx_mock.add_response(method=http_method, url=f"{ADMIN}/config", json={"status": "ok"})
        payload = {"strategy": {"mode": "single"}, "targets": [{"virtual_key": "openai"}]}
        assert getattr(client.admin.config, method)(payload) == {"status": "ok"}
        assert json.loads(httpx_mock.get_requests()[0].content) == payload

    def test_delete(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="DELETE", url=f"{ADMIN}/config", json={"status": "reset"})
        assert client.admin.config.delete() == {"status": "reset"}

    def test_history_and_rollback(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{ADMIN}/config/history",
            json={
                "data": [
                    {"version": 1, "updated_at": "t", "config": {"strategy": {"mode": "single"}}}
                ]
            },
        )
        httpx_mock.add_response(
            method="POST", url=f"{ADMIN}/config/rollback/1", json={"status": "rolled_back"}
        )
        history = client.admin.config.history()
        assert history[0].version == 1
        assert history[0].config.strategy == {"mode": "single"}
        assert client.admin.config.rollback(1)["status"] == "rolled_back"

    async def test_async_history(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/config/history", json={"data": [{"version": 2}]}
        )
        assert (await async_client.admin.config.history())[0].version == 2


class TestLogs:
    def test_list_forwards_v14_filters(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{ADMIN}/logs?limit=10&offset=0&stage=all&provider=openai&model=gpt-4o&since=t&api_key_id=none",
            json={"data": [{"trace_id": "t1"}], "summary": {"total_entries": 1}},
        )
        result = client.admin.logs.list(
            limit=10, stage="all", provider="openai", model="gpt-4o", since="t", api_key_id="none"
        )
        assert result["data"][0]["trace_id"] == "t1"

    def test_list_rejects_trace_id_filter(self, client):
        with pytest.raises(TypeError):
            client.admin.logs.list(trace_id="t1")

    def test_stats_with_buckets(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/logs/stats?buckets=12", json={"total": 42, "series": []}
        )
        assert client.admin.logs.stats(buckets=12)["total"] == 42

    def test_delete(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="DELETE",
            url=f"{ADMIN}/logs?before=2026-01-01T00%3A00%3A00Z",
            json={"deleted": 3},
        )
        assert client.admin.logs.delete(before="2026-01-01T00:00:00Z") == {"deleted": 3}

    async def test_async_logs(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/logs?limit=50&offset=0&api_key_id=k1", json={"data": []}
        )
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/logs/stats?buckets=4", json={"total": 0}
        )
        httpx_mock.add_response(method="DELETE", url=f"{ADMIN}/logs", json={"deleted": 0})
        assert await async_client.admin.logs.list(api_key_id="k1") == {"data": []}
        assert await async_client.admin.logs.stats(buckets=4) == {"total": 0}
        assert await async_client.admin.logs.delete() == {"deleted": 0}


class TestProvidersPluginsAudit:
    @pytest.mark.parametrize(
        "payload",
        [[{"name": "cache"}], {"data": [{"name": "cache"}]}, {"plugins": [{"name": "cache"}]}],
    )
    def test_plugins_list_shapes(self, client, httpx_mock: HTTPXMock, payload):
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/plugins", json=payload)
        assert client.admin.plugins.list() == [{"name": "cache"}]

    def test_providers_list(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/providers", json={"data": [{"name": "openai"}]}
        )
        assert client.admin.providers.list() == [{"name": "openai"}]

    def test_catalogs(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{ADMIN}/providers/catalog",
            json=[{"id": "openai", "registered": True, "catalog_models": 90}],
        )
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/plugins/catalog", json={"data": [{"name": "budget"}]}
        )
        assert client.admin.providers.catalog()[0]["id"] == "openai"
        assert client.admin.plugins.catalog() == [{"name": "budget"}]

    def test_audit_list(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url=f"{ADMIN}/audit?limit=20&offset=0&action=key.create&actor_id=k1&outcome=success&since=t",
            json={"data": [{"action": "key.create"}], "summary": {"total_entries": 1}},
        )
        result = client.admin.audit.list(
            action="key.create", actor_id="k1", outcome="success", since="t", limit=20
        )
        assert result["data"][0]["action"] == "key.create"

    def test_dashboard_and_health(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/dashboard", json={"keys": {"active": 5}}
        )
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/health", json={"status": "ok"})
        assert client.admin.dashboard()["keys"]["active"] == 5
        assert client.admin.health()["status"] == "ok"

    async def test_async_parity(self, async_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/providers", json={"data": [{"name": "openai"}]}
        )
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/providers/catalog", json=[{"id": "openai"}]
        )
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/plugins/catalog", json={"data": []})
        httpx_mock.add_response(
            method="GET", url=f"{ADMIN}/audit?limit=50&offset=0", json={"data": []}
        )
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/health", json={"status": "ok"})
        httpx_mock.add_response(method="GET", url=f"{ADMIN}/dashboard", json={})
        assert await async_client.admin.providers.list() == [{"name": "openai"}]
        assert await async_client.admin.providers.catalog() == [{"id": "openai"}]
        assert await async_client.admin.plugins.catalog() == []
        assert await async_client.admin.audit.list() == {"data": []}
        assert (await async_client.admin.health())["status"] == "ok"
        assert await async_client.admin.dashboard() == {}
