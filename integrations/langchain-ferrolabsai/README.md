# langchain-ferrolabsai

[![PyPI version](https://badge.fury.io/py/langchain-ferrolabsai.svg)](https://pypi.org/project/langchain-ferrolabsai/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

LangChain integration for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — route LangChain chat, streaming, tool-calling, and embedding workloads across **30+ LLM providers** through a single OpenAI-compatible endpoint, with automatic fallback, load balancing, cost tracking, and observability.

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
    base_url="http://localhost:8080",   # any Ferro Labs AI Gateway instance
    api_key="sk-ferro-...",
)

response = llm.invoke([HumanMessage(content="Hello, world")])
print(response.content)
print(response.response_metadata["provider"])     # which provider handled it
print(response.response_metadata["cost_usd"])     # cost for this request
print(response.response_metadata["latency_ms"])   # observed latency
print(response.response_metadata["trace_id"])     # gateway trace ID (x-trace-id)
```

Swap providers without changing the model class — Ferro auto-routes by model
name:

```python
claude = FerroChatModel(model="claude-3-5-sonnet-20241022", base_url="...", api_key="...")
gemini = FerroChatModel(model="gemini-1.5-flash",            base_url="...", api_key="...")
```

### Streaming

```python
for chunk in llm.stream([HumanMessage(content="Tell me a story")]):
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

### Embeddings

```python
from langchain_ferrolabsai import FerroEmbeddings

embed = FerroEmbeddings(model="text-embedding-3-small", base_url="...", api_key="...")
vectors = embed.embed_documents(["hello", "world"])
query_vec = embed.embed_query("hello")
```

### Legacy `LLM` interface

```python
from langchain_ferrolabsai import FerroLLM

llm = FerroLLM(model="gpt-4o", base_url="...", api_key="...")
print(llm.invoke("Write a haiku about gateways"))
```

## Why use this instead of `ChatOpenAI(base_url=...)`?

`ChatOpenAI` pointed at a Ferro Labs gateway works as a drop-in. This package adds:

- First-class `provider`, `cost_usd`, `latency_ms`, `trace_id` exposure on `response_metadata`.
- Native support for Ferro extras: `route_tag`, `template_id`, `template_variables`.
- `trace_id` is the **join key** for the v1.2 observability bridge plugins
  (LangSmith, Langfuse, Phoenix, Datadog, …) shipping from the
  [`ferro-labs/ai-gateway-plugins`](https://github.com/ferro-labs) repo —
  any provider's calls become visible in your existing LLMOps backend without
  per-provider wiring.

## Status & roadmap

`0.1.0` is the **first functional release** of the adapter. See
[`CHANGELOG.md`](CHANGELOG.md) for what shipped and what's planned. Async
surfaces and `with_structured_output()` are the next two items.

## Related

- [`ferrolabsai`](https://pypi.org/project/ferrolabsai/) — the core Python SDK this package wraps.
- [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — the open-source gateway server (v1.1.0+ OTel-native).
- [`ai-gateway-cookbook`](https://github.com/ferro-labs/ai-gateway-cookbook) — runnable recipes (start with `python/02-langgraph-multi-provider-agent`).
- [Documentation](https://docs.ferrolabs.ai)

## License

Apache-2.0
