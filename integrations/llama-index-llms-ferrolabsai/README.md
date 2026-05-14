# llama-index-llms-ferrolabsai

[![PyPI version](https://badge.fury.io/py/llama-index-llms-ferrolabsai.svg)](https://pypi.org/project/llama-index-llms-ferrolabsai/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

LlamaIndex LLM integration for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — power LlamaIndex RAG, agents, and query engines with **30+ LLM providers** through a single OpenAI-compatible endpoint, with automatic fallback, load balancing, cost tracking, and observability.

> **Status: 0.0.1 placeholder.** The full adapter (`FerroLabsAI` LLM class) is in active development as part of the [OSS Ecosystem Roadmap, Appendix A, Phase C](https://github.com/ferro-labs/ai-gateway-workspace/blob/main/docs/OSS-ECOSYSTEM-ROADMAP.md). The 0.0.1 release exists to reserve the package name on PyPI and signal upcoming work.

---

## Install

```bash
pip install llama-index-llms-ferrolabsai
```

## Planned API

```python
from llama_index.llms.ferrolabsai import FerroLabsAI

llm = FerroLabsAI(
    model="gpt-4o",
    base_url="http://localhost:8080",   # any Ferro Labs AI Gateway instance
    api_key="sk-ferro-...",
)

resp = llm.complete("Explain RAG in one sentence.")
print(resp.text)

# Per-response Ferro metadata (additional_kwargs)
print(resp.additional_kwargs["provider"])
print(resp.additional_kwargs["cost_usd"])
print(resp.additional_kwargs["latency_ms"])
print(resp.additional_kwargs["trace_id"])
```

## Why use this instead of `OpenAI(api_base=...)`?

`llama_index.llms.openai.OpenAI` pointed at a Ferro Labs gateway already works as a drop-in. This package adds:

- First-class `provider`, `cost_usd`, `latency_ms`, `trace_id` exposure on `additional_kwargs`.
- Native support for Ferro extras: `route_tag`, `template_id`, `template_variables`.
- Streaming + async modes that surface all 30+ providers transparently.
- A tested compatibility matrix against LlamaIndex's chat / completion / streaming interfaces.

## Upstream mirror

Once stable, this package will also be mirrored as a PR to
[`run-llama/llama_index`](https://github.com/run-llama/llama_index) under
`llama-index-integrations/llms/llama-index-llms-ferrolabsai/` for first-party hub discoverability.

## Related

- [`ferrolabsai`](https://pypi.org/project/ferrolabsai/) — the core Python SDK this package wraps.
- [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway) — the open-source gateway server.
- [Documentation](https://docs.ferrolabs.ai)

## License

Apache-2.0
