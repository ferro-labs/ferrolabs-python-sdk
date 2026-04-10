# AGENT.md — AI Coding Agent Guide for ferrolabsai

This document provides instructions for AI coding agents working on the `ferrolabsai` Python SDK — the official client library for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway).

---

## Project Overview

`ferrolabsai` is a drop-in replacement for the OpenAI Python SDK that routes LLM requests through the Ferro Labs AI Gateway to 29+ providers and 2,500+ models. The SDK exposes an OpenAI-compatible surface for chat completions, embeddings, images, and model catalog, plus Ferro-specific admin APIs for gateway management.

- **Package name:** `ferrolabsai`
- **Version:** Defined in `pyproject.toml` under `[project].version`
- **Python support:** 3.9+
- **Only runtime dependency:** `httpx`
- **License:** Apache-2.0

---

## Repository Structure

```
ferrolabs-python-sdk/
├── ferrolabsai/                  # Main package
│   ├── __init__.py               # Public API surface — all exports live here
│   ├── client.py                 # FerroClient + AsyncFerroClient implementations
│   ├── types.py                  # Dataclass response models (ChatCompletion, Usage, etc.)
│   ├── completions/              # chat.completions resource (sync + async)
│   │   ├── resource.py           # Completions (sync)
│   │   └── async_resource.py     # AsyncCompletions
│   ├── embeddings/               # embeddings resource (sync + async)
│   │   ├── resource.py           # Embeddings (sync)
│   │   └── async_resource.py     # AsyncEmbeddings
│   ├── images/                   # images resource
│   │   └── resource.py
│   ├── models/                   # model catalog resource
│   │   └── resource.py
│   ├── admin/                    # Admin API (keys, config, logs, providers, plugins)
│   │   └── resource.py
│   └── exceptions/               # Exception hierarchy
│       └── __init__.py
├── tests/
│   └── test_sdk.py               # Full test suite (pytest + pytest-httpx)
├── docs/
│   └── architecture.md           # SDK architecture, design decisions, request lifecycle
├── pyproject.toml                # Build config, dependencies, tool settings
├── Makefile                      # Dev shortcuts: install, test, lint, format, build, clean
├── .github/workflows/ci.yml     # CI: test matrix (3.9–3.12), lint, publish to PyPI
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE
```

---

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
make install          # pip install -e ".[dev]"
```

Dev dependencies: `pytest`, `pytest-asyncio`, `pytest-httpx`, `mypy`, `ruff`.

---

## Key Commands

| Command        | Purpose                                           |
| -------------- | ------------------------------------------------- |
| `make install` | Editable install with dev extras                  |
| `make test`    | Run pytest suite                                  |
| `make lint`    | Run `ruff check` + `mypy`                         |
| `make format`  | Run `ruff format`                                 |
| `make build`   | Build sdist + wheel into `dist/`                  |
| `make clean`   | Remove build artifacts and tool caches            |

Always run `make format lint test` before committing.

---

## Coding Conventions

### Language & Style
- **Python 3.9+ syntax** — use `dict[str, X]`, `X | None`, `from __future__ import annotations`.
- **Type annotations are mandatory** on every public function, method, and class attribute. `mypy --strict` must pass.
- **Ruff** handles linting and formatting. Line length is **100** characters. Select rules: `E`, `F`, `I`, `UP`.
- Do not hand-format — run `make format`.

### Architecture Patterns
- **Dataclass response models** — all types in `types.py` are `@dataclass` with a `from_dict()` classmethod. No pydantic dependency.
- **Resource pattern** — each API area (completions, embeddings, images, models, admin) lives in its own sub-package with a `resource.py` (sync) and optionally `async_resource.py`.
- **Client holds HTTP** — `FerroClient._request()` and `AsyncFerroClient._request()` are the only HTTP entry points. Resources receive the client instance and call `self._client._request(...)`.
- **Exception hierarchy** — all HTTP errors raise typed exceptions inheriting from `FerroAPIError` (which inherits from `FerroError`). Connection/timeout errors retry automatically and raise `FerroConnectionError`.
- **Immutability by default** — do not mutate arguments; return new objects.
- **Keep files small** — prefer several focused modules over one large file.

### Public API
- All public exports must be listed in `ferrolabsai/__init__.py` and the `__all__` list.
- The SDK mirrors the OpenAI SDK surface: `client.chat.completions.create()`, `client.embeddings.create()`, `client.images.generate()`, `client.models.list()`.
- Ferro-specific extras: `template_id`, `template_variables`, `route_tag` on completions; `client.admin.*` for gateway management.

### Environment Variables
- `FERRO_API_KEY` — primary API key (takes precedence).
- `OPENAI_API_KEY` — fallback for migration.
- `FERRO_BASE_URL` — gateway address (defaults to `http://localhost:8080`).

