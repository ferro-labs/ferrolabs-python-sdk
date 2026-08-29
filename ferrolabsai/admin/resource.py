"""
Admin resource — manages a Ferro Labs AI Gateway instance via /admin/*.

Routes mirror the OSS gateway admin API defined in the
``ai-gateway/internal/admin/handlers`` package (``Handlers.Routes``):

Read (read_only or admin scope):
    GET    /admin/dashboard
    GET    /admin/keys
    GET    /admin/keys/usage
    GET    /admin/keys/{id}
    GET    /admin/logs
    GET    /admin/logs/stats
    GET    /admin/providers
    GET    /admin/providers/catalog
    GET    /admin/health
    GET    /admin/plugins
    GET    /admin/plugins/catalog
    GET    /admin/config
    GET    /admin/config/history
    GET    /admin/audit

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

Dashboard sessions (``/admin/session(s)``) are deliberately not wrapped — SDK
callers hold API keys. All requests use the ``Authorization: Bearer ...``
header set on ``FerroClient``; a ``read_only`` key gets 403
``insufficient_scope`` (:class:`FerroPermissionError`) on write routes.
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


def items(data: Any, *keys: str) -> builtins.list[dict[str, Any]]:
    """Unwrap a bare array or a ``{"<key>": [...]}`` envelope into a list."""
    if isinstance(data, list):
        return data
    for key in keys:
        found = data.get(key)
        if isinstance(found, list):
            return found
    return []


def query(**params: Any) -> dict[str, Any]:
    """Drop ``None`` values so they are not sent as ``?x=None``."""
    return {k: v for k, v in params.items() if v is not None}


class Admin:
    """
    Admin namespace exposed as ``client.admin``.

    Sub-resources:
        keys      — manage API keys (CRUD + revoke + rotate + usage)
        config    — manage the active routing config (get/set/history/rollback)
        logs      — query and prune the request log
        providers — registered providers (``list``) and the full provider catalog
        plugins   — installed plugins (``list``) and the built-in plugin catalog
        audit     — admin audit trail

    Plus convenience methods on the namespace itself:
        dashboard() — high-level usage and key counts
        health()    — gateway health check (admin view)

    Example::

        # Create a key
        new_key = client.admin.keys.create(name="backend-service", scopes=["admin"])
        print(new_key.key)  # full fgw_... — shown ONCE

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
        self.audit = _AuditResource(client)

    def dashboard(self) -> dict[str, Any]:
        """``GET /admin/dashboard`` — provider/key counts and request log totals."""
        return self._client._request("GET", "/admin/dashboard")

    def health(self) -> dict[str, Any]:
        """``GET /admin/health`` — gateway health check (admin scope view)."""
        return self._client._request("GET", "/admin/health")


# ----------------------------------------------------------------------
# Keys
# ----------------------------------------------------------------------


