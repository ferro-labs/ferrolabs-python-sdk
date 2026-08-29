"""Async admin resource for /admin/* — see ``admin/resource.py`` for route docs."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from ..types import APIKey, ConfigHistoryEntry, CreatedAPIKey, GatewayConfig
from .resource import items, query

if TYPE_CHECKING:
    from ..client import AsyncFerroClient


class AsyncAdmin:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client
        self.keys = _AsyncKeysResource(client)
        self.config = _AsyncConfigResource(client)
        self.logs = _AsyncLogsResource(client)
        self.providers = _AsyncProvidersResource(client)
        self.plugins = _AsyncPluginsResource(client)
        self.audit = _AsyncAuditResource(client)

    async def dashboard(self) -> dict[str, Any]:
        return await self._client._request("GET", "/admin/dashboard")

    async def health(self) -> dict[str, Any]:
        return await self._client._request("GET", "/admin/health")


class _AsyncKeysResource:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def list(self) -> builtins.list[APIKey]:
        data = await self._client._request("GET", "/admin/keys")
        return [APIKey.from_dict(k) for k in items(data, "keys", "data")]

    async def retrieve(self, key_id: str) -> APIKey:
        return APIKey.from_dict(await self._client._request("GET", f"/admin/keys/{key_id}"))

    async def create(
        self,
        *,
        name: str,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedAPIKey:
        body = query(name=name, scopes=scopes, expires_at=expires_at)
        return CreatedAPIKey.from_dict(
            await self._client._request("POST", "/admin/keys", json=body)
        )

    async def update(
        self,
        key_id: str,
        *,
        name: str | None = None,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
        active: bool | None = None,
    ) -> APIKey:
        body = query(name=name, scopes=scopes, expires_at=expires_at, active=active)
        data = await self._client._request("PUT", f"/admin/keys/{key_id}", json=body)
        return APIKey.from_dict(data)

    async def delete(self, key_id: str) -> None:
        await self._client._request("DELETE", f"/admin/keys/{key_id}")

    async def revoke(self, key_id: str) -> None:
        await self._client._request("POST", f"/admin/keys/{key_id}/revoke")

    async def rotate(self, key_id: str) -> CreatedAPIKey:
        data = await self._client._request("POST", f"/admin/keys/{key_id}/rotate")
        return CreatedAPIKey.from_dict(data)

    async def usage(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str = "usage",
        active: bool | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        params = query(
            limit=limit,
            offset=offset,
            sort=sort,
            active=None if active is None else ("true" if active else "false"),
            since=since,
        )
        return await self._client._request("GET", "/admin/keys/usage", params=params)


class _AsyncConfigResource:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def get(self) -> GatewayConfig:
        return GatewayConfig.from_dict(await self._client._request("GET", "/admin/config"))

    async def create(self, config: dict[str, Any]) -> dict[str, Any]:
        return await self._client._request("POST", "/admin/config", json=config)

    async def update(self, config: dict[str, Any]) -> dict[str, Any]:
        return await self._client._request("PUT", "/admin/config", json=config)

    async def delete(self) -> dict[str, Any]:
        return await self._client._request("DELETE", "/admin/config")

    async def history(self) -> builtins.list[ConfigHistoryEntry]:
        data = await self._client._request("GET", "/admin/config/history")
        return [ConfigHistoryEntry.from_dict(e) for e in items(data, "data")]

    async def rollback(self, version: int) -> dict[str, Any]:
        return await self._client._request("POST", f"/admin/config/rollback/{version}")


class _AsyncLogsResource:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        stage: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        since: str | None = None,
        api_key_id: str | None = None,
    ) -> dict[str, Any]:
        params = query(
            limit=limit,
            offset=offset,
            stage=stage,
            provider=provider,
            model=model,
            since=since,
            api_key_id=api_key_id,
        )
        return await self._client._request("GET", "/admin/logs", params=params)

    async def stats(
        self,
        *,
        buckets: int | None = None,
        limit: int | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        params = query(buckets=buckets, limit=limit, since=since)
        return await self._client._request("GET", "/admin/logs/stats", params=params or None)

    async def delete(
        self,
        *,
        before: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        params = query(before=before, stage=stage)
        return await self._client._request("DELETE", "/admin/logs", params=params or None)


class _AsyncProvidersResource:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def list(self) -> builtins.list[dict[str, Any]]:
        return items(await self._client._request("GET", "/admin/providers"), "data", "providers")

    async def catalog(self) -> builtins.list[dict[str, Any]]:
        return items(
            await self._client._request("GET", "/admin/providers/catalog"), "providers", "data"
        )


class _AsyncPluginsResource:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def list(self) -> builtins.list[dict[str, Any]]:
        return items(await self._client._request("GET", "/admin/plugins"), "data", "plugins")

    async def catalog(self) -> builtins.list[dict[str, Any]]:
        return items(await self._client._request("GET", "/admin/plugins/catalog"), "data")


class _AsyncAuditResource:
    def __init__(self, client: AsyncFerroClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        outcome: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params = query(
            limit=limit,
            offset=offset,
            action=action,
            actor_id=actor_id,
            outcome=outcome,
            since=since,
        )
        return await self._client._request("GET", "/admin/audit", params=params)
