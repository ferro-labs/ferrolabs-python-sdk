# langchain-ferrolabsai

[![PyPI version](https://badge.fury.io/py/langchain-ferrolabsai.svg)](https://pypi.org/project/langchain-ferrolabsai/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

LangChain integration for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — route LangChain chat, streaming, tool-calling, and embedding workloads across **30+ LLM providers** through a single OpenAI-compatible endpoint, with automatic fallback, load balancing, cost tracking, and observability.

> **Status: 0.0.1 placeholder.** The full adapter (`FerroChatModel`, `FerroEmbeddings`, `FerroLLM`) is in active development as part of the [OSS Ecosystem Roadmap, Appendix A, Phase C](https://github.com/ferro-labs/ai-gateway-workspace/blob/main/docs/OSS-ECOSYSTEM-ROADMAP.md). The 0.0.1 release exists to reserve the package name on PyPI and signal upcoming work.

---

## Install

```bash
pip install langchain-ferrolabsai
```

## Planned API

```python
from langchain_ferrolabsai import FerroChatModel, FerroEmbeddings

llm = FerroChatModel(
    model="gpt-4o",
    base_url="http://localhost:8080",   # any Ferro Labs AI Gateway instance
    api_key="sk-ferro-...",
)

response = llm.invoke("Hello, world")
print(response.content)
print(response.response_metadata["provider"])     # which provider handled it
print(response.response_metadata["cost_usd"])     # cost for this request
print(response.response_metadata["latency_ms"])   # observed latency
print(response.response_metadata["trace_id"])     # gateway trace ID
```

## Why use this instead of `ChatOpenAI(base_url=...)`?

`ChatOpenAI` pointed at a Ferro Labs gateway already works as a drop-in. This package adds:

- First-class `provider`, `cost_usd`, `latency_ms`, `trace_id` exposure on `response_metadata`.
- Native support for Ferro extras: `route_tag`, `template_id`, `template_variables`.
- Streaming + async + tool calling that surfaces all 30+ providers transparently.
- Optional LangSmith bridge so non-OpenAI providers (Anthropic, Bedrock, Vertex, etc.) appear in your existing LangSmith dashboards.

## Related

- [`ferrolabsai`](https://pypi.org/project/ferrolabsai/) — the core Python SDK this package wraps.
- [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — the open-source gateway server.
- [Documentation](https://docs.ferrolabs.ai)

## License

Apache-2.0