class _KeysResource:
    """Manage gateway API keys via ``/admin/keys``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(self) -> builtins.list[APIKey]:
        """``GET /admin/keys`` — list all API keys (secrets masked)."""
        return [
            APIKey.from_dict(k)
            for k in items(self._client._request("GET", "/admin/keys"), "keys", "data")
        ]

    def retrieve(self, key_id: str) -> APIKey:
        """``GET /admin/keys/{id}`` — fetch metadata for one key (key value is masked)."""
        return APIKey.from_dict(self._client._request("GET", f"/admin/keys/{key_id}"))

    def create(
        self,
        *,
        name: str,
        scopes: builtins.list[str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedAPIKey:
        """
        ``POST /admin/keys`` — create a new API key.

        The full key value (``fgw_...``) is only returned in this response.
        Store it securely — it cannot be retrieved again.

        Args:
            name: Human-readable label for this key.
            scopes: ``["admin"]`` or ``["read_only"]`` (unknown scope → 400 ``invalid_scope``).
            expires_at: RFC3339 expiry timestamp. ``None`` = never expires.
        """
        body = query(name=name, scopes=scopes, expires_at=expires_at)
        return CreatedAPIKey.from_dict(self._client._request("POST", "/admin/keys", json=body))

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
        body = query(name=name, scopes=scopes, expires_at=expires_at, active=active)
        return APIKey.from_dict(self._client._request("PUT", f"/admin/keys/{key_id}", json=body))

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
        return CreatedAPIKey.from_dict(
            self._client._request("POST", f"/admin/keys/{key_id}/rotate")
        )

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
        params = query(
            limit=limit,
            offset=offset,
            sort=sort,
            active=None if active is None else ("true" if active else "false"),
            since=since,
        )
        return self._client._request("GET", "/admin/keys/usage", params=params)


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------


class _ConfigResource:
    """
    Manage the active gateway routing config via ``/admin/config``.

    The OSS gateway has a *single* active config (not a multi-config registry).
    Use ``history()`` to inspect previous versions and ``rollback(version)`` to
    revert. Updates are zero-downtime hot reloads. Note that ``get()`` masks
    secrets and redacts free-form map keys, so its body does not round-trip
    unchanged into ``update()``.
    """

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def get(self) -> GatewayConfig:
        """``GET /admin/config`` — fetch the currently active config."""
        return GatewayConfig.from_dict(self._client._request("GET", "/admin/config"))

    def create(self, config: dict[str, Any]) -> dict[str, Any]:
        """``POST /admin/config`` — install a new config (status 201). Unknown keys → 400."""
        return self._client._request("POST", "/admin/config", json=config)

    def update(self, config: dict[str, Any]) -> dict[str, Any]:
        """``PUT /admin/config`` — replace the active config (hot reload, no restart)."""
        return self._client._request("PUT", "/admin/config", json=config)

    def delete(self) -> dict[str, Any]:
        """``DELETE /admin/config`` — reset the active config to its default."""
        return self._client._request("DELETE", "/admin/config")

    def history(self) -> builtins.list[ConfigHistoryEntry]:
        """``GET /admin/config/history`` — list all prior config versions."""
        data = self._client._request("GET", "/admin/config/history")
        return [ConfigHistoryEntry.from_dict(e) for e in items(data, "data")]

    def rollback(self, version: int) -> dict[str, Any]:
        """``POST /admin/config/rollback/{version}`` — revert to a prior version."""
        return self._client._request("POST", f"/admin/config/rollback/{version}")


# ----------------------------------------------------------------------
# Logs
# ----------------------------------------------------------------------


class _LogsResource:
    """
    Query the gateway request log via ``/admin/logs``.

    Requires a request-log store (``REQUEST_LOG_STORE_BACKEND=sqlite|postgres``
    on the gateway); the endpoints answer 501 without one.
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
        api_key_id: str | None = None,
    ) -> dict[str, Any]:
        """
        ``GET /admin/logs`` — paginated request log entries (one row per request).

        Args:
            limit: Max entries to return (server caps at 200).
            offset: Pagination offset.
            stage: Default lists terminal rows only; ``"all"`` includes every
                lifecycle stage (``before_request`` / ``after_request`` / ``on_error``).
            provider: Filter by provider name.
            model: Filter by model id.
            since: RFC3339 timestamp — only entries at or after this time.
            api_key_id: Filter by the calling key's id (``"none"`` = master key / no key).
        """
        params = query(
            limit=limit,
            offset=offset,
            stage=stage,
            provider=provider,
            model=model,
            since=since,
            api_key_id=api_key_id,
        )
        return self._client._request("GET", "/admin/logs", params=params)

    def stats(
        self,
        *,
        buckets: int | None = None,
        limit: int | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        """``GET /admin/logs/stats`` — totals, latency/TTFT percentiles, per-provider
        and per-model cost; ``buckets=N`` adds an ``N``-point time series."""
        params = query(buckets=buckets, limit=limit, since=since)
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
        params = query(before=before, stage=stage)
        return self._client._request("DELETE", "/admin/logs", params=params or None)


# ----------------------------------------------------------------------
# Providers / Plugins / Audit
# ----------------------------------------------------------------------


class _ProvidersResource:
    """Providers via ``/admin/providers``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(self) -> builtins.list[dict[str, Any]]:
        """``GET /admin/providers`` — registered providers and their availability."""
        return items(self._client._request("GET", "/admin/providers"), "data", "providers")

    def catalog(self) -> builtins.list[dict[str, Any]]:
        """``GET /admin/providers/catalog`` — every provider the build knows:
        ``{id, registered, catalog_models}``."""
        return items(self._client._request("GET", "/admin/providers/catalog"), "providers", "data")


class _PluginsResource:
    """Plugins via ``/admin/plugins``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(self) -> builtins.list[dict[str, Any]]:
        """``GET /admin/plugins`` — configured gateway plugins."""
        return items(self._client._request("GET", "/admin/plugins"), "data", "plugins")

    def catalog(self) -> builtins.list[dict[str, Any]]:
        """``GET /admin/plugins/catalog`` — built-in plugins available to configure."""
        return items(self._client._request("GET", "/admin/plugins/catalog"), "data")


class _AuditResource:
    """Admin audit trail via ``/admin/audit``."""

    def __init__(self, client: FerroClient) -> None:
        self._client = client

    def list(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        outcome: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """``GET /admin/audit`` — ``{data, summary, filters}`` of admin actions
        (key/config writes, denied attempts)."""
        params = query(
            limit=limit,
            offset=offset,
            action=action,
            actor_id=actor_id,
            outcome=outcome,
            since=since,
        )
        return self._client._request("GET", "/admin/audit", params=params)
