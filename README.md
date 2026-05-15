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

Route LLM requests across **29 providers and 2,500+ models** through a single OpenAI-compatible API.
Zero code changes to migrate from `openai`. Built on [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway).

```python
from ferrolabsai import FerroClient

client = FerroClient(api_key="sk-ferro-...")

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
print(f"Handled by: {response.provider} in {response.latency_ms}ms")
```

---

## Why ferrolabsai

- **One API for 29 providers.** OpenAI, Anthropic, Google, Groq, Together, Mistral, Cohere, Bedrock, Vertex, Azure, and more — all via a single client.
- **Drop-in OpenAI replacement.** The surface matches the OpenAI SDK. Change two lines and keep all your existing code.
- **Smart routing built in.** Fallback chains, weighted load balancing, and per-request overrides via `route_tag`.
- **Cost and provider visibility.** Every response includes `provider`, `cost_usd`, `latency_ms`, and `trace_id` — no extra calls.
- **Self-hostable.** Point `base_url` at any [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) instance and go.
- **Typed and async-first.** Dataclass response models, full `AsyncFerroClient`, streaming in both modes.

---

## Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Migrate from OpenAI](#migrate-from-openai)
- [Framework integrations](#framework-integrations)
- [Usage](#usage)
  - [Chat completions](#chat-completions)
  - [Streaming](#streaming)
  - [Async](#async)
  - [Embeddings](#embeddings)
  - [Image generation](#image-generation)
  - [Model catalog](#model-catalog)
  - [Ferro extras: templates & route tags](#ferro-extras-templates--route-tags)
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

You'll need a running [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) instance and an API key issued by it.

```python
from ferrolabsai import FerroClient

client = FerroClient(
    api_key="sk-ferro-your-key",
    base_url="http://localhost:8080",  # your gateway address
)
```

### Environment variables

```bash
export FERRO_API_KEY="sk-ferro-your-key"
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
client = FerroClient(api_key="sk-ferro-...")
```

Every `client.chat.completions.create(...)` call, every streaming loop, every tool call — identical API surface. Ferro routes to the right provider based on the model name.

---

## Framework integrations

Ferro's gateway exposes an OpenAI-compatible HTTP API at `/v1/*`, so anything that speaks OpenAI works. Point the base URL at your gateway and keep your existing framework.

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    api_key="sk-ferro-your-key",
    base_url="http://localhost:8080/v1",
    model="gpt-4o",
)
response = llm.invoke("Hello from LangChain via Ferro")
```

### LlamaIndex

```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    api_key="sk-ferro-your-key",
    api_base="http://localhost:8080/v1",
    model="gpt-4o",
)
```

### Vercel AI SDK (Next.js)

```typescript
import { createOpenAI } from '@ai-sdk/openai';

const ferro = createOpenAI({
  apiKey: process.env.FERRO_API_KEY,
  baseURL: 'http://localhost:8080/v1',
});
```

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
    max_tokens=256,
)
print(response.content)                       # shortcut for choices[0].message.content
print(f"Cost: ${response.usage.cost_usd:.6f}")
print(f"Provider: {response.provider}")        # which backend handled it
```

### Streaming

```python
for chunk in client.chat.completions.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Write a haiku about Go performance."}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

### Async

```python
import asyncio
from ferrolabsai import AsyncFerroClient

async def main():
    async with AsyncFerroClient(api_key="sk-ferro-...") as client:
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
    async with AsyncFerroClient(api_key="sk-ferro-...") as client:
        async for chunk in await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Count to 5"}],
            stream=True,
        ):
            print(chunk.choices[0].delta.content or "", end="", flush=True)
```

### Embeddings

```python
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=["Ferro routes LLM requests", "across 29 providers"],
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

```python
# Browse all 2,500+ models
models = client.models.list()

# Filter by provider
anthropic_models = client.models.list(provider="anthropic")

# Filter by capability
vision_models = client.models.list(capability="vision")

# Pricing for a specific model
info = client.models.retrieve("gpt-4o")
print(f"Context window: {info.context_window:,} tokens")
print(f"Input:  ${info.input_cost_per_token * 1_000_000:.2f}/M tokens")
print(f"Output: ${info.output_cost_per_token * 1_000_000:.2f}/M tokens")
```

### Forwarded Ferro fields: templates & route tags

The SDK passes two Ferro-specific fields on `chat.completions.create(...)`:

**`template_id` + `template_variables`** — forwarded in the chat completion body for gateway deployments that support server-side prompt templates:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "I can't log in"}],
    template_id="support-agent",
    template_variables={
        "product": "Acme SaaS",
        "plan": "Pro",
        "date": "2026-04-09",
    },
)
```

**`route_tag`** — forwarded as `x_route_tag` in the chat completion body for gateway deployments that support per-request route tags:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    route_tag="low-cost",   # e.g. forces fallback to cheaper providers
)
```

These fields are pass-through SDK fields. Confirm your gateway version supports them before relying on them for routing or template rendering.

---

## Observability

Every `ChatCompletion` includes fields that tell you what the gateway actually did — no extra API calls, no log scraping:

| Field | Type | Source |
|---|---|---|
| `response.provider` | `str` | Which upstream provider served the request (e.g. `"openai"`, `"anthropic"`) |
| `response.trace_id` | `str` | Correlates this request with gateway logs |
| `response.latency_ms` | `int` | End-to-end gateway latency |
| `response.usage.cost_usd` | `float` | Computed cost in USD |
| `response.usage.cache_hit` | `bool` | Whether the response came from the gateway's semantic cache |
| `response.usage.prompt_tokens` / `completion_tokens` / `total_tokens` | `int` | Standard OpenAI token counts |

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)

print(f"trace={response.trace_id} provider={response.provider} "
      f"latency={response.latency_ms}ms cost=${response.usage.cost_usd:.6f}")
```

To dig deeper into a specific request, use `client.admin.logs.list(trace_id=...)` — see [Admin API](#admin-api-oss-gateway).

---

## Configuration

`FerroClient` and `AsyncFerroClient` accept the same keyword arguments:

```python
client = FerroClient(
    api_key="sk-ferro-...",                  # or FERRO_API_KEY env var
    base_url="http://localhost:8080",        # or FERRO_BASE_URL env var
    timeout=120.0,                           # seconds (default: 120.0)
    max_retries=2,                           # retries on connection errors (default: 2)
    default_headers={"x-env": "prod"},       # merged into every request
    http_client=my_httpx_client,             # bring your own httpx.Client
)
```

**Retries** are triggered only by `httpx.ConnectError` and `httpx.TimeoutException` — HTTP errors (4xx/5xx) propagate immediately as typed exceptions so you can handle them yourself.

**Bring-your-own httpx client** lets you configure proxies, custom TLS, connection pool limits, or instrumentation middleware and reuse that across the SDK:

```python
import httpx

pooled = httpx.Client(limits=httpx.Limits(max_connections=50))
client = FerroClient(api_key="sk-ferro-...", http_client=pooled)
```

Close the client explicitly when you're done (or use a `with` block):

```python
with FerroClient(api_key="sk-ferro-...") as client:
    ...
# or
client = FerroClient(api_key="sk-ferro-...")
try:
    ...
finally:
    client.close()
```

---

## Error handling

```python
from ferrolabsai import (
    FerroClient,
    FerroAuthError,
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
except FerroAuthError:
    print("Invalid API key — check FERRO_API_KEY")
except FerroRateLimitError:
    print("Rate limit hit — back off and retry")
except FerroNotFoundError:
    print("Model or endpoint not found")
except FerroServerError as e:
    print(f"Gateway error {e.status_code} — upstream provider may be down")
except FerroConnectionError:
    print("Cannot reach gateway — is it running?")
```

All HTTP-level exceptions inherit from `FerroAPIError` and expose `.status_code`, `.code`, `.message`, and `.request_id`. `FerroConnectionError` and `FerroStreamError` inherit from `FerroError` directly.

---

## Admin API (OSS gateway)

These APIs are available on any self-hosted Ferro Labs AI Gateway instance. Requires an admin-scoped API key.

The admin namespace mirrors the OSS gateway's `/admin/*` HTTP surface defined in [`internal/admin/handlers.go`](https://github.com/ferro-labs/ai-gateway/blob/main/internal/admin/handlers.go).

### API keys

```python
# Create
new_key = client.admin.keys.create(
    name="backend-service",
    scopes=["admin"],
)
print(new_key.key)  # full key value — shown ONCE, store it securely

# List
keys = client.admin.keys.list()

# Per-key usage counts (sorted by usage by default)
usage = client.admin.keys.usage(limit=20)

# Revoke — keeps the record for audit, invalidates the key immediately
client.admin.keys.revoke("key_id")

# Rotate — atomically invalidates old, returns new
rotated = client.admin.keys.rotate("key_id")

# Permanently delete the record
client.admin.keys.delete("key_id")
```

### Gateway routing config

The OSS gateway has a single *active* routing config. Use `history()` to inspect prior versions and `rollback(version)` to revert. Updates are zero-downtime hot reloads.

```python
# Read the current config
cfg = client.admin.config.get()
print(cfg.strategy)  # e.g. {"mode": "fallback"}
print(cfg.targets)   # list of {virtual_key, weight, ...}

# Replace it (PUT) — hot reload, no restart
client.admin.config.update({
    "strategy": {"mode": "fallback"},
    "targets": [
        {"virtual_key": "openai",    "weight": 1},
        {"virtual_key": "anthropic", "weight": 1},
        {"virtual_key": "groq",      "weight": 1},
    ],
    "plugins": [
        {"name": "cache",  "enabled": True},
        {"name": "logger", "enabled": True},
    ],
})

# Inspect history and roll back
history = client.admin.config.history()
client.admin.config.rollback(history[-2].version)
```

### Request logs

The gateway logs every request (when the `logger` plugin is enabled). Query, aggregate, and prune via `client.admin.logs`.

```python
# Recent failures
errors = client.admin.logs.list(limit=20, stage="on_error")
for entry in errors["data"]:
    print(entry["trace_id"], entry["model"], entry["provider"])

# Aggregate stats
stats = client.admin.logs.stats()

# Prune old entries
client.admin.logs.delete(before="2026-01-01T00:00:00Z")
```

### Providers, plugins, dashboard

```python
providers = client.admin.providers.list()  # registered LLM providers
plugins   = client.admin.plugins.list()    # installed gateway plugins
dashboard = client.admin.dashboard()       # high-level counts
health    = client.admin.health()          # gateway health check
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
make clean            # remove artifacts
```

All 30 tests run in under a second against `pytest-httpx` fixtures, so no network or running gateway is required.

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Links

- [Ferro Labs AI Gateway (OSS)](https://github.com/ferro-labs/ai-gateway)
- [Issue tracker](https://github.com/ferro-labs/ferrolabs-python-sdk/issues)
- [Changelog](CHANGELOG.md)
