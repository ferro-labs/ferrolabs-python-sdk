<div align="center">
  <table border="0" cellspacing="0" cellpadding="0"><tr>
    <td rowspan="2"><img src="https://raw.githubusercontent.com/ferro-labs/ai-gateway/refs/heads/main/docs/logo.png" alt="Ferro Labs" width="64" /></td>
    <td align="center"><h1>Ferro Labs - AI Gateway</h1></td>
  </tr><tr>
    <td align="center"><strong>Python SDK</strong></td>
  </tr></table>
  <p>
    <a href="https://pypi.org/project/ferrolabsai/"><img src="https://badge.fury.io/py/ferrolabsai.svg" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/ferrolabsai/"><img src="https://img.shields.io/pypi/pyversions/ferrolabsai.svg" alt="Python versions" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>
    <a href="https://github.com/ferro-labs/ferrolabs-python-sdk/actions/workflows/ci.yml"><img src="https://github.com/ferro-labs/ferrolabs-python-sdk/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  </p>
</div>

Route LLM requests across **30 providers and 2,500+ models** through a single OpenAI-compatible API.
Zero code changes to migrate from `openai`. Built on [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway).

```python
from ferrolabsai import FerroClient

client = FerroClient(api_key="fgw_...")

# Route to OpenAI
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)

# Route to Anthropic — same client, same call
response = client.chat.completions.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Hello"}],
)

print(response.content)
print(f"Handled by {response.provider}, trace {response.trace_id}")
```

