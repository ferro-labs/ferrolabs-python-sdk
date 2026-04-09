# Architecture — ferrolabsai Python SDK

This document describes the internal architecture of the `ferrolabsai` SDK, how the pieces fit together, and the design decisions behind them.

---

## High-Level Overview

The SDK acts as a thin HTTP client that sits between application code and a running [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) instance. It provides an OpenAI-compatible surface so users can switch from `openai.OpenAI` to `ferrolabsai.FerroClient` with minimal code changes, while gaining access to 29+ LLM providers, smart routing, and gateway management APIs.

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Code                         │
│                                                             │
│  client.chat.completions.create(model="gpt-4o", ...)       │
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
              │    └── admin                │
              │         ├── keys            │
              │         ├── config          │
              │         ├── logs            │
              │         ├── providers       │
              │         └── plugins         │
              └────────────┬────────────────┘
                           │  HTTP (httpx)
              ┌────────────▼────────────────┐
              │   Ferro Labs AI Gateway     │
              │       /v1/*  /admin/*       │
              │                             │
              │  Routing · Fallback · Cache │
              │  Rate limiting · Logging    │
              └────────────┬────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐    ┌────▼─────┐   ┌────▼────┐
      │ OpenAI  │    │Anthropic │   │  Groq   │  ... 29+ providers
      └─────────┘    └──────────┘   └─────────┘
```

---

## Module Map

```
ferrolabsai/
├── __init__.py               # Public API surface & __all__
├── client.py                 # FerroClient, AsyncFerroClient, _raise_api_error
├── types.py                  # All dataclass response models
├── exceptions/
│   └── __init__.py           # FerroError hierarchy
├── completions/
│   ├── resource.py           # Completions (sync + streaming)
│   └── async_resource.py     # AsyncCompletions (async + streaming)
├── embeddings/
│   ├── resource.py           # Embeddings (sync)
│   └── async_resource.py     # AsyncEmbeddings
├── images/
│   └── resource.py           # Images (sync)
├── models/
│   └── resource.py           # Models catalog (sync)
└── admin/
    └── resource.py           # Admin, _KeysResource, _ConfigResource,
                              # _LogsResource, _ProvidersResource, _PluginsResource
```

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
    # Ferro extras
    trace_id: str | None = None
    provider: str | None = None
    latency_ms: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatCompletion:
        ...
```

### 2. Resource Pattern

Each API surface (completions, embeddings, images, models, admin) is a **resource class** that:

1. Receives the client instance via `__init__(self, client)`.
2. Calls `self._client._request(method, path, ...)` for all HTTP traffic.
3. Returns typed dataclass models.

This mirrors the OpenAI SDK's structure (`client.chat.completions`, `client.embeddings`, etc.) and keeps individual files focused and small.

```
FerroClient
  ├── _http: httpx.Client               # connection pool + auth headers
  ├── _request(method, path, ...)        # central HTTP with retry logic
  │
  ├── chat: _ChatNamespace
  │     └── completions: Completions     # → /v1/chat/completions
  ├── embeddings: Embeddings             # → /v1/embeddings
  ├── images: Images                     # → /v1/images/generations
  ├── models: Models                     # → /v1/models
  └── admin: Admin                       # → /admin/*
        ├── keys: _KeysResource          # → /admin/keys
        ├── config: _ConfigResource      # → /admin/config
        ├── logs: _LogsResource          # → /admin/logs
        ├── providers: _ProvidersResource # → /admin/providers
        └── plugins: _PluginsResource    # → /admin/plugins
```

### 3. Single HTTP Entry Point

All HTTP traffic flows through `FerroClient._request()` (sync) or `AsyncFerroClient._request()` (async). This centralizes:

- **Authentication** — `Authorization: Bearer {api_key}` header injected by `httpx.Client`.
- **Retry logic** — retries on `httpx.ConnectError` and `httpx.TimeoutException` only (not HTTP errors).
- **Error mapping** — `_raise_api_error()` translates HTTP status codes into typed exceptions.
- **Response parsing** — JSON deserialization, 204 handling.

Streaming is the exception: `_stream_request()` returns an iterator of raw SSE lines, and the resource class handles SSE parsing (`data: ...` / `[DONE]`).

### 4. Typed Exception Hierarchy

```
FerroError (base)
├── FerroAPIError (any non-2xx HTTP response)
│   ├── FerroAuthError        (401)
│   ├── FerroRateLimitError   (429)
│   ├── FerroNotFoundError    (404)
│   └── FerroServerError      (5xx)
├── FerroConnectionError      (network / timeout — retried first)
└── FerroStreamError          (SSE parse failure)
```

`FerroAPIError` carries `.status_code`, `.code`, `.message`, and `.request_id`. Connection and stream errors inherit from `FerroError` directly since they have no HTTP status.

### 5. Sync + Async Duality

The SDK provides both `FerroClient` (synchronous, `httpx.Client`) and `AsyncFerroClient` (asynchronous, `httpx.AsyncClient`).

- Sync resources live in `resource.py` within each sub-package.
- Async resources live in `async_resource.py`.
- Resources that don't yet have an async variant (images, models, admin) only have `resource.py`.

The async client currently supports completions and embeddings. Other resources can be added following the same pattern.

### 6. OpenAI Compatibility Layer

The SDK intentionally mirrors OpenAI SDK ergonomics:

| OpenAI                            | ferrolabsai                                |
| --------------------------------- | ------------------------------------------ |
| `from openai import OpenAI`       | `from ferrolabsai import FerroClient`      |
| `client.chat.completions.create`  | `client.chat.completions.create`           |
| `client.embeddings.create`        | `client.embeddings.create`                 |
| `client.images.generate`          | `client.images.generate`                   |
| `OPENAI_API_KEY`                  | `FERRO_API_KEY` (falls back to `OPENAI_API_KEY`) |

The `_ChatNamespace` class exists solely to provide the `client.chat.completions` accessor, matching OpenAI's nested layout.

---

## Request Lifecycle

```
1. User calls:  client.chat.completions.create(model="gpt-4o", messages=[...])
                   │
2. Completions.create()
   ├── Builds request body (model, messages, temperature, Ferro extras...)
   ├── Non-streaming: calls self._client._request("POST", "/v1/chat/completions", json=body)
   └── Streaming: calls self._client._stream_request(path, body) → yields SSE lines
                   │
3. FerroClient._request()
   ├── Builds httpx.Request with auth headers
   ├── Sends via self._http (httpx.Client)
   ├── On success: returns parsed JSON dict
   ├── On HTTP error: _raise_api_error() → typed FerroXxxError
   └── On connection/timeout error: retries up to max_retries, then FerroConnectionError
                   │
4. Completions.create() (continued)
   ├── Non-streaming: ChatCompletion.from_dict(data) → typed dataclass
   └── Streaming: parses "data: {json}" lines → yields ChatCompletionChunk
                   │
5. User receives ChatCompletion with:
   ├── .content              → shortcut to first choice
   ├── .provider             → which backend handled it (Ferro extra)
   ├── .trace_id             → correlation ID for gateway logs
   ├── .latency_ms           → end-to-end gateway latency
   └── .usage.cost_usd       → computed cost in USD
```

---

## Streaming Architecture

The SDK supports server-sent events (SSE) for real-time token streaming.

### Sync Streaming
```python
for chunk in client.chat.completions.create(model="gpt-4o", messages=[...], stream=True):
    print(chunk.choices[0].delta.content, end="")
```

Internally:
1. `Completions.create(stream=True)` calls `self._stream()`.
2. `_stream()` calls `FerroClient._stream_request()` which opens a streaming `httpx` response.
3. Lines are iterated via `response.iter_lines()`.
4. Each `data: {...}` line is parsed into a `ChatCompletionChunk` and yielded.
5. `data: [DONE]` terminates the iterator.

### Async Streaming
```python
async for chunk in await client.chat.completions.create(model="gpt-4o", messages=[...], stream=True):
    print(chunk.choices[0].delta.content, end="")
```

Uses `response.aiter_lines()` within an `async with self._client._http.stream(...)` context.

---

## Admin API Surface

The admin namespace exposes gateway management operations that map 1:1 to the OSS gateway's `/admin/*` HTTP routes (defined in `ai-gateway/internal/admin/handlers.go`).

| SDK Method                              | HTTP Route                          | Scope      |
| --------------------------------------- | ----------------------------------- | ---------- |
| `admin.dashboard()`                     | `GET /admin/dashboard`              | read-only  |
| `admin.health()`                        | `GET /admin/health`                 | read-only  |
| `admin.keys.list()`                     | `GET /admin/keys`                   | read-only  |
| `admin.keys.retrieve(id)`              | `GET /admin/keys/{id}`              | read-only  |
| `admin.keys.create(name=...)`          | `POST /admin/keys`                  | admin      |
| `admin.keys.update(id, ...)`           | `PUT /admin/keys/{id}`              | admin      |
| `admin.keys.delete(id)`                | `DELETE /admin/keys/{id}`           | admin      |
| `admin.keys.revoke(id)`                | `POST /admin/keys/{id}/revoke`      | admin      |
| `admin.keys.rotate(id)`                | `POST /admin/keys/{id}/rotate`      | admin      |
| `admin.keys.usage(limit=...)`          | `GET /admin/keys/usage`             | read-only  |
| `admin.config.get()`                    | `GET /admin/config`                 | read-only  |
| `admin.config.create(config)`          | `POST /admin/config`                | admin      |
| `admin.config.update(config)`          | `PUT /admin/config`                 | admin      |
| `admin.config.delete()`                | `DELETE /admin/config`              | admin      |
| `admin.config.history()`               | `GET /admin/config/history`         | read-only  |
| `admin.config.rollback(version)`       | `POST /admin/config/rollback/{v}`   | admin      |
| `admin.logs.list(limit=...)`           | `GET /admin/logs`                   | read-only  |
| `admin.logs.stats()`                    | `GET /admin/logs/stats`             | read-only  |
| `admin.logs.delete(before=...)`         | `DELETE /admin/logs`                | admin      |
| `admin.providers.list()`               | `GET /admin/providers`              | read-only  |
| `admin.plugins.list()`                  | `GET /admin/plugins`                | read-only  |

---

## Ferro-Specific Extensions

The SDK passes through fields that the standard OpenAI API doesn't know about. These are safe — any OpenAI-compatible backend that doesn't recognize them silently ignores them.

### Request Extensions (on `chat.completions.create`)

| Parameter            | Wire Field            | Purpose                                                            |
| -------------------- | --------------------- | ------------------------------------------------------------------ |
| `template_id`        | `template_id`         | Render a server-side prompt template (Go `text/template` syntax)   |
| `template_variables` | `template_variables`  | Variables injected into the template                               |
| `route_tag`          | `x_route_tag`         | Override the routing strategy for this single request              |

### Response Extensions (on `ChatCompletion`)

| Field         | Source                                      | Purpose                              |
| ------------- | ------------------------------------------- | ------------------------------------ |
| `trace_id`    | `x_ferro_trace_id` or `trace_id` in body    | Correlates with gateway logs         |
| `provider`    | `x_ferro_provider` or `provider` in body    | Which upstream served the request    |
| `latency_ms`  | `x_ferro_latency_ms` in body                | End-to-end gateway latency           |
| `cost_usd`    | `usage.cost_usd` in body                    | Computed cost in USD                 |
| `cache_hit`   | `usage.cache_hit` in body                   | Whether semantic cache was used      |

---

## Error Handling Flow

```
HTTP response received
  │
  ├── 2xx → parse JSON → return dict / dataclass
  │
  ├── 401 → FerroAuthError
  ├── 404 → FerroNotFoundError
  ├── 429 → FerroRateLimitError
  ├── 5xx → FerroServerError
  ├── other 4xx → FerroAPIError
  │
  ├── ConnectError → retry up to max_retries → FerroConnectionError
  └── TimeoutException → retry up to max_retries → FerroConnectionError
```

HTTP errors (4xx/5xx) are **never retried** — they propagate immediately so the caller can handle them. Only connection and timeout errors trigger the retry loop.

---

## Configuration & Auth

```python
FerroClient(
    api_key="...",            # or FERRO_API_KEY / OPENAI_API_KEY env var
    base_url="...",           # or FERRO_BASE_URL env var (default: http://localhost:8080)
    timeout=120.0,            # httpx timeout in seconds
    max_retries=2,            # connection error retries (default: 2)
    default_headers={...},    # merged into every request
    http_client=my_httpx,     # bring your own httpx.Client
)
```

Auth resolution order:
1. `api_key` parameter
2. `FERRO_API_KEY` environment variable
3. `OPENAI_API_KEY` environment variable (migration fallback)

If none is found, `FerroAuthError` is raised at construction time.

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

The SDK intentionally keeps zero additional runtime dependencies to minimize install footprint and avoid version conflicts in user projects.

---

## Testing Strategy

- All tests live in `tests/test_sdk.py`.
- HTTP is fully mocked via `pytest-httpx` — no network access, no running gateway.
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- Tests cover: client construction, auth resolution, error mapping, retries, response parsing, streaming, admin CRUD, and resource wiring.
