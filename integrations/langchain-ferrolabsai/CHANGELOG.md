# Changelog

All notable changes to `langchain-ferrolabsai` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Async surfaces (`_agenerate`, `_astream`, `aembed_documents`, `aembed_query`).
- `with_structured_output()` helper for JSON-mode + Pydantic-schema responses.
- Native multi-modal message support (image inputs) once the gateway exposes a
  stable contract.

---

## [0.1.0] — 2026-05-25

First functional release. Replaces the `0.0.1` placeholder.

### Added

- **`FerroChatModel`** — `langchain_core.language_models.chat_models.BaseChatModel`
  adapter wrapping `ferrolabsai.FerroClient.chat.completions`. Supports sync
  generation, streaming via `_stream`, and tool binding via `bind_tools`
  (compatible with LangGraph agents).
- **`FerroEmbeddings`** — `langchain_core.embeddings.Embeddings` adapter wrapping
  `ferrolabsai.FerroClient.embeddings`. `embed_documents` preserves input order
  even when the gateway returns embeddings out of order.
- **`FerroLLM`** — completion-style adapter for legacy LangChain chains. Wraps
  chat completions with a single user message.
- **`trace_id` surfacing** — every chat response carries `trace_id`, `provider`,
  `latency_ms`, `cost_usd`, and `cache_hit` (when present) in
  `response_metadata`. `trace_id` is the join key for the v1.2 observability
  bridge plugins (LangSmith, Langfuse, Phoenix, …).
- **Native support for Ferro extras** — `route_tag`, `template_id`,
  `template_variables`, and `user` are first-class fields on `FerroChatModel`
  and forwarded on every request.
- **`pytest-httpx`-based test suite** mirroring the parent SDK's mocking
  pattern. No real gateway or network access required to run tests.

### Notes

- Async support is intentionally deferred to a follow-up release to keep the
  initial diff reviewable. LangChain's default sync-fallback async behaviour
  works in the meantime.
- Streaming surfaces incremental content chunks and OpenAI-style streamed
  `delta.tool_calls` as LangChain `tool_call_chunks` for tool-using agents.

---

## [0.0.1] — 2026-05-13

Placeholder release to reserve the `langchain-ferrolabsai` name on PyPI. No
working implementation; importing the package raised `NotImplementedError`
with a link to the roadmap.