---

## Testing

- Tests live in `tests/test_sdk.py`.
- All HTTP is mocked using `pytest-httpx` — **no real gateway or network access is needed**.
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- Every bug fix needs a regression test. Every new feature needs unit tests.
- Target 80%+ coverage on new code.
- Run: `make test` or `pytest tests/ -v --tb=short`.

---

## CI / CD

- **CI workflow:** `.github/workflows/ci.yml`
- Tests run on Python 3.9, 3.10, 3.11, 3.12 on `ubuntu-latest`.
- Lint and type check run as part of CI.
- **Publishing:** Triggered by semver tags (`v*.*.*`). Uses PyPI trusted publishing (OIDC). Asserts the tag matches `pyproject.toml` version.
- PRs target `development` branch; releases are cut from `main`.

---

## Branching & Commits

- **Feature branches** are created from `development`.
- PRs target `development`; squash-merged by default.
- Releases are cut from `main`.
- Follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `ci:`.
- Keep subjects under 72 characters.

---

## Adding a New API Resource

1. Create a new sub-package under `ferrolabsai/` (e.g., `ferrolabsai/newresource/`).
2. Add `resource.py` with a class that takes `client: FerroClient` in `__init__`.
3. Use `self._client._request(method, path, ...)` for HTTP calls.
4. Return typed dataclass models — add them to `types.py` with `from_dict()`.
5. Wire the resource into `FerroClient.__init__` in `client.py`.
6. Export new types from `ferrolabsai/__init__.py` and add to `__all__`.
7. Add async variant in `async_resource.py` if needed, wire into `AsyncFerroClient`.
8. Write tests in `tests/test_sdk.py` with `pytest-httpx` mocks.
9. Update `CHANGELOG.md` under `Unreleased`.

---

## Common Pitfalls

- **Do not add runtime dependencies** beyond `httpx` without discussion. The SDK is intentionally lightweight.
- **Do not import pydantic** — response models are plain dataclasses.
- **Do not hardcode secrets** in code, tests, or fixtures.
- **Ferro-specific response fields** (`trace_id`, `provider`, `latency_ms`, `cost_usd`) come from custom headers/body fields prefixed with `x_ferro_`. Handle graceful fallback when they're absent.
- **`from __future__ import annotations`** must be at the top of every module for 3.9 compatibility with `X | None` syntax.

---

## Documentation

In-depth design docs live in `docs/`:

| Document                                  | Covers                                                                           |
| ----------------------------------------- | -------------------------------------------------------------------------------- |
| [`docs/architecture.md`](docs/architecture.md) | Module map, resource pattern, request lifecycle, streaming, admin API surface, error handling, Ferro-specific extensions |

Read `architecture.md` before making structural changes to the SDK.

---

## Related Repositories

- [ferro-labs/ai-gateway](https://github.com/ferro-labs/ai-gateway) — The backend gateway (Go). The SDK talks to its HTTP API.
- Admin API surface is defined in `internal/admin/handlers.go` in the gateway repo.
