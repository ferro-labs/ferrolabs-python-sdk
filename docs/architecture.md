# Architecture — ferrolabsai Python SDK

This document describes the internal architecture of the `ferrolabsai` SDK, how the pieces fit together, and the design decisions behind them. It is written against **ai-gateway v1.4.5**; the contract suite (`tests/contract/`) keeps it honest.

---

## High-Level Overview

The SDK acts as a thin HTTP client that sits between application code and a running [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) instance. It provides an OpenAI-compatible surface so users can switch from `openai.OpenAI` to `ferrolabsai.FerroClient` with minimal code changes, while gaining access to 30 LLM providers, smart routing, and gateway management APIs.

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Code                         │
│                                                             │
│  client.chat.completions.create(model="gpt-4o", ...)        │
│  client.embeddings.create(model="text-embedding-3-small")   │
│  client.admin.config.update({...})                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────────┐
              │     ferrolabsai SDK         │
              │                             │
              │  FerroClient / AsyncFerro   │
              │    ├── chat.completions     │
              │    ├── embeddings           │
              │    ├── images               │
              │    ├── models               │
              │    ├── responses            │
              │    ├── moderations          │
              │    ├── rerank() / probes    │
              │    └── admin                │
              │         ├── keys            │
              │         ├── config          │
              │         ├── logs            │
              │         ├── providers       │
              │         ├── plugins         │
              │         └── audit           │
              └────────────┬────────────────┘
                           │  HTTP (httpx)
              ┌────────────▼────────────────┐
              │   Ferro Labs AI Gateway     │
              │  /v1/*  /admin/*  /health   │
              │                             │
              │  Routing · Fallback · Cache │
              │  Budgets · Logging · OTel   │
              └────────────┬────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐    ┌────▼─────┐   ┌────▼────┐
      │ OpenAI  │    │Anthropic │   │  Groq   │  ... 30 providers
      └─────────┘    └──────────┘   └─────────┘
```

---

## Module Map

```
ferrolabsai/
├── __init__.py               # Public API surface & __all__
├── _version.py               # __version__ constant (kept in sync with pyproject.toml)
├── client.py                 # FerroClient, AsyncFerroClient, retry policy, _raise_api_error
├── streaming.py              # Stream / AsyncStream SSE wrappers
├── types.py                  # Dataclass response models
├── types_responses.py        # Response (Responses API), re-exported from types
├── exceptions/__init__.py    # FerroError hierarchy
├── completions/              # chat.completions (resource.py + async_resource.py)
├── embeddings/               # embeddings
├── images/                   # images.generate
├── models/                   # model catalog (client-side lookup/filter)
├── responses/                # Responses API
├── moderations/              # moderations
└── admin/                    # Admin, _KeysResource, _ConfigResource, _LogsResource,
                              # _ProvidersResource, _PluginsResource, _AuditResource
```

Every resource sub-package has a sync `resource.py` and an `async_resource.py`; the async module imports the request-body builders and path constants from the sync one so the wire format is defined once.

---

## Core Design Decisions

### 1. No pydantic — Plain Dataclasses

All response models are standard `@dataclass` classes with a `from_dict()` classmethod factory. This keeps the dependency tree minimal (only `httpx`) and avoids version conflicts with pydantic v1 vs v2 in user projects.

```python
@dataclass
class ChatCompletion:
    id: str
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    # Gateway extensions
    trace_id: str | None = None            # X-Request-ID header
    provider: str | None = None            # body `provider` / X-Gateway-Provider header
    gateway_overhead_ms: float | None = None  # X-Gateway-Overhead-Ms header
    provider_metadata: dict[str, Any] | None = None
```

### 2. Resource Pattern

Each API surface is a **resource class** that receives the client via `__init__(self, client: FerroClient)` (typed under `TYPE_CHECKING` to avoid an import cycle), calls `self._client._request(method, path, ...)` for HTTP, and returns typed dataclasses (or the raw dict where the gateway's shape is loosely structured — admin lists, rerank, moderations).

```
FerroClient
  ├── _http: httpx.Client                 # connection pool + auth headers
  ├── _request(method, path, ...)         # central HTTP with retry + error mapping
  ├── _open_stream(path, body)            # SSE: no retry, returns the live response
  ├── health() / ready() / live()         # → /health, /readyz, /livez
  ├── capabilities()                      # → /v1/capabilities
  ├── rerank(...)                         # → /v1/rerank
  │
  ├── chat.completions: Completions       # → /v1/chat/completions
  ├── embeddings: Embeddings              # → /v1/embeddings
  ├── images: Images                      # → /v1/images/generations
  ├── models: Models                      # → /v1/models (client-side filter/lookup)
  ├── responses: Responses                # → /v1/responses[/{id}]
  ├── moderations: Moderations            # → /v1/moderations
  └── admin: Admin                        # → /admin/*
        ├── keys / config / logs / providers / plugins / audit
```

### 3. Single HTTP Entry Point

All non-streaming traffic flows through `_request()` (sync) or `AsyncFerroClient._request()`. It centralizes:

- **Authentication** — `Authorization: Bearer {api_key}` header on the `httpx` client.
- **Retry policy** — see below.
- **Error mapping** — `_raise_api_error()` translates the gateway's error envelope into typed exceptions.
- **Response parsing** — JSON, 204 handling, and header metadata injection for inference paths only (`/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/images/generations`, `/v1/responses`, `/v1/rerank`, `/v1/moderations`). Catalog, probe, and admin bodies are returned untouched.
- **Probe semantics** — `/health` and `/readyz` answer `503` with a JSON body when degraded; `_request(..., allow=(503,))` returns that body instead of raising.

### 4. Retry Policy

Shared by sync and async; streaming requests are never retried.

| Trigger | Retried? |
|---|---|
| HTTP `429` | yes, every method (the gateway did not process the request) |
| `httpx.ConnectError`, `httpx.ConnectTimeout` | yes, every method (the request never left) |
| HTTP `408`, `5xx` | idempotent methods only (`GET`, `HEAD`, `PUT`, `DELETE`, `OPTIONS`) |
| other `httpx.TimeoutException` (read / write / pool) | idempotent methods only — a `POST` may already have been processed |
| any other `4xx` | no — raised immediately |
| streaming (`_open_stream`) | never; transport errors map to `FerroConnectionError` |

The decision lives in `_should_retry(method, status=…)` / `_should_retry(method, exc=…)`, shared by both loops.

Delay before retry *n*: `Retry-After` seconds when present (capped at 30 s — the same cap the gateway applies to its own upstream retries), else `uniform(0, min(0.5 · 2^(n-1), 8))` (full jitter). `max_retries` defaults to 2 and is validated at construction.

### 5. Typed Exception Hierarchy

```
FerroError (base)
├── FerroAPIError (any non-2xx HTTP response; .status_code .code .message .request_id)
│   ├── FerroAuthError            (401)
│   ├── FerroBudgetExceededError  (402 insufficient_quota)
│   ├── FerroPermissionError      (403 insufficient_scope)
│   ├── FerroNotFoundError        (404 model_not_found / not_found — also raised locally by models.retrieve)
│   ├── FerroRateLimitError       (429; .retry_after from the Retry-After header)
│   └── FerroServerError          (5xx)
├── FerroConnectionError          (network / timeout after all retries)
└── FerroStreamError              (malformed SSE frame, or a gateway error frame; .code)
```

`.request_id` is the `X-Request-ID` of the failed response (falls back to `request_id` / `trace_id` in the body).

### 6. Streaming

`chat.completions.create(stream=True)` returns a `Stream` (async: `AsyncStream`) rather than a bare generator so the HTTP response — and therefore its headers — stays reachable:

- `stream.trace_id` (`X-Request-ID`) and `stream.provider` (`X-Gateway-Provider`, not set on SSE as of v1.4.5) are available before the first chunk and copied onto every `ChatCompletionChunk`.
- Frames are parsed line-wise: `data: {...}` → `ChatCompletionChunk`; `data: [DONE]` ends the stream; `{"error": {...}}` → `FerroStreamError(code=...)`; anything unparsable → `FerroStreamError("Malformed SSE chunk ...")`.
- `usage` appears on the terminal chunk. The gateway always asks the upstream for usage (for metering) and forwards that chunk unless the client sent `stream_options={"include_usage": False}`.
- The response is closed when the stream is exhausted, on error, on `close()`, or when the `with` block exits.

### 7. Sync + Async Duality

`FerroClient` (`httpx.Client`) and `AsyncFerroClient` (`httpx.AsyncClient`) expose the same namespaces; every resource has an async twin. The async client's `create(stream=True)` is awaited once (opening the stream, so HTTP errors surface there) and returns an `AsyncStream`.

### 8. OpenAI Compatibility Layer

| OpenAI                            | ferrolabsai                                |
| --------------------------------- | ------------------------------------------ |
| `from openai import OpenAI`       | `from ferrolabsai import FerroClient`      |
| `client.chat.completions.create`  | `client.chat.completions.create`           |
| `client.embeddings.create`        | `client.embeddings.create`                 |
| `client.images.generate`          | `client.images.generate`                   |
| `client.models.list / retrieve`   | `client.models.list / retrieve` (client-side) |
| `client.responses.create`         | `client.responses.create`                  |
| `OPENAI_API_KEY`                  | `FERRO_API_KEY` (falls back to `OPENAI_API_KEY`) |

The `_ChatNamespace` class exists solely to provide the `client.chat.completions` accessor, matching OpenAI's nested layout.

---

## Request Lifecycle

```
1. User calls:  client.chat.completions.create(model="gpt-4o", messages=[...])
                   │
2. Completions.create()
   ├── build_body(): model, messages, stream + non-None optionals + **kwargs
   ├── Non-streaming: self._client._request("POST", "/v1/chat/completions", json=body)
   └── Streaming: Stream(self._client._open_stream(path, body))
                   │
3. FerroClient._request()
   ├── Sends via self._http (httpx.Client)
   ├── 2xx: parse JSON; inference path → merge X-Request-ID / X-Gateway-Provider /
   │        X-Gateway-Overhead-Ms into the dict (body fields win)
   ├── 408/429/5xx or connect/timeout: sleep (Retry-After or jittered backoff), retry
   └── Other non-2xx or retries exhausted: _raise_api_error() → typed FerroXxxError
                   │
4. Completions.create() → ChatCompletion.from_dict(data)
                   │
5. User receives ChatCompletion with:
   ├── .content               → shortcut to first choice
   ├── .provider              → which backend answered (body `provider`)
   ├── .trace_id              → X-Request-ID; joins with admin.logs / OTel
   ├── .gateway_overhead_ms   → gateway's own processing time
   ├── .provider_metadata     → provider-specific extras
   └── .usage                 → tokens (+ reasoning / cache counters when reported)
```

---

## Gateway Contract

### Response headers read by the SDK

| Header | Set by the gateway on | SDK field |
|---|---|---|
| `X-Request-ID` | every response (32 lowercase hex, equals the OTel trace id) | `trace_id`, `Stream.trace_id`, chunk `trace_id`, `FerroAPIError.request_id` |
| `X-Gateway-Provider` | `/v1/responses`, `/v1/*` pass-through, legacy `/v1/completions` — **not** non-streaming chat (body `provider` instead), **not** SSE | `provider` (only when the body has none) |
| `X-Gateway-Overhead-Ms` | non-streaming `/v1/chat/completions`, when > 0 | `gateway_overhead_ms` |
| `Retry-After` | every gateway-originated `429` (`"1"`), upstream `429` (upstream value) | retry delay; `FerroRateLimitError.retry_after` |

No Ferro-branded, cost, latency, or cache-hit response header exists at any gateway version; the SDK reads none.

### Body extensions read by the SDK

| Field | Where | SDK field |
|---|---|---|
| `provider`, `provider_metadata` | non-streaming chat completion | `ChatCompletion.provider` / `.provider_metadata` |
| `usage.reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens` | chat usage (omitted when zero) | `Usage.*` |
| `message.reasoning_content`, `delta.reasoning_content` | chat message / stream delta | `ChatMessage.reasoning_content`, `StreamDelta.reasoning_content` |
| `{"error": {message, type, code}}` | every non-2xx and mid-stream error frame | exception `.message` / `.code` |

### Model catalog

`GET /v1/models` returns `EnrichedModelInfo` (`ai-gateway/internal/handler/models.go`): `id`, `object`, `created`, `owned_by`, plus `mode`, `context_window`, `max_output_tokens`, `capabilities[]`, `status`, `deprecated` when the catalog knows the model. Query parameters are ignored and `GET /v1/models/{id}` is not a native route (it would fall through to the `/v1/*` pass-through with the operator's credential), so `list(provider=, capability=)`, `search()`, and `retrieve()` all work client-side over one fetch.

---

## Admin API Surface

The admin namespace maps 1:1 to the gateway's `/admin/*` routes (`ai-gateway/internal/admin/handlers/server.go`, `Handlers.Routes`).

| SDK Method                              | HTTP Route                          | Scope      |
| --------------------------------------- | ----------------------------------- | ---------- |
| `admin.dashboard()`                     | `GET /admin/dashboard`              | read_only  |
| `admin.health()`                        | `GET /admin/health`                 | read_only  |
| `admin.keys.list()`                     | `GET /admin/keys`                   | read_only  |
| `admin.keys.retrieve(id)`               | `GET /admin/keys/{id}`              | read_only  |
| `admin.keys.create(name=...)`           | `POST /admin/keys`                  | admin      |
| `admin.keys.update(id, ...)`            | `PUT /admin/keys/{id}`              | admin      |
| `admin.keys.delete(id)`                 | `DELETE /admin/keys/{id}`           | admin      |
| `admin.keys.revoke(id)`                 | `POST /admin/keys/{id}/revoke`      | admin      |
| `admin.keys.rotate(id)`                 | `POST /admin/keys/{id}/rotate`      | admin      |
| `admin.keys.usage(limit=...)`           | `GET /admin/keys/usage`             | read_only  |
| `admin.config.get()`                    | `GET /admin/config`                 | read_only  |
| `admin.config.create(config)`           | `POST /admin/config`                | admin      |
| `admin.config.update(config)`           | `PUT /admin/config`                 | admin      |
| `admin.config.delete()`                 | `DELETE /admin/config`              | admin      |
| `admin.config.history()`                | `GET /admin/config/history`         | read_only  |
| `admin.config.rollback(version)`        | `POST /admin/config/rollback/{v}`   | admin      |
| `admin.logs.list(stage=, api_key_id=, ...)` | `GET /admin/logs`               | read_only  |
| `admin.logs.stats(buckets=)`            | `GET /admin/logs/stats`             | read_only  |
| `admin.logs.delete(before=...)`         | `DELETE /admin/logs`                | admin      |
| `admin.providers.list()`                | `GET /admin/providers`              | read_only  |
| `admin.providers.catalog()`             | `GET /admin/providers/catalog`      | read_only  |
| `admin.plugins.list()`                  | `GET /admin/plugins`                | read_only  |
| `admin.plugins.catalog()`               | `GET /admin/plugins/catalog`        | read_only  |
| `admin.audit.list(action=, actor_id=, outcome=, since=)` | `GET /admin/audit` | read_only |

Not wrapped on purpose: `/admin/session(s)` (dashboard-only), `/metrics`, `/debug/vars`. Gateway rules worth knowing: the last admin key record cannot be revoked or deleted (`409`), `read_only` writes get `403 insufficient_scope`, and `GET /admin/config` masks secrets so it does not round-trip into `PUT`.

---

## Error Handling Flow

```
HTTP response received
  │
  ├── 2xx → parse JSON → return dict / dataclass
  ├── 503 on /health, /readyz → return the JSON body (degraded is an answer)
  │
  ├── 408 / 429 / 5xx → retry (Retry-After or jittered backoff) … then map as below
  │
  ├── 401 → FerroAuthError
  ├── 402 → FerroBudgetExceededError
  ├── 403 → FerroPermissionError
  ├── 404 → FerroNotFoundError
  ├── 429 → FerroRateLimitError(retry_after=...)
  ├── 5xx → FerroServerError
  ├── other 4xx (400, 405, 409, 413, 501, …) → FerroAPIError(code=...)
  │
  ├── ConnectError / TimeoutException → retry up to max_retries → FerroConnectionError
  └── SSE: HTTP error before the first byte → same mapping; error frame → FerroStreamError
```

---

## Configuration & Auth

```python
FerroClient(
    api_key="...",            # or FERRO_API_KEY / OPENAI_API_KEY env var
    base_url="...",           # or FERRO_BASE_URL env var (default: http://localhost:8080)
    timeout=120.0,            # httpx timeout in seconds
    max_retries=2,            # retries for connect/timeout/408/429/5xx (default: 2)
    default_headers={...},    # merged into every request
    http_client=my_httpx,     # bring your own httpx.Client
)
```

Auth resolution order: `api_key` parameter → `FERRO_API_KEY` → `OPENAI_API_KEY` (migration fallback). If none is found, `FerroAuthError` is raised at construction time.

---

## Dependency Graph

```
ferrolabsai (this SDK)
  └── httpx ≥ 0.24.0    # the ONLY runtime dependency

Dev only:
  ├── pytest ≥ 7.0
  ├── pytest-asyncio ≥ 0.21
  ├── pytest-httpx ≥ 0.22
  ├── mypy ≥ 1.0
  └── ruff ≥ 0.1.0
```

---

## Testing Strategy

- **Unit** (`tests/test_client.py`, `test_chat.py`, `test_resources.py`, `test_admin.py`): HTTP fully mocked via `pytest-httpx`; covers construction, auth resolution, error mapping, the retry policy, header metadata, streaming (happy path, usage chunk, error frames), every resource and admin route, sync and async.
- **Contract** (`tests/contract/`): runs only when `FERRO_CONTRACT_BASE_URL` is set. `scripts/with-gateway.sh` builds `ferrogw` from an ai-gateway checkout, starts `tests/contract/stub_upstream.py` as a fake OpenAI, points the gateway at it, and asserts the header/body/error contract described above against the real server. CI runs it against the pinned gateway tag (required) and `main` (advisory).
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
