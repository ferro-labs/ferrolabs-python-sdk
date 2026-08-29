# langchain-ferrolabsai

[![PyPI version](https://badge.fury.io/py/langchain-ferrolabsai.svg)](https://pypi.org/project/langchain-ferrolabsai/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

LangChain integration for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — route LangChain chat, streaming, tool-calling, structured-output, and embedding workloads across **30 LLM providers** through a single OpenAI-compatible endpoint, with automatic fallback, load balancing, budgets, and observability.

Compatibility: `langchain-ferrolabsai 0.2.x` ↔ `ferrolabsai ≥ 0.3.0` ↔ `ai-gateway ≥ v1.4.0`; `langchain-core ≥ 0.3` (tested on 1.x).

---

## Install

```bash
pip install langchain-ferrolabsai
```

## Quick start

### Chat

```python
from langchain_ferrolabsai import FerroChatModel
from langchain_core.messages import HumanMessage

llm = FerroChatModel(
    model="gpt-4o",
    base_url="http://localhost:8080",  # any Ferro Labs AI Gateway instance
    api_key="fgw_...",
)

response = llm.invoke([HumanMessage(content="Hello, world")])
print(response.content)
print(response.response_metadata["provider"])  # which provider answered
print(response.response_metadata["trace_id"])  # gateway X-Request-ID
print(response.response_metadata.get("gateway_overhead_ms"))  # gateway's own overhead
```

`response_metadata` contains exactly what the gateway provides — `model`, `id`,
`trace_id`, `provider`, `gateway_overhead_ms` — with absent values stripped.
`trace_id` is the join key for `client.admin.logs.list()` and for the
gateway's observability exporters (LangSmith, Langfuse, Phoenix, …).

Swap providers without changing the model class — Ferro auto-routes by model
name:

```python
claude = FerroChatModel(model="claude-3-5-sonnet-20241022", base_url="...", api_key="...")
gemini = FerroChatModel(model="gemini-2.5-flash", base_url="...", api_key="...")
```

### Streaming

```python
for chunk in llm.stream([HumanMessage(content="Tell me a story")]):
    print(chunk.content, end="", flush=True)
```

### Async

```python
response = await llm.ainvoke([HumanMessage(content="Hello")])

async for chunk in llm.astream([HumanMessage(content="Tell me a story")]):
    print(chunk.content, end="", flush=True)
```

### Tool calling / LangGraph agents

```python
from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


agent_llm = llm.bind_tools([add])
response = agent_llm.invoke([HumanMessage(content="What is 4 + 7?")])
print(response.tool_calls)
```

### Structured output

Uses the OpenAI-style `response_format={"type": "json_schema", ...}` path, so
it works with every provider the gateway can translate it for (see
`client.capabilities()` on the core SDK).

```python
from pydantic import BaseModel


class Answer(BaseModel):
    city: str
    population: int


structured = llm.with_structured_output(Answer)
print(structured.invoke("Largest city in France?"))  # Answer(city='Paris', population=...)

# include_raw=True → {"raw": AIMessage, "parsed": Answer | None, "parsing_error": ...}
```

### Embeddings

```python
from langchain_ferrolabsai import FerroEmbeddings

embed = FerroEmbeddings(model="text-embedding-3-small", base_url="...", api_key="...")
vectors = embed.embed_documents(["hello", "world"])
query_vec = embed.embed_query("hello")

# async
vectors = await embed.aembed_documents(["hello", "world"])
```

### Legacy `LLM` interface

```python
from langchain_ferrolabsai import FerroLLM

llm = FerroLLM(model="gpt-4o", base_url="...", api_key="...")
print(llm.invoke("Write a haiku about gateways"))
```

## Why use this instead of `ChatOpenAI(base_url=...)`?

`ChatOpenAI` pointed at a Ferro Labs gateway works as a drop-in. This package adds:

- `provider`, `trace_id`, and `gateway_overhead_ms` on `response_metadata` (and
  `trace_id` on the first streamed chunk) — read from the gateway's real response
  headers, no guessing.
- Typed gateway errors from the core SDK: `FerroBudgetExceededError` (402),
  `FerroPermissionError` (403), `FerroRateLimitError.retry_after`, with
  `Retry-After`-aware retries on 429/5xx.
- Async parity (`ainvoke`, `astream`, `aembed_*`) over `AsyncFerroClient`.

## Status & roadmap

`0.2.0` adds the async surface and `with_structured_output()` on top of
`ferrolabsai 0.3`. See [`CHANGELOG.md`](CHANGELOG.md).

## Related

- [`ferrolabsai`](https://pypi.org/project/ferrolabsai/) — the core Python SDK this package wraps.
- [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — the open-source gateway server.
- [`ai-gateway-cookbook`](https://github.com/ferro-labs/ai-gateway-cookbook) — runnable recipes (start with `python/02-langgraph-multi-provider-agent`).
- [Documentation](https://docs.ferrolabs.ai)

## License

Apache-2.0
