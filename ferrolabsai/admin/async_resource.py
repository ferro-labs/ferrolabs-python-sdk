"""Async admin resource for /admin/*."""

from __future__ import annotations

import builtins
from typing import Any

from ..types import APIKey, ConfigHistoryEntry, CreatedAPIKey, GatewayConfig


class AsyncAdmin:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.keys = _AsyncKeysResource(client)
        self.config = _AsyncConfigResource(client)
        self.logs = _AsyncLogsResource(client)
        self.providers = _AsyncProvidersResource(client)
        self.plugins = _AsyncPluginsResource(client)

    async def dashboard(self) -> dict[str, Any]:
        return await self._client._request("GET", "/admin/dashboard")  # type: ignore[no-any-return]

    async def health(self) -> dict[str, Any]:
        return await self._client._request("GET", "/admin/health")  # type: ignore[no-any-return]


class _AsyncKeysResource:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def list(self) -> builtins.list[APIKey]:
        data = await self._client._request("GET", "/admin/keys")
        items = data if isinstance(data, list) else (data.get("keys") or data.get("data") or [])
        return [APIKey.from_dict(k) for k in items]

    async def retrieve(self, key_id: str) -> APIKey:
        data = await self._client._request("GET", f"/admin/keys/{key_id}")
        return APIKey.from_dict(data)

    async def create(
        self,
        *,
        name: str,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedAPIKey:
        body: dict[str, Any] = {"name": name}
        if scopes is not None:
            body["scopes"] = scopes
        if expires_at is not None:
            body["expires_at"] = expires_at
        data = await self._client._request("POST", "/admin/keys", json=body)
        return CreatedAPIKey.from_dict(data)

    async def update(
        self,
        key_id: str,
        *,
        name: str | None = None,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
        active: bool | None = None,
    ) -> APIKey:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if scopes is not None:
            body["scopes"] = scopes
        if expires_at is not None:
            body["expires_at"] = expires_at
        if active is not None:
            body["active"] = active
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
        params: dict[str, Any] = {"limit": limit, "offset": offset, "sort": sort}
        if active is not None:
            params["active"] = "true" if active else "false"
        if since is not None:
            params["since"] = since
        return await self._client._request("GET", "/admin/keys/usage", params=params)  # type: ignore[no-any-return]


class _AsyncConfigResource:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def get(self) -> GatewayConfig:
        data = await self._client._request("GET", "/admin/config")
        return GatewayConfig.from_dict(data)

    async def create(self, config: dict[str, Any]) -> dict[str, Any]:
        return await self._client._request("POST", "/admin/config", json=config)  # type: ignore[no-any-return]

    async def update(self, config: dict[str, Any]) -> dict[str, Any]:
        return await self._client._request("PUT", "/admin/config", json=config)  # type: ignore[no-any-return]

    async def delete(self) -> dict[str, Any]:
        return await self._client._request("DELETE", "/admin/config")  # type: ignore[no-any-return]

    async def history(self) -> list[ConfigHistoryEntry]:
        data = await self._client._request("GET", "/admin/config/history")
        items = data.get("data") if isinstance(data, dict) else data
        return [ConfigHistoryEntry.from_dict(e) for e in (items or [])]

    async def rollback(self, version: int) -> dict[str, Any]:
        return await self._client._request("POST", f"/admin/config/rollback/{version}")  # type: ignore[no-any-return]


class _AsyncLogsResource:
    def __init__(self, client: Any) -> None:
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
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if stage is not None:
            params["stage"] = stage
        if provider is not None:
            params["provider"] = provider
        if model is not None:
            params["model"] = model
        if since is not None:
            params["since"] = since
        return await self._client._request("GET", "/admin/logs", params=params)  # type: ignore[no-any-return]

    async def stats(
        self,
        *,
        limit: int | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if since is not None:
            params["since"] = since
        return await self._client._request("GET", "/admin/logs/stats", params=params or None)  # type: ignore[no-any-return]

    async def delete(
        self,
        *,
        before: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if before is not None:
            params["before"] = before
        if stage is not None:
            params["stage"] = stage
        return await self._client._request("DELETE", "/admin/logs", params=params or None)  # type: ignore[no-any-return]


class _AsyncProvidersResource:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def list(self) -> builtins.list[dict[str, Any]]:
        data = await self._client._request("GET", "/admin/providers")
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("providers") or []


class _AsyncPluginsResource:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def list(self) -> builtins.list[dict[str, Any]]:
        data = await self._client._request("GET", "/admin/plugins")
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("plugins") or []
