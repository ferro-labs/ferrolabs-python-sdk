"""
Admin resource — manages a Ferro Labs AI Gateway instance via /admin/*.

Routes mirror the OSS gateway admin API defined in
``ai-gateway/internal/admin/handlers.go`` (``Handlers.Routes``):

Read (read-only or admin scope):
    GET    /admin/dashboard
    GET    /admin/keys
    GET    /admin/keys/usage
    GET    /admin/keys/{id}
    GET    /admin/logs
    GET    /admin/logs/stats
    GET    /admin/providers
    GET    /admin/health
    GET    /admin/plugins
    GET    /admin/config
    GET    /admin/config/history

Write (admin scope only):
    POST   /admin/keys
    PUT    /admin/keys/{id}
    DELETE /admin/keys/{id}
    POST   /admin/keys/{id}/revoke
    POST   /admin/keys/{id}/rotate
    DELETE /admin/logs
    POST   /admin/config
    PUT    /admin/config
    DELETE /admin/config
    POST   /admin/config/rollback/{version}

These endpoints are available on any self-hosted Ferro Labs AI Gateway
instance (and on FerroCloud). All requests require an API key with admin
scope (or read-only scope for read endpoints), passed via the standard
``Authorization: Bearer ...`` header set on ``FerroClient``.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from ..types import (
    APIKey,
    ConfigHistoryEntry,
    CreatedAPIKey,
    GatewayConfig,
)

if TYPE_CHECKING:
    from ..client import FerroClient


class Admin:
    """
    Admin namespace exposed as ``client.admin``.

    Sub-resources:
        keys      — manage API keys (CRUD + revoke + rotate + usage)
        config    — manage the active routing config (get/set/history/rollback)
        logs      — query and prune the request log
        providers — list registered provider plugins
        plugins   — list installed gateway plugins

    Plus convenience methods on the namespace itself:
        dashboard() — high-level usage and key counts
        health()    — gateway health check

    Example::

        # Create a key
        new_key = client.admin.keys.create(name="backend-service")
        print(new_key.key)  # full sk-ferro-... — shown ONCE

        # Update the active routing config (zero-downtime hot reload)
        client.admin.config.update({
            "strategy": {"mode": "fallback"},
            "targets": [
                {"virtual_key": "openai", "weight": 1},
                {"virtual_key": "anthropic", "weight": 1},
            ],
        })

        # Roll back to a previous version
        history = client.admin.config.history()
        client.admin.config.rollback(history[-2].version)
    """

    def __init__(self, client: FerroClient) -> None:
        self._client = client
        self.keys = _KeysResource(client)
        self.config = _ConfigResource(client)
        self.logs = _LogsResource(client)
        self.providers = _ProvidersResource(client)
        self.plugins = _PluginsResource(client)

    def dashboard(self) -> dict[str, Any]:
        """``GET /admin/dashboard`` — provider/key counts and request log totals."""
        return self._client._request("GET", "/admin/dashboard")

    def health(self) -> dict[str, Any]:
        """``GET /admin/health`` — gateway health check."""
        return self._client._request("GET", "/admin/health")


# ----------------------------------------------------------------------
# Keys
# ----------------------------------------------------------------------


class _KeysResource:
    """Manage gateway API keys via ``/admin/keys``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(self) -> builtins.list[APIKey]:
        """``GET /admin/keys`` — list all API keys."""
        data = self._client._request("GET", "/admin/keys")
        items = data if isinstance(data, list) else (data.get("keys") or data.get("data") or [])
        return [APIKey.from_dict(k) for k in items]

    def retrieve(self, key_id: str) -> APIKey:
        """``GET /admin/keys/{id}`` — fetch metadata for one key (key value is masked)."""
        data = self._client._request("GET", f"/admin/keys/{key_id}")
        return APIKey.from_dict(data)

    def create(
        self,
        *,
        name: str,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedAPIKey:
        """
        ``POST /admin/keys`` — create a new API key.

        The full key value (``sk-ferro-...``) is only returned in this response.
        Store it securely — it cannot be retrieved again.

        Args:
            name: Human-readable label for this key.
            scopes: List of scopes (e.g. ``["admin"]``, ``["read-only"]``).
            expires_at: RFC3339 expiry timestamp. ``None`` = never expires.
        """
        body: dict[str, Any] = {"name": name}
        if scopes is not None:
            body["scopes"] = scopes
        if expires_at is not None:
            body["expires_at"] = expires_at
        data = self._client._request("POST", "/admin/keys", json=body)
        return CreatedAPIKey.from_dict(data)

    def update(
        self,
        key_id: str,
        *,
        name: str | None = None,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
        active: bool | None = None,
    ) -> APIKey:
        """``PUT /admin/keys/{id}`` — update key metadata."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if scopes is not None:
            body["scopes"] = scopes
        if expires_at is not None:
            body["expires_at"] = expires_at
        if active is not None:
            body["active"] = active
        data = self._client._request("PUT", f"/admin/keys/{key_id}", json=body)
        return APIKey.from_dict(data)

    def delete(self, key_id: str) -> None:
        """``DELETE /admin/keys/{id}`` — permanently delete a key."""
        self._client._request("DELETE", f"/admin/keys/{key_id}")

    def revoke(self, key_id: str) -> None:
        """
        ``POST /admin/keys/{id}/revoke`` — mark a key as revoked.

        The record is preserved (for audit) but the key is invalidated
        immediately. Use ``delete()`` to permanently remove the record.
        """
        self._client._request("POST", f"/admin/keys/{key_id}/revoke")

    def rotate(self, key_id: str) -> CreatedAPIKey:
        """
        ``POST /admin/keys/{id}/rotate`` — atomically replace a key's value.

        Returns the new key. Store it securely — shown only once.
        """
        data = self._client._request("POST", f"/admin/keys/{key_id}/rotate")
        return CreatedAPIKey.from_dict(data)

    def usage(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str = "usage",
        active: bool | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        """
        ``GET /admin/keys/usage`` — per-key usage counts and last-used timestamps.

        Args:
            limit: Max keys to return (server caps at 100).
            offset: Pagination offset.
            sort: ``"usage"`` (default) or ``"last_used"``.
            active: Filter by active flag.
            since: RFC3339 timestamp — only keys used at or after this time.

        Returns the raw response: ``{data, summary, filters}``.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset, "sort": sort}
        if active is not None:
            params["active"] = "true" if active else "false"
        if since is not None:
            params["since"] = since
        return self._client._request("GET", "/admin/keys/usage", params=params)


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------


