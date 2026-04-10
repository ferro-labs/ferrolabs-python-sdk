# Copilot Instructions for `ferrolabs-python-sdk`

## Build, test, and lint commands

- Install dev dependencies: `make install` or `pip install -e ".[dev]"`
- Run the full test suite: `make test` or `pytest tests/ -v`
- Run a single test: `pytest tests/test_sdk.py::TestChatCompletions::test_basic_create -v`
- Run a subset of tests by name: `pytest tests/test_sdk.py -k streaming -v`
- Lint and type-check: `make lint` or `ruff check ferrolabsai tests && mypy ferrolabsai`
- Format: `make format` or `ruff format ferrolabsai tests`
- Build the package: `make build` or `python3 -m build`

## High-level architecture

- `ferrolabsai/client.py` is the hub. It resolves API keys from `FERRO_API_KEY` with fallback to `OPENAI_API_KEY`, resolves `FERRO_BASE_URL` with a default of `http://localhost:8080`, owns the shared `httpx` client, applies retry/error handling, and wires the public namespaces.
- Public SDK namespaces intentionally mirror the OpenAI SDK and the gateway HTTP surface: `client.chat.completions`, `client.embeddings`, `client.images`, `client.models`, and `client.admin.*`.
- Resource modules are thin request builders. Each `ferrolabsai/<domain>/resource.py` file translates Python kwargs into the corresponding gateway request and delegates transport to `FerroClient._request(...)` or the streaming helpers instead of managing `httpx` behavior itself.
- `ferrolabsai/types.py` is the response normalization layer. Gateway JSON is converted into dataclasses there, including OpenAI-compatible fields plus Ferro-specific extras like `provider`, `trace_id`, `latency_ms`, `cost_usd`, and raw gateway config payloads.
- Admin support is a direct wrapper around `/admin/*` endpoints. The `Admin` namespace groups sub-resources for keys, config, logs, providers, and plugins, and some admin methods intentionally return raw dict payloads when the gateway response shape is still loosely structured.
- Tests in `tests/test_sdk.py` are request/response contract tests around the HTTP layer. They use `pytest-httpx` to verify headers, payloads, path routing, SSE streaming parsing, env-var fallbacks, retry validation, and admin endpoint behavior without requiring a live gateway.

## Key conventions

- Target Python 3.9 syntax. New modules should use `from __future__ import annotations`, public functions and methods are expected to be fully typed, and changes should stay compatible with the repo's `mypy --strict` setup.
- Ruff is both the linter and formatter here. Keep changes aligned with the existing 100-character line length and prefer the repo's Ruff formatting over hand-formatting.
- Preserve the OpenAI-style surface first. New capabilities should usually be exposed as additional kwargs on existing resource methods or as new resource namespaces that match gateway routes, not as a parallel custom API shape.
- Ferro-only request features are forwarded as request fields, not wrapped in separate helper abstractions. Existing examples are `template_id` and `template_variables`; sync chat completions also map `route_tag` to `x_route_tag`, but async parity is not complete yet.
- Keep resource classes thin. Shared behavior such as retries, auth headers, connection handling, status-code mapping, and HTTP client lifecycle belongs in `client.py`, not duplicated across resource modules.
- Public resource methods should return typed dataclasses parsed via `from_dict(...)` helpers in `types.py` unless the endpoint is intentionally passthrough admin data.
- Error translation is centralized in `_raise_api_error(...)`. Extend the existing `Ferro*Error` hierarchy instead of leaking raw `httpx` exceptions from public SDK methods.
- Async support is added explicitly per namespace. Today `AsyncFerroClient` wires `chat.completions` and `embeddings`; if you add async support elsewhere, create the matching `async_resource.py`, register it in `AsyncFerroClient`, and add async tests.
- When adding public clients, exceptions, or response types, update `ferrolabsai/__init__.py` and `__all__` so the package surface stays explicit and importable from the top level.
- Tests should mock HTTP precisely with `pytest_httpx.HTTPXMock` and assert the exact outgoing request shape, especially auth headers, routed endpoint paths, Ferro-specific fields, and SSE frames ending with `data: [DONE]`.
