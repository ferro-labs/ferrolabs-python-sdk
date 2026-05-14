# Changelog

All notable changes to `llama-index-llms-ferrolabsai` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- `FerroLabsAI` — `llama_index.core.llms.LLM` adapter wrapping `ferrolabsai.FerroClient.chat.completions`.
- Sync + async + streaming chat / completion modes.
- `provider`, `cost_usd`, `latency_ms`, `trace_id` exposed via `additional_kwargs`.
- Native support for Ferro extras (`route_tag`, `template_id`, `template_variables`).
- Tool / function calling pass-through.
- pytest-httpx based test suite.
- Upstream PR mirroring into `run-llama/llama_index` once stable.

---

## [0.0.1] — TBD

Placeholder release to reserve the `llama-index-llms-ferrolabsai` name on PyPI. No working implementation; importing `FerroLabsAI` raises `NotImplementedError` with a link to the roadmap.