class _ConfigResource:
    """
    Manage the active gateway routing config via ``/admin/config``.

    The OSS gateway has a *single* active config (not a multi-config registry).
    Use ``history()`` to inspect previous versions and ``rollback(version)`` to
    revert. Updates are zero-downtime hot reloads.
    """

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def get(self) -> GatewayConfig:
        """``GET /admin/config`` — fetch the currently active config."""
        data = self._client._request("GET", "/admin/config")
        return GatewayConfig.from_dict(data)

    def create(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        ``POST /admin/config`` — install a new config (status 201).

        ``config`` is the raw routing-config dict (``strategy``, ``targets``,
        ``plugins``, ``aliases``, etc.).
        """
        return self._client._request("POST", "/admin/config", json=config)

    def update(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        ``PUT /admin/config`` — replace the active config (status 200).

        Hot-reloads in place — no gateway restart required. In-flight
        requests complete with the previous config; the next request after
        the update uses the new one.
        """
        return self._client._request("PUT", "/admin/config", json=config)

    def delete(self) -> dict[str, Any]:
        """``DELETE /admin/config`` — reset the active config to its default."""
        return self._client._request("DELETE", "/admin/config")

    def history(self) -> list[ConfigHistoryEntry]:
        """``GET /admin/config/history`` — list all prior config versions."""
        data = self._client._request("GET", "/admin/config/history")
        items = data.get("data") if isinstance(data, dict) else data
        return [ConfigHistoryEntry.from_dict(e) for e in (items or [])]

    def rollback(self, version: int) -> dict[str, Any]:
        """``POST /admin/config/rollback/{version}`` — revert to a prior version."""
        return self._client._request("POST", f"/admin/config/rollback/{version}")


# ----------------------------------------------------------------------
# Logs
# ----------------------------------------------------------------------


class _LogsResource:
    """
    Query the gateway request log via ``/admin/logs``.

    Replaces what was previously ``client.admin.usage.requests()`` — the OSS
    gateway exposes raw per-request log entries (with trace IDs, latency,
    tokens, cost, and provider routing decisions) at ``/admin/logs``.

    Note: request log storage must be enabled in the gateway (via the
    ``logger`` plugin). Endpoints return HTTP 501 if it isn't.
    """

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        stage: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        """
        ``GET /admin/logs`` — paginated request log entries.

        Args:
            limit: Max entries to return (server caps at 200).
            offset: Pagination offset.
            stage: Filter by lifecycle stage (e.g. ``"on_error"``).
            provider: Filter by provider name.
            model: Filter by model id.
            since: RFC3339 timestamp — only entries at or after this time.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if stage is not None:
            params["stage"] = stage
        if provider is not None:
            params["provider"] = provider
        if model is not None:
            params["model"] = model
        if since is not None:
            params["since"] = since
        return self._client._request("GET", "/admin/logs", params=params)

    def stats(
        self,
        *,
        limit: int | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        """``GET /admin/logs/stats`` — aggregate counts, latency, and cost."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if since is not None:
            params["since"] = since
        return self._client._request("GET", "/admin/logs/stats", params=params or None)

    def delete(
        self,
        *,
        before: str | None = None,
        stage: str | None = None,
    ) -> dict[str, Any]:
        """
        ``DELETE /admin/logs`` — prune log entries.

        Args:
            before: RFC3339 timestamp — delete entries strictly before this.
            stage: Restrict deletion to a single lifecycle stage.
        """
        params: dict[str, Any] = {}
        if before is not None:
            params["before"] = before
        if stage is not None:
            params["stage"] = stage
        return self._client._request("DELETE", "/admin/logs", params=params or None)


# ----------------------------------------------------------------------
# Providers / Plugins
# ----------------------------------------------------------------------


class _ProvidersResource:
    """List provider plugins via ``/admin/providers``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(self) -> builtins.list[dict[str, Any]]:
        """``GET /admin/providers`` — registered providers and their availability."""
        data = self._client._request("GET", "/admin/providers")
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("providers") or []


class _PluginsResource:
    """List installed plugins via ``/admin/plugins``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(self) -> builtins.list[dict[str, Any]]:
        """``GET /admin/plugins`` — gateway plugins (cache, logger, ratelimit, ...)."""
        data = self._client._request("GET", "/admin/plugins")
        if isinstance(data, list):
            return data
        return data.get("data") or data.get("plugins") or []
