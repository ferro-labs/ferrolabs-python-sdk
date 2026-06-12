# Changelog

All notable changes to `ferrolabsai` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.1] — 2026-06-13

### Fixed
- Streaming completions now raise `FerroStreamError` on malformed SSE chunks
  instead of silently dropping them, for both the sync and async clients. This
  is the first code path that actually raises the previously-unused
  `FerroStreamError`.

### Added
- Test coverage for `admin.dashboard()` and `admin.plugins.list()` (bare-array,
  `{"data": [...]}`, and `{"plugins": [...]}` response shapes).
- Streaming malformed-chunk regression tests for the sync and async clients.

## [0.2.0] — 2026-05-14

### Added
- Awaitable async resources for models, images, and admin endpoints:
  `async_client.models.*`, `async_client.images.generate()`, and
  `async_client.admin.*` now use async request paths instead of sync resource
  classes.
- Capped exponential retry backoff for sync and async connection/timeout
  retries.
- `py.typed` marker for downstream type checkers.

### Changed
- Package version lookup now uses package metadata through a shared version
  helper, keeping `__version__` and the client user agent aligned.
- `route_tag`, `template_id`, and `template_variables` remain forwarded
  request fields, but are documented as gateway-dependent until OSS gateway
  support is confirmed.

### Fixed
- Integration package publish workflows now use valid GitHub tag glob
  patterns, while keeping exact tag/version validation in the publish job.
- Async requests now return `{}` for `204 No Content` and other empty-body
  responses, matching sync client behavior.
- Async custom HTTP clients merge SDK auth/default headers, matching sync
  client behavior.
- Request IDs propagate from error response headers or `trace_id` response
  bodies into Ferro exceptions.

## [0.1.0] — 2026-04-09

### Added
- `FerroClient` — synchronous client with OpenAI-compatible interface
- `AsyncFerroClient` — async client using `httpx.AsyncClient`
- `client.chat.completions.create()` — streaming and non-streaming
- `client.embeddings.create()` — text embeddings
- `client.images.generate()` — image generation
- `client.models.list()` / `.retrieve()` / `.search()` — 2,500+ model catalog
- `client.admin.keys` — API key CRUD (list, retrieve, create, update, delete, revoke, rotate, usage) backed by `/admin/keys`
- `client.admin.config` — single-active routing config: `get`, `create`, `update`, `delete`, `history`, `rollback` backed by `/admin/config`
- `client.admin.logs` — request log query / stats / prune backed by `/admin/logs`
- `client.admin.providers`, `client.admin.plugins`, `client.admin.dashboard()`, `client.admin.health()`
- Ferro-specific extras: `template_id`, `template_variables`, `route_tag`, `cost_usd`, `provider`
- Full exception hierarchy: `FerroAuthError`, `FerroRateLimitError`, `FerroNotFoundError`, `FerroServerError`, `FerroConnectionError`
- Auto-retry on connection errors (configurable `max_retries`)
- Context manager support (`with FerroClient(...) as client:`)
- Environment variable support: `FERRO_API_KEY`, `FERRO_BASE_URL`, `OPENAI_API_KEY` fallback
- Test suite with 100% mocked HTTP (no real gateway needed)
- GitHub Actions CI across Python 3.9–3.12 with PyPI trusted publishing
