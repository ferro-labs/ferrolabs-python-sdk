# Changelog

All notable changes to `langchain-ferrolabsai` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- `FerroChatModel` — `langchain_core.language_models.chat_models.BaseChatModel` adapter wrapping `ferrolabsai.FerroClient.chat.completions`.
- `FerroEmbeddings` — `langchain_core.embeddings.Embeddings` adapter wrapping `ferrolabsai.FerroClient.embeddings`.
- `FerroLLM` — completion-style adapter for legacy LangChain chains.
- Streaming + async + tool calling.
- `provider`, `cost_usd`, `latency_ms`, `trace_id` exposed via `response_metadata`.
- Native support for Ferro extras (`route_tag`, `template_id`, `template_variables`).
- pytest-httpx based test suite mirroring the parent SDK's mocking pattern.

---

## [0.0.1] — TBD

Placeholder release to reserve the `langchain-ferrolabsai` name on PyPI. No working implementation; importing the package raises `NotImplementedError` with a link to the roadmap.