**Compatibility:** `ferrolabsai 0.3.x` ↔ `ai-gateway ≥ v1.4.0`. Every claim in this README is executed against a real `ai-gateway v1.4.5` by the [contract suite](#contract-tests) on each CI run.

---

## Why ferrolabsai

- **One API for 30 providers.** OpenAI, Anthropic, Google, Groq, Together, Mistral, Cohere, Bedrock, Vertex, Azure, and more — all via a single client.
- **Drop-in OpenAI replacement.** The surface matches the OpenAI SDK. Change two lines and keep all your existing code.
- **Smart routing built in.** Fallback chains, weighted load balancing, conditional and cost-optimized routing — configured on the gateway, invisible to callers.
- **Provider and trace visibility.** Every inference response carries `provider` and `trace_id` (the gateway's `X-Request-ID`) — no extra calls.
- **Self-hostable.** Point `base_url` at any [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) instance and go.
- **Typed and async-first.** Dataclass response models, full `AsyncFerroClient`, streaming in both modes, zero dependencies beyond `httpx`.

---

## Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Migrate from OpenAI](#migrate-from-openai)
- [Framework adapters](#framework-adapters)
- [Usage](#usage)
  - [Chat completions](#chat-completions)
  - [Streaming](#streaming)
  - [Async](#async)
  - [Embeddings](#embeddings)
  - [Image generation](#image-generation)
  - [Model catalog](#model-catalog)
  - [Responses API, rerank, moderations](#responses-api-rerank-moderations)
  - [Gateway probes and capabilities](#gateway-probes-and-capabilities)
- [Observability](#observability)
- [Configuration](#configuration)
- [Error handling](#error-handling)
- [Admin API (OSS gateway)](#admin-api-oss-gateway)
- [Development](#development)
- [License](#license)

---

## Installation

```bash
pip install ferrolabsai
```

Requires **Python 3.9+**. The only runtime dependency is [`httpx`](https://www.python-httpx.org/).

---

## Quickstart

You'll need a running [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) instance and an API key issued by it (`fgw_...`, or the gateway's `MASTER_KEY`).

```python
from ferrolabsai import FerroClient

client = FerroClient(
    api_key="fgw_your-key",
    base_url="http://localhost:8080",  # your gateway address
)
```

### Environment variables

```bash
export FERRO_API_KEY="fgw_your-key"
export FERRO_BASE_URL="http://localhost:8080"
```

```python
client = FerroClient()  # reads FERRO_API_KEY / FERRO_BASE_URL automatically
```

`FERRO_API_KEY` takes precedence, but `OPENAI_API_KEY` is also accepted as a fallback to make migration painless.

---

## Migrate from OpenAI

```python
# Before
from openai import OpenAI
client = OpenAI(api_key="sk-openai-...")

# After — all your existing code works unchanged
from ferrolabsai import FerroClient
client = FerroClient(api_key="fgw_...")
```

Every `client.chat.completions.create(...)` call, every streaming loop, every tool call — identical API surface. Ferro routes to the right provider based on the model name.

---

## Framework adapters

The gateway exposes an OpenAI-compatible HTTP API at `/v1/*`, so `langchain_openai`, `llama_index.llms.openai`, and the Vercel AI SDK all work by pointing their base URL at your gateway. The first-party adapters go further and surface the gateway's `trace_id` / `provider` and typed errors:

| Package | What it wraps | Status |
|---|---|---|
| [`langchain-ferrolabsai`](integrations/langchain-ferrolabsai/) | `FerroChatModel` (sync/async, streaming, tools, `with_structured_output`), `FerroEmbeddings`, `FerroLLM` | **0.2.0** — on ferrolabsai 0.3 |
| [`llama-index-llms-ferrolabsai`](integrations/llama-index-llms-ferrolabsai/) | LlamaIndex `LLM` | placeholder (0.0.1) |

```python
from langchain_ferrolabsai import FerroChatModel

llm = FerroChatModel(model="gpt-4o", base_url="http://localhost:8080", api_key="fgw_...")
print(llm.invoke("Hello").response_metadata["trace_id"])
```

See [`integrations/README.md`](integrations/README.md) for layout and publishing.

---

## Usage

### Chat completions

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain LLM routing in one paragraph."},
    ],
    temperature=0.7,
    max_completion_tokens=256,          # supersedes max_tokens; both accepted
    response_format={"type": "json_object"},
    seed=42,
)
print(response.content)                # shortcut for choices[0].message.content
print(response.provider)               # which backend handled it
print(response.usage.total_tokens)
print(response.provider_metadata)      # provider-specific extras, when present
```

`tools`, `tool_choice`, `parallel_tool_calls`, `stop`, `top_p`, `frequency_penalty`, `presence_penalty`, `user` are first-class; any other OpenAI parameter passes through as `**kwargs`.

### Streaming

```python
stream = client.chat.completions.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Write a haiku about Go performance."}],
    stream=True,
    stream_options={"include_usage": True},   # terminal chunk carries usage
)
print(stream.trace_id)                        # available before the first chunk
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="", flush=True)
    if chunk.usage:                            # last chunk only
        print(f"\n{chunk.usage.total_tokens} tokens")
```

The return value is a `Stream` (an iterator that also exposes `trace_id`, `provider`, and the underlying `response`; use `with` or `close()` to release the connection early). Every chunk carries `trace_id` too. Note that ai-gateway forwards the terminal usage chunk unless you send `stream_options={"include_usage": False}`. A mid-stream gateway error frame raises `FerroStreamError` with `.code` (`stream_error`, `stream_timeout`).

### Async

```python
import asyncio
from ferrolabsai import AsyncFerroClient

async def main():
    async with AsyncFerroClient(api_key="fgw_...") as client:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(response.content)

asyncio.run(main())
```

Async streaming:

```python
async def stream_example():
    async with AsyncFerroClient(api_key="fgw_...") as client:
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Count to 5"}],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices:
                print(chunk.choices[0].delta.content or "", end="", flush=True)
```

### Embeddings

```python
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=["Ferro routes LLM requests", "across 30 providers"],
)
vectors = [d.embedding for d in response.data]
print(f"Embedding dimensions: {len(vectors[0])}")
```

### Image generation

```python
response = client.images.generate(
    model="dall-e-3",
    prompt="A futuristic AI gateway routing data streams across glowing servers",
    size="1024x1024",
    quality="hd",
)
print(response.data[0].url)
```

### Model catalog

`GET /v1/models` returns the gateway's enriched catalog (`ModelInfo`: `id`, `owned_by`, `mode`, `context_window`, `max_output_tokens`, `capabilities`, `status`, `deprecated`). The gateway ignores query parameters and has no `/v1/models/{id}` route, so filtering and lookup are done client-side over one fetch.

```python
models = client.models.list()
anthropic_models = client.models.list(provider="anthropic")     # matches owned_by
vision_models = client.models.list(capability="vision")          # matches capabilities[]
claude = client.models.search("claude")                          # substring on id

info = client.models.retrieve("gpt-4o")   # raises FerroNotFoundError locally if unknown
print(f"{info.provider}: {info.context_window:,} tokens, {info.capabilities}")
```

### Responses API, rerank, moderations

```python
# OpenAI-style Responses API (model-routed; governed and priced like chat)
r = client.responses.create(model="gpt-4o", input="Summarise the gateway in one line")
print(r.status, r.output, r.trace_id)
# retrieve/delete pin to the gateway's `responses_target`; 501 unless configured
client.responses.retrieve(r.id)

# Cohere-shape rerank and OpenAI-shape moderations return the provider JSON
client.rerank(model="rerank-v3.5", query="gateway", documents=["a", "b"], top_n=1)
client.moderations.create(input="some text")
```

### Gateway probes and capabilities

```python
client.live()           # {"status": "ok"}
client.ready()          # {"status": "ready", "providers": [...], "targets": [...]} (503 body returned, not raised)
client.health()         # {"status", "version", "commit", "built", "providers"}
client.capabilities()   # per-provider parameter support: forward | translate | unsupported
```

---

## Observability

Every inference response (`chat`, `embeddings`, `images`, `responses`, `rerank`, `moderations`) gets the gateway's response headers merged in. This is exactly what ai-gateway v1.4.x provides — nothing else is invented:

| Field | Type | Source | Populated on |
|---|---|---|---|
| `response.trace_id` | `str` | `X-Request-ID` header (32 hex chars; equals the OTel trace id) | every response, `Stream.trace_id`, every chunk, every `FerroAPIError.request_id` |
| `response.provider` | `str` | body `provider` on chat completions; `X-Gateway-Provider` header on responses/pass-through | non-streaming chat, responses (not on SSE streams as of v1.4.5) |
| `response.gateway_overhead_ms` | `float` | `X-Gateway-Overhead-Ms` header — the gateway's own processing time, **not** end-to-end latency | non-streaming chat completions |
| `response.provider_metadata` | `dict` | body `provider_metadata` | when the provider returns extras |
| `response.usage.prompt_tokens` / `completion_tokens` / `total_tokens` | `int` | body `usage` | chat, embeddings, terminal streaming chunk |
| `response.usage.reasoning_tokens` / `cache_read_tokens` / `cache_write_tokens` | `int \| None` | body `usage` (omitted when zero) | when the provider reports them |

```python
response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hello"}])
print(f"trace={response.trace_id} provider={response.provider} overhead={response.gateway_overhead_ms}ms")
```

Cost and cache hits are not exposed to callers — they live in the gateway's request log (`client.admin.logs.list(model=...)` joins on `trace_id`), Prometheus, and OTel spans.

---

## Configuration

`FerroClient` and `AsyncFerroClient` accept the same keyword arguments:

```python
client = FerroClient(
    api_key="fgw_...",                       # or FERRO_API_KEY env var
    base_url="http://localhost:8080",        # or FERRO_BASE_URL env var
    timeout=120.0,                           # seconds (default: 120.0)
    max_retries=2,                           # default: 2
    default_headers={"x-env": "prod"},       # merged into every request
    http_client=my_httpx_client,             # bring your own httpx.Client
)
```

**Retries** cover connection errors, timeouts, and HTTP `408` / `429` / `5xx` — capped exponential backoff with full jitter (0.5 s base, 8 s cap), honouring `Retry-After` when the gateway sends one (capped at 30 s, the same cap the gateway applies upstream). Other `4xx` responses and **streaming requests are never retried**.

**Bring-your-own httpx client** lets you configure proxies, custom TLS, connection pool limits, or instrumentation middleware and reuse that across the SDK:

```python
import httpx

pooled = httpx.Client(limits=httpx.Limits(max_connections=50))
client = FerroClient(api_key="fgw_...", http_client=pooled)
```

Close the client explicitly when you're done (or use a `with` block):

```python
with FerroClient(api_key="fgw_...") as client:
    ...
```

---

## Error handling

```python
from ferrolabsai import (
    FerroClient,
    FerroAuthError,
    FerroBudgetExceededError,
    FerroPermissionError,
    FerroRateLimitError,
    FerroNotFoundError,
    FerroServerError,
    FerroConnectionError,
)

try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
except FerroAuthError:                    # 401
    print("Invalid API key — check FERRO_API_KEY")
except FerroBudgetExceededError:          # 402 insufficient_quota
    print("Spend limit reached for this key")
except FerroPermissionError:              # 403 insufficient_scope
    print("This key lacks the scope for that route")
except FerroRateLimitError as e:          # 429 (already retried)
    print(f"Rate limited — retry after {e.retry_after}s")
except FerroNotFoundError as e:           # 404 model_not_found / not_found
    print(f"Not found: {e.code}")
except FerroServerError as e:             # 5xx (already retried)
    print(f"Gateway error {e.status_code} ({e.code}) — trace {e.request_id}")
except FerroConnectionError:
    print("Cannot reach gateway — is it running?")
```

All HTTP-level exceptions inherit from `FerroAPIError` and expose `.status_code`, `.code` (the gateway's error code, e.g. `model_not_found`, `insufficient_scope`), `.message`, and `.request_id`. `FerroConnectionError` and `FerroStreamError` inherit from `FerroError` directly.

---

## Admin API (OSS gateway)

These APIs are available on any self-hosted Ferro Labs AI Gateway instance. Reads need a `read_only` or `admin` key; writes need `admin` (a `read_only` key gets `FerroPermissionError`).

The admin namespace mirrors the OSS gateway's `/admin/*` HTTP surface defined in the [`internal/admin/handlers`](https://github.com/ferro-labs/ai-gateway/tree/main/internal/admin/handlers) package.

### API keys

```python
# Create
new_key = client.admin.keys.create(
    name="backend-service",
    scopes=["admin"],                 # or ["read_only"]
)
print(new_key.key)  # full key value — shown ONCE, store it securely

# List / retrieve (key values are masked: fgw_ab12...cd34)
keys = client.admin.keys.list()
key = client.admin.keys.retrieve("key_id")

# Update metadata
client.admin.keys.update("key_id", name="renamed", active=False)

# Per-key usage counts (sorted by usage by default)
usage = client.admin.keys.usage(limit=20)

# Revoke — keeps the record for audit, invalidates the key immediately
client.admin.keys.revoke("key_id")

# Rotate — atomically invalidates old, returns new
rotated = client.admin.keys.rotate("key_id")

# Permanently delete the record (the gateway refuses to delete the last admin key)
client.admin.keys.delete("key_id")
```

### Gateway routing config

The OSS gateway has a single *active* routing config. Use `history()` to inspect prior versions and `rollback(version)` to revert. Updates are zero-downtime hot reloads.

```python
cfg = client.admin.config.get()
print(cfg.strategy)  # e.g. {"mode": "fallback"}
print(cfg.targets)   # list of {virtual_key, weight, ...}

client.admin.config.update({
    "strategy": {"mode": "fallback"},
    "targets": [
        {"virtual_key": "openai",    "weight": 1},
        {"virtual_key": "anthropic", "weight": 1},
    ],
})

history = client.admin.config.history()
client.admin.config.rollback(history[-2].version)
```

Note: `get()` masks secrets and redacts free-form map keys, so its body does not round-trip unchanged into `update()`; unknown keys are rejected with `400`.

### Request logs

The gateway records every request when a request-log store is configured (`REQUEST_LOG_STORE_BACKEND=sqlite|postgres`); the endpoints answer `501` without one.

```python
# Recent entries for a model (one row per request; stage="all" shows every lifecycle stage)
entries = client.admin.logs.list(limit=20, model="gpt-4o")
for entry in entries["data"]:
    print(entry["trace_id"], entry["provider"], entry["duration_ms"], entry["cost_usd"])

# Filter by the calling key
client.admin.logs.list(api_key_id="key_id")

# Aggregate stats with a 24-point time series
stats = client.admin.logs.stats(buckets=24)

# Prune old entries
client.admin.logs.delete(before="2026-01-01T00:00:00Z")
```

### Providers, plugins, audit, dashboard

```python
providers = client.admin.providers.list()      # registered providers and their models
catalog   = client.admin.providers.catalog()   # every provider the build knows: {id, registered, catalog_models}
plugins   = client.admin.plugins.list()        # configured plugins
available = client.admin.plugins.catalog()     # built-in plugins available to configure
audit     = client.admin.audit.list(action="key.create", limit=50)   # admin audit trail
dashboard = client.admin.dashboard()           # high-level counts
health    = client.admin.health()              # gateway health check (admin view)
```

---

## Development

```bash
git clone https://github.com/ferro-labs/ferrolabs-python-sdk
cd ferrolabs-python-sdk
make install          # editable install with dev dependencies
make test             # pytest (all HTTP is mocked — no gateway needed)
make lint             # ruff + mypy
make format           # ruff format
make build            # build sdist + wheel into dist/
make contract         # boot a real gateway from ../ai-gateway and run tests/contract
```

The 113 unit tests run in a few seconds against `pytest-httpx` fixtures, so no network or running gateway is required.

### Contract tests

`tests/contract/` is skipped unless `FERRO_CONTRACT_BASE_URL` is set. `scripts/with-gateway.sh` builds `ferrogw` from an [ai-gateway](https://github.com/ferro-labs/ai-gateway) checkout (`FERRO_GATEWAY_SOURCE`, default `../ai-gateway`), points it at a stdlib stub upstream (`tests/contract/stub_upstream.py`), and runs the 23 contract tests: probes, catalog, chat, streaming, embeddings, responses, the error envelope (401/403/404/501), and every admin route the SDK wraps. CI runs it against the pinned `v1.4.5` (required) and `main` (advisory).

See [CHANGELOG.md](CHANGELOG.md) for release history and [docs/architecture.md](docs/architecture.md) for the design.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Links

- [Ferro Labs AI Gateway (OSS)](https://github.com/ferro-labs/ai-gateway)
- [Issue tracker](https://github.com/ferro-labs/ferrolabs-python-sdk/issues)
- [Changelog](CHANGELOG.md)
