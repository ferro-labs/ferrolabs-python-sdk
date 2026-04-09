# ferrolabsai — Official Python SDK for Ferro Labs AI Gateway

[![PyPI version](https://badge.fury.io/py/ferrolabsai.svg)](https://badge.fury.io/py/ferrolabsai)
[![Python versions](https://img.shields.io/pypi/pyversions/ferrolabsai.svg)](https://pypi.org/project/ferrolabsai/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/ferro-labs/sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/ferro-labs/sdk-python/actions/workflows/ci.yml)

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
```

---

## Installation

```bash
pip install ferrolabsai
```

Requires Python 3.8+. The only dependency is `httpx`.

---

## Quickstart

### FerroCloud (managed)

Sign up at [ferrolabs.ai](https://ferrolabs.ai) and grab your API key from the dashboard.

```python
from ferrolabsai import FerroClient

client = FerroClient(api_key="sk-ferro-your-key")
# base_url defaults to https://api.ferrolabs.ai
```

### Self-hosted OSS gateway

```python
client = FerroClient(
    api_key="sk-ferro-your-key",
    base_url="http://localhost:8080",  # your gateway address
)
```

### Environment variables

```bash
export FERRO_API_KEY="sk-ferro-your-key"
export FERRO_BASE_URL="https://api.ferrolabs.ai"  # optional
```

```python
client = FerroClient()  # reads from env automatically
```

---

## Migrate from OpenAI in one line

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

## Features

### Chat completions

```python
# Non-streaming
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain LLM routing in one paragraph."},
    ],
    temperature=0.7,
    max_tokens=256,
)
print(response.content)
print(f"Cost: ${response.usage.cost_usd:.6f}")
print(f"Provider: {response.provider}")  # Ferro tells you which provider handled it
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

### Async streaming

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

# Get pricing for a specific model
info = client.models.retrieve("gpt-4o")
print(f"Context window: {info.context_window:,} tokens")
print(f"Input: ${info.input_cost_per_token * 1_000_000:.2f}/M tokens")
print(f"Output: ${info.output_cost_per_token * 1_000_000:.2f}/M tokens")
```

---

## Ferro-specific features

### Server-side prompt templates

Define templates once in the dashboard, render them dynamically at request time.
Variables use Go `text/template` syntax (`{{.variable_name}}`).

```python
# Create a template (one time)
template = client.admin.templates.create(
    name="support-agent",
    template="You are a support agent for {{.product}}. "
             "The user's subscription is {{.plan}}. "
             "Today is {{.date}}. Be concise and helpful.",
    variables=["product", "plan", "date"],
)
client.admin.templates.publish(template.id)

# Use it in completions — variables resolved server-side
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "I can't log in"}],
    template_id=template.id,
    template_variables={
        "product": "Acme SaaS",
        "plan": "Pro",
        "date": "2026-04-09",
    },
)
```

### Route tags (override routing per-request)

```python
# Force a specific routing strategy for one request
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    route_tag="low-cost",   # maps to a conditional routing rule
)
```

---

## Admin API (OSS gateway)

These APIs are available on any self-hosted Ferro Labs AI Gateway instance
or via FerroCloud. Requires an admin-scoped API key.

The admin namespace mirrors the OSS gateway's `/admin/*` HTTP surface
defined in [`internal/admin/handlers.go`](https://github.com/ferro-labs/ai-gateway/blob/main/internal/admin/handlers.go).

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

The OSS gateway has a single *active* routing config. Use `history()` to
inspect prior versions and `rollback(version)` to revert. Updates are
zero-downtime hot reloads.

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
        {"name": "cache",   "enabled": True},
        {"name": "logger",  "enabled": True},
    ],
})

# Inspect history and roll back
history = client.admin.config.history()
client.admin.config.rollback(history[-2].version)
```

### Request logs

The gateway logs every request (when the `logger` plugin is enabled).
Query, aggregate, and prune them via `client.admin.logs`.

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

### Providers and plugins

```python
providers = client.admin.providers.list()  # registered LLM providers
plugins   = client.admin.plugins.list()    # installed gateway plugins
dashboard = client.admin.dashboard()       # high-level counts
health    = client.admin.health()          # gateway health check
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
except FerroServerError as e:
    print(f"Gateway error {e.status_code} — provider may be down")
except FerroConnectionError:
    print("Cannot reach gateway — is it running?")
```

---

## Framework integrations

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    api_key="sk-ferro-your-key",
    base_url="https://api.ferrolabs.ai/v1",
    model="gpt-4o",
)
response = llm.invoke("Hello from LangChain via Ferro")
```

### LlamaIndex

```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    api_key="sk-ferro-your-key",
    api_base="https://api.ferrolabs.ai/v1",
    model="gpt-4o",
)
```

### Vercel AI SDK (Next.js)

```typescript
import { createOpenAI } from '@ai-sdk/openai';

const ferro = createOpenAI({
  apiKey: process.env.FERRO_API_KEY,
  baseURL: 'https://api.ferrolabs.ai/v1',
});
```

---

## Development

```bash
git clone https://github.com/ferro-labs/sdk-python
cd sdk-python
pip install -e ".[dev]"

# Run tests (no gateway needed — all HTTP is mocked)
pytest tests/ -v

# Type check
mypy ferrolabsai/

# Lint
ruff check ferrolabsai/
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Links

- [Ferro Labs AI Gateway (OSS)](https://github.com/ferro-labs/ai-gateway)
- [FerroCloud Dashboard](https://app.ferrocloud.io)
- [Documentation](https://docs.ferrolabs.ai/sdk/python)
- [Discord Community](https://discord.gg/ferrolabs)
