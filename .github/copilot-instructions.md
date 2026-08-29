# Copilot Instructions for `ferrolabs-python-sdk`

## Build, test, and lint commands

- Install dev dependencies: `make install` or `pip install -e ".[dev]"`
- Run the full test suite: `make test` or `pytest tests/ -v` (the `tests/contract` dir auto-skips without a gateway)
- Run a single test: `pytest tests/test_chat.py::TestCreate::test_basic_create -v`
- Run a subset of tests by name: `pytest tests/test_chat.py -k streaming -v`
- Run the contract suite against a real gateway: `make contract` (builds `ferrogw` from `../ai-gateway`)
- Lint and type-check: `make lint` or `ruff check ferrolabsai tests && mypy ferrolabsai`
- Format: `make format` or `ruff format ferrolabsai tests`
- Build the package: `make build` or `python3 -m build`

## High-level architecture

- `ferrolabsai/client.py` is the hub. It resolves API keys from `FERRO_API_KEY` with fallback to `OPENAI_API_KEY`, resolves `FERRO_BASE_URL` with a default of `http://localhost:8080`, owns the shared `httpx` client, applies the retry policy (connect/timeout/408/429/5xx with jitter and `Retry-After`) and error mapping, merges the gateway's response headers into inference bodies, and wires the public namespaces. `ferrolabsai/streaming.py` wraps SSE responses in `Stream`/`AsyncStream`.
- Public SDK namespaces intentionally mirror the OpenAI SDK and the gateway HTTP surface: `client.chat.completions`, `client.embeddings`, `client.images`, `client.models`, `client.responses`, `client.moderations`, `client.rerank()`, the probes `client.health()/ready()/live()/capabilities()`, and `client.admin.*`.
- Resource modules are thin request builders. Each `ferrolabsai/<domain>/resource.py` file translates Python kwargs into the corresponding gateway request and delegates transport to `FerroClient._request(...)` or the streaming helpers instead of managing `httpx` behavior itself.
- `ferrolabsai/types.py` is the response normalization layer. Gateway JSON is converted into dataclasses there, including OpenAI-compatible fields plus the gateway's real extensions: `provider`, `trace_id` (`X-Request-ID`), `gateway_overhead_ms` (`X-Gateway-Overhead-Ms`), `provider_metadata`, `reasoning_content`, the extra usage counters, and raw gateway config payloads. There is no cost, cache-hit, or latency field — the gateway does not expose them to callers.
- Admin support is a direct wrapper around `/admin/*` endpoints. The `Admin` namespace groups sub-resources for keys, config, logs, providers, plugins, and audit, and some admin methods intentionally return raw dict payloads when the gateway response shape is still loosely structured.
- Unit tests in `tests/test_{client,chat,resources,admin}.py` are request/response tests around the HTTP layer. They use `pytest-httpx` to verify headers, payloads, path routing, SSE streaming parsing, env-var fallbacks, the retry policy, and admin endpoint behavior without requiring a live gateway. `tests/contract/` runs the same claims against a real gateway booted by `scripts/with-gateway.sh`.

## Key conventions

- Target Python 3.9 syntax. New modules should use `from __future__ import annotations`, public functions and methods are expected to be fully typed, and changes should stay compatible with the repo's `mypy --strict` setup.
- Ruff is both the linter and formatter here. Keep changes aligned with the existing 100-character line length and prefer the repo's Ruff formatting over hand-formatting.
- Preserve the OpenAI-style surface first. New capabilities should usually be exposed as additional kwargs on existing resource methods or as new resource namespaces that match gateway routes, not as a parallel custom API shape.
- Only send request fields the gateway actually decodes (`internal/handler/chatrequest.go`). `max_completion_tokens`, `parallel_tool_calls`, `response_format`, `stream_options`, `seed` are first-class; anything else passes through `**kwargs` verbatim. Do not reintroduce the old routing-tag / prompt-template request fields — the gateway never read them.
- Keep resource classes thin. Shared behavior such as retries, auth headers, connection handling, status-code mapping, and HTTP client lifecycle belongs in `client.py`, not duplicated across resource modules.
- Public resource methods should return typed dataclasses parsed via `from_dict(...)` helpers in `types.py` unless the endpoint is intentionally passthrough admin data.
- Error translation is centralized in `_raise_api_error(...)`. Extend the existing `Ferro*Error` hierarchy instead of leaking raw `httpx` exceptions from public SDK methods.
- Async support is added explicitly per namespace. Every namespace has an `async_resource.py` that reuses the sync module's body builders and path constants; if you add a namespace, create both, register them in `FerroClient` and `AsyncFerroClient`, and add async tests.
- When adding public clients, exceptions, or response types, update `ferrolabsai/__init__.py` and `__all__` so the package surface stays explicit and importable from the top level.
- Tests should mock HTTP precisely with `pytest_httpx.HTTPXMock` and assert the exact outgoing request shape, especially auth headers, routed endpoint paths, and SSE frames ending with `data: [DONE]`. Anything that claims a gateway behaviour also needs an assertion in `tests/contract/test_contract.py`.
