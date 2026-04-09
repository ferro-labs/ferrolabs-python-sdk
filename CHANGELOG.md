# Changelog

All notable changes to `ferrolabsai` will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-04-09

### Added
- `FerroClient` — synchronous client with OpenAI-compatible interface
- `AsyncFerroClient` — async client using `httpx.AsyncClient`
- `client.chat.completions.create()` — streaming and non-streaming
- `client.embeddings.create()` — text embeddings
- `client.images.generate()` — image generation
- `client.models.list()` / `.retrieve()` / `.search()` — 2,500+ model catalog
- `client.admin.keys` — API key CRUD (list, retrieve, create, update, delete, revoke, rotate, usage) backed by `/admin/keys`
- `client.admin.config` — single-active routing config: `get`, `create`, `update`, `delete`, `history`, `rollback` backed by `/admin/config`
- `client.admin.logs` — request log query / stats / prune backed by `/admin/logs`
- `client.admin.providers`, `client.admin.plugins`, `client.admin.dashboard()`, `client.admin.health()`
- Ferro-specific extras: `template_id`, `template_variables`, `route_tag`, `cost_usd`, `provider`
- Full exception hierarchy: `FerroAuthError`, `FerroRateLimitError`, `FerroNotFoundError`, `FerroServerError`, `FerroConnectionError`
- Auto-retry on connection errors (configurable `max_retries`)
- Context manager support (`with FerroClient(...) as client:`)
- Environment variable support: `FERRO_API_KEY`, `FERRO_BASE_URL`, `OPENAI_API_KEY` fallback
- Test suite with 100% mocked HTTP (no real gateway needed)
- GitHub Actions CI across Python 3.8–3.12 with PyPI trusted publishing
