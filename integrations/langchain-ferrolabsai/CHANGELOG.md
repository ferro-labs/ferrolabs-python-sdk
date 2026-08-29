# Changelog

All notable changes to `langchain-ferrolabsai` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Native multi-modal message support (image inputs) once the gateway exposes a
  stable contract.

---

## [0.2.0] — 2026-08-29

Requires `ferrolabsai >= 0.3.0` (the "truth release") and ai-gateway ≥ v1.4.0
(contract-tested against v1.4.5).

### Breaking

- The gateway-derived fields on `response_metadata` are now exactly what the
  gateway provides: `model`, `id`, `trace_id` (`X-Request-ID` header),
  `provider` (body field), `gateway_overhead_ms` (`X-Gateway-Overhead-Ms`
  header); LangChain adds its own (e.g. `finish_reason`). `latency_ms`,
  `cost_usd`, and `cache_hit` are gone — the gateway never emitted them, so
  they were always absent.
- Removed the `route_tag`, `template_id`, and `template_variables` fields from
  `FerroChatModel` and `FerroLLM`. The gateway has never read them.

### Added

- Async surface: `FerroChatModel._agenerate` / `_astream` (so `ainvoke`,
  `astream`, `abatch` run on `AsyncFerroClient` instead of a thread) and
  `FerroEmbeddings.aembed_documents` / `aembed_query`.
- `FerroChatModel.with_structured_output(schema, include_raw=False)` via the
  OpenAI-style `response_format={"type": "json_schema", ...}` path; accepts a
  pydantic model class or a JSON-schema dict.
- Streaming: the first chunk carries `trace_id` in `response_metadata`, and the
  terminal usage-only chunk surfaces `usage_metadata` (send
  `stream_options={"include_usage": True}`).
- Python 3.13 classifier.

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
