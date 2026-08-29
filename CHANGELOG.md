# Changelog

All notable changes to `ferrolabsai` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] — 2026-08-29

The "truth release": every claim the SDK makes now matches what
[ai-gateway](https://github.com/ferro-labs/ai-gateway) actually does, and a
contract suite (`tests/contract/`, run in CI against `v1.4.5` and `main`)
keeps it that way. Compatibility: `ferrolabsai 0.3.x` ↔ `ai-gateway ≥ v1.4.0`.

### Breaking
- **Response metadata reads the gateway's real headers.** `trace_id` comes
  from `X-Request-ID`, `provider` from the chat body's `provider` field (or
  `X-Gateway-Provider` on responses/pass-through), and the new
  `gateway_overhead_ms` from `X-Gateway-Overhead-Ms`. The legacy
  `x-trace-id` / `x-ferro-request-id` header fallbacks and the `x_ferro_*`
  body keys are gone.
- **Removed `ChatCompletion.latency_ms`, `Usage.cost_usd`, `Usage.cache_hit`,
  `Usage.provider`.** They were read from `X-Ferro-Latency-Ms` /
  `X-Ferro-Cost-Usd` / `X-Ferro-Provider` headers that the gateway has never
  emitted at any version, so they were always `None`. `gateway_overhead_ms`
  is *not* a rename of `latency_ms`: it is the gateway's own processing time,
  not end-to-end latency. Cost and cache hits remain available in the request
  log (`admin.logs.list()`), Prometheus, and OTel — not to callers.
- **Removed `route_tag` / `x_route_tag`, `template_id`, `template_variables`**
  from `chat.completions.create()`. The gateway never decoded them
  (`internal/handler/chatrequest.go`); unknown kwargs still pass through
  verbatim.
- **`ModelInfo` is the gateway's `EnrichedModelInfo`.** `provider` is now a
  read-only alias of the new `owned_by`; `input_cost_per_token` /
  `output_cost_per_token` are removed (never served); added `created`, `mode`,
  `max_output_tokens`, `deprecated`; `capabilities` defaults to `[]`.
- **`models.retrieve(id)` no longer calls `GET /v1/models/{id}`.** That path is
  not a native gateway route — it fell through to the `/v1/*` pass-through and
  was forwarded upstream with the operator's provider credential. It is now a
  client-side lookup over `GET /v1/models` and raises `FerroNotFoundError`
  (`code="model_not_found"`) locally. `models.list(provider=, capability=)`
  and `models.search()` filter client-side too (the gateway ignores query
  parameters); `provider` matches `owned_by`, `capability` matches
  `capabilities[]`, `search` is a case-insensitive substring on `id`.
- **Streaming returns a `Stream` / `AsyncStream` object** instead of a bare
  generator. It iterates exactly as before and additionally exposes
  `trace_id`, `provider`, `response`, `close()`, and context-manager support.
  HTTP errors on a stream now raise when `create(stream=True)` is called (async:
  when awaited), not on first iteration.
- **Retries now cover HTTP 408/429/5xx** (previously connect/timeout only),
  with full-jitter backoff and `Retry-After` honoured (capped at 30 s).
  `max_retries=0` disables them. Streaming is never retried.
- `FerroRateLimitError.__init__` gained keyword-only `retry_after`;
  `FerroStreamError.__init__` gained keyword-only `code`.
- `_request(stream=True)` (private) is removed; `_open_stream()` replaces it.

### Added
- `stream_options` parameter (e.g. `{"include_usage": True}`);
  `ChatCompletionChunk.usage`, `.trace_id`, `.provider`; `Usage.reasoning_tokens`,
  `.cache_read_tokens`, `.cache_write_tokens`; `ChatMessage.reasoning_content`,
  `StreamDelta.reasoning_content`; `ChatCompletion.provider_metadata`.
  Mid-stream `{"error": ...}` frames raise `FerroStreamError` with `.code`
  (`stream_error`, `stream_timeout`).
- Request params `max_completion_tokens`, `parallel_tool_calls`,
  `response_format`, `seed` on `chat.completions.create()` (sync + async).
- `FerroBudgetExceededError` (402 `insufficient_quota`) and
  `FerroPermissionError` (403 `insufficient_scope`); every `FerroAPIError`
  now carries `status_code` and the gateway's `code`.
- `client.responses.create() / retrieve(id) / delete(id)` → `/v1/responses`
  (`Response` dataclass; id routes answer 501 `responses_not_configured`
  unless the gateway sets `responses_target`).
- `client.capabilities()` → `/v1/capabilities`; `client.health()`,
  `client.ready()`, `client.live()` → `/health`, `/readyz`, `/livez` (503
  bodies are returned, not raised); `client.rerank()` → `/v1/rerank`;
  `client.moderations.create()` → `/v1/moderations`.
- Admin parity with ai-gateway 1.4: `admin.audit.list()`,
  `admin.providers.catalog()`, `admin.plugins.catalog()`,
  `admin.logs.list(api_key_id=)` (and `stage="all"`),
  `admin.logs.stats(buckets=)`.
- `EmbeddingResponse.trace_id`, `ImageResponse.trace_id`.
- Python 3.13 in the CI matrix and classifiers; mypy runs on every leg.
- Contract suite: `scripts/with-gateway.sh` + `tests/contract/` (stub
  upstream, 23 assertions against a real gateway); `make contract`.
- Unit tests for the previously open good-first-issues (#8 keys
  retrieve/update, #9 config create/delete, #10 logs delete, #12 sync
  models.search/images.generate/admin.health/providers.list, #14 retry
  exhaustion → `FerroConnectionError`, #19 async streaming + embeddings).

### Fixed
- Header metadata is merged into inference bodies only; `/v1/models`,
  probes, and `/admin/*` bodies are returned untouched.
- `admin.providers.catalog()` unwraps the gateway's `{"providers": [...]}`
  envelope.
- `__version__` is a constant kept in sync with `pyproject.toml` (the
  installed-distribution lookup reported a stale number in editable checkouts).
- Resource classes type their `client` (no more `Any` /
  `# type: ignore[no-any-return]`).
- README: "29 providers" → 30 <!-- drift-ok: quoting the stale README claim being corrected -->; `admin.logs.list(trace_id=...)` example (no
  such parameter) replaced; dead `internal/admin/handlers.go` links → the
  `internal/admin/handlers` package; observability section rewritten to list
  exactly what populates and from where; framework section now points at
  `langchain-ferrolabsai`.

### Removed
- Everything listed under **Breaking**: `latency_ms`, `cost_usd`,
  `cache_hit`, `Usage.provider`, `route_tag`, `template_id`,
  `template_variables`, `ModelInfo` pricing fields, `x_ferro_*` /
  `X-Ferro-*` / `x-trace-id` handling. None of it was ever provided or read
  by the gateway.

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
