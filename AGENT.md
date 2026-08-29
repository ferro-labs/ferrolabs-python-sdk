# AGENT.md — AI Coding Agent Guide for ferrolabsai

This document provides instructions for AI coding agents working on the `ferrolabsai` Python SDK — the official client library for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway).

---

## Project Overview

`ferrolabsai` is a drop-in replacement for the OpenAI Python SDK that routes LLM requests through the Ferro Labs AI Gateway to 30 providers and 2,500+ models. The SDK exposes an OpenAI-compatible surface for chat completions, embeddings, images, the Responses API, moderations, rerank, and the model catalog, plus gateway-specific surface: health probes, `/v1/capabilities`, and the `/admin/*` management API.

- **Package name:** `ferrolabsai`
- **Version:** `pyproject.toml` `[project].version` and `ferrolabsai/_version.py` (kept equal; a test asserts it)
- **Compatibility:** `ferrolabsai 0.3.x` ↔ `ai-gateway ≥ v1.4.0` (contract-tested against `v1.4.5`)
- **Python support:** 3.9 – 3.13
- **Only runtime dependency:** `httpx`
- **License:** Apache-2.0

---

## Repository Structure

```
ferrolabs-python-sdk/
├── ferrolabsai/                  # Main package (publishes `ferrolabsai` to PyPI)
│   ├── __init__.py               # Public API surface — all exports live here
│   ├── _version.py               # __version__ constant
│   ├── client.py                 # FerroClient + AsyncFerroClient, retry policy, error mapping
│   ├── streaming.py              # Stream / AsyncStream SSE wrappers
│   ├── types.py                  # Dataclass response models (ChatCompletion, Usage, ModelInfo, ...)
│   ├── types_responses.py        # Response dataclass (Responses API), re-exported from types
│   ├── completions/              # chat.completions (resource.py + async_resource.py)
│   ├── embeddings/               # embeddings
│   ├── images/                   # images.generate
│   ├── models/                   # model catalog — client-side list/retrieve/search
│   ├── responses/                # /v1/responses create/retrieve/delete
│   ├── moderations/              # /v1/moderations
│   ├── admin/                    # Admin API (keys, config, logs, providers, plugins, audit)
│   └── exceptions/               # Exception hierarchy
├── integrations/                 # Sibling framework adapter packages (own pyproject.toml each)
│   ├── README.md                 # Layout + publishing overview
│   ├── langchain-ferrolabsai/    # Publishes `langchain-ferrolabsai` to PyPI (0.2.0, on ferrolabsai 0.3)
│   │   ├── pyproject.toml / README.md / CHANGELOG.md / LICENSE
│   │   ├── langchain_ferrolabsai/{__init__,chat_models,embeddings,llms,_messages}.py
│   │   └── tests/
│   └── llama-index-llms-ferrolabsai/   # Publishes `llama-index-llms-ferrolabsai` (placeholder 0.0.1)
│       ├── pyproject.toml / README.md / CHANGELOG.md / LICENSE
│       ├── llama_index/llms/ferrolabsai/__init__.py   # PEP 420 namespace package
│       └── tests/test_placeholder.py
├── tests/
│   ├── conftest.py               # Shared fixtures + canned gateway payloads
│   ├── test_client.py            # Construction, retries, error mapping, header metadata, probes
│   ├── test_chat.py              # Chat body, parsing, streaming (sync + async)
│   ├── test_resources.py         # Embeddings, images, models, responses
│   ├── test_admin.py             # /admin/* parity
│   └── contract/                 # Real-gateway suite (skipped unless FERRO_CONTRACT_BASE_URL)
│       ├── conftest.py
│       ├── stub_upstream.py      # stdlib fake OpenAI the gateway is pointed at
│       └── test_contract.py
├── scripts/with-gateway.sh       # Builds ferrogw from ../ai-gateway, boots it + the stub, runs tests/contract
├── docs/
│   └── architecture.md           # SDK architecture, gateway contract, request lifecycle
├── pyproject.toml                # Build config, dependencies, tool settings (ferrolabsai)
├── Makefile                      # Dev shortcuts: install, test, lint, format, build, contract, clean
├── .github/workflows/
│   ├── ci.yml                                          # Unit matrix + contract job + publish
│   ├── publish-langchain-ferrolabsai.yml               # Test + publish on `langchain-ferrolabsai-vX.Y.Z` tags
│   └── publish-llama-index-llms-ferrolabsai.yml        # Test + publish on `llama-index-llms-ferrolabsai-vX.Y.Z` tags
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE
```

### Sibling integration packages

Framework adapter packages live under `integrations/` as independently versioned and independently published Python distributions. Each sub-folder has its own `pyproject.toml`, README, CHANGELOG, LICENSE, source tree, and pytest suite, and is built with Hatchling exactly like the parent SDK.

| Package | Folder | Tag prefix | Publish workflow |
|---|---|---|---|
| `langchain-ferrolabsai` | `integrations/langchain-ferrolabsai/` | `langchain-ferrolabsai-vX.Y.Z` | `.github/workflows/publish-langchain-ferrolabsai.yml` |
| `llama-index-llms-ferrolabsai` | `integrations/llama-index-llms-ferrolabsai/` | `llama-index-llms-ferrolabsai-vX.Y.Z` | `.github/workflows/publish-llama-index-llms-ferrolabsai.yml` |

Conventions:

- **Independent versioning.** Each sub-package's `pyproject.toml` version is bumped on its own cadence. Do not piggy-back on the parent SDK's `v*.*.*` tag.
- **Tag prefix pattern.** Releases are cut by pushing tags like `langchain-ferrolabsai-v0.2.0`. The publish workflow asserts the tag matches the sub-package's `pyproject.toml` version before uploading.
- **Trusted Publishing.** PyPI credentials use OIDC environments named `pypi-langchain-ferrolabsai` and `pypi-llama-index-llms-ferrolabsai` — provision these on PyPI before the first publish.
- **Dependency on the core SDK.** Each sub-package declares `ferrolabsai>=X.Y.Z` as a runtime dependency (`langchain-ferrolabsai` needs `>=0.3.0`).
- **`llama_index` namespace package.** `llama-index-llms-ferrolabsai` uses the PEP 420 implicit namespace package layout (`llama_index/llms/ferrolabsai/`) so it can later be mirrored upstream into `run-llama/llama_index` with no code changes.
- **Placeholder behaviour.** While a sub-package is at `0.0.x`, its `__init__.py` exposes only `__version__`; any attempt to import the planned public classes raises `NotImplementedError` with a roadmap link. Real classes land at `0.1.0`.
- **Release flow.** `make build` and `make test` from the sub-folder; bump version in its `pyproject.toml` + `CHANGELOG.md`; commit + push tag with the prefix above; CI runs the full test matrix and publishes via Trusted Publishing.

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

| Command          | Purpose                                                            |
| ---------------- | ------------------------------------------------------------------ |
| `make install`   | Editable install with dev extras                                   |
| `make test`      | Run the unit suite (contract dir auto-skips)                       |
| `make lint`      | Run `ruff check` + `mypy`                                          |
| `make format`    | Run `ruff format`                                                  |
| `make build`     | Build sdist + wheel into `dist/`                                   |
| `make contract`  | Boot a real gateway from `../ai-gateway` and run `tests/contract`  |
| `make clean`     | Remove build artifacts and tool caches                             |

Always run `make format lint test` before committing; run `make contract` when touching anything that talks to the gateway.

---

## Coding Conventions

### Language & Style
- **Python 3.9+ syntax** — use `dict[str, X]`, `X | None`, `from __future__ import annotations`.
- **Type annotations are mandatory** on every public function, method, and class attribute. `mypy --strict` must pass on every CI leg (3.9 – 3.13).
- **Ruff** handles linting and formatting. Line length is **100** characters. Select rules: `E`, `F`, `I`, `UP`.
- Do not hand-format — run `make format`.

### Architecture Patterns
- **Dataclass response models** — all types in `types.py` are `@dataclass` with a `from_dict()` classmethod. No pydantic dependency.
- **Resource pattern** — each API area lives in its own sub-package with a `resource.py` (sync) and `async_resource.py`. The async module imports the body builders / path constants from the sync one so the wire format is written once.
- **Client holds HTTP** — `_request()` (retry + error mapping + header metadata on inference paths) and `_open_stream()` (SSE, never retried) are the only HTTP entry points. Resources receive the typed client (`if TYPE_CHECKING: from ..client import FerroClient`) and call `self._client._request(...)`.
- **Exception hierarchy** — all HTTP errors raise typed exceptions inheriting from `FerroAPIError`. `429`, connection errors, and connect timeouts retry for every method; `408/5xx` and read/write/pool timeouts retry only for idempotent methods (`_should_retry`). Jittered backoff honours `Retry-After`; exhaustion raises `FerroConnectionError` / the mapped `FerroAPIError`.
- **Immutability by default** — do not mutate arguments; return new objects (`_with_response_metadata` returns a new dict, streaming uses `dataclasses.replace`).
- **Keep files small** — prefer several focused modules over one large file (`types_responses.py` exists for that reason).

### Public API
- All public exports must be listed in `ferrolabsai/__init__.py` and the `__all__` list.
- The SDK mirrors the OpenAI SDK surface: `client.chat.completions.create()`, `client.embeddings.create()`, `client.images.generate()`, `client.models.list()`, `client.responses.create()`.
- Gateway-specific surface: `client.health()/ready()/live()/capabilities()/rerank()`, `client.moderations`, `client.admin.*`.
- **Only model what the gateway really does.** Response metadata comes from `X-Request-ID`, `X-Gateway-Provider`, `X-Gateway-Overhead-Ms`, and the body fields `provider` / `provider_metadata` / `reasoning_content` / usage counters. There is no cost, cache-hit, or latency field for callers, and no per-request routing-tag or prompt-template request field — do not reintroduce them. `docs/architecture.md` § "Gateway Contract" is the reference; the contract suite enforces it.

### Environment Variables
- `FERRO_API_KEY` — primary API key (takes precedence).
- `OPENAI_API_KEY` — fallback for migration.
- `FERRO_BASE_URL` — gateway address (defaults to `http://localhost:8080`).

---

## Testing

- Unit tests live in `tests/test_*.py`; shared fixtures and canned gateway payloads in `tests/conftest.py`.
- All HTTP is mocked using `pytest-httpx` — **no real gateway or network access is needed**.
- `tests/contract/` runs against a real gateway and is skipped unless `FERRO_CONTRACT_BASE_URL` is set; `scripts/with-gateway.sh` (or `make contract`) sets everything up. Every README observability claim is asserted there.
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- Every bug fix needs a regression test. Every new feature needs unit tests, and a contract assertion if it touches a gateway route.
- Target 80%+ coverage on new code.
- Run: `make test` or `pytest tests/ -v --tb=short`.

---

## CI / CD

- **CI workflow:** `.github/workflows/ci.yml`
- Unit tests, ruff, and mypy run on Python 3.9, 3.10, 3.11, 3.12, 3.13 on `ubuntu-latest`.
- **Contract job** checks out `ferro-labs/ai-gateway` at `v1.4.5` (required) and `main` (`continue-on-error`) and runs `scripts/with-gateway.sh`. Raise the pin when the SDK starts depending on newer gateway behaviour and update the README compatibility line.
- **Publishing:** Triggered by semver tags (`v*.*.*`); `needs` the unit matrix and the contract job. Uses PyPI trusted publishing (OIDC). Asserts the tag matches `pyproject.toml` version.
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
2. Add `resource.py` with a class that takes `client: FerroClient` in `__init__` (imported under `TYPE_CHECKING`), a `PATH` constant, and a module-level body builder.
3. Use `self._client._request(method, path, ...)` for HTTP calls. If the route returns inference metadata, add its prefix to `_INFERENCE_PREFIXES` in `client.py`.
4. Return typed dataclass models — add them to `types.py` with `from_dict()`.
5. Wire the resource into `FerroClient.__init__` in `client.py`.
6. Export new types from `ferrolabsai/__init__.py` and add to `__all__`.
7. Add the async variant in `async_resource.py` (reusing the sync builder), wire into `AsyncFerroClient`.
8. Write unit tests in `tests/test_<area>.py` with `pytest-httpx` mocks, and a contract test in `tests/contract/test_contract.py` (extend `stub_upstream.py` if the route needs an upstream).
9. Update `CHANGELOG.md` under `Unreleased` and the route tables in `README.md` / `docs/architecture.md`.

---

## Common Pitfalls

- **Do not add runtime dependencies** beyond `httpx` without discussion. The SDK is intentionally lightweight.
- **Do not import pydantic** — response models are plain dataclasses.
- **Do not hardcode secrets** in code, tests, or fixtures.
- **Do not call `GET /v1/models/{id}`** — it is not a native gateway route; it falls through to the `/v1/*` pass-through with the operator's provider credential. `models.retrieve()` is a client-side lookup for that reason.
- **Header metadata is for inference bodies only.** `_with_response_metadata` must never touch `/v1/models`, probe, or `/admin/*` bodies.
- **Streaming is never retried** and must keep the `httpx.Response` reachable (`Stream.response`).
- **`from __future__ import annotations`** must be at the top of every module for 3.9 compatibility with `X | None` syntax.

---

## Documentation

In-depth design docs live in `docs/`:

| Document                                  | Covers                                                                           |
| ----------------------------------------- | -------------------------------------------------------------------------------- |
| [`docs/architecture.md`](docs/architecture.md) | Module map, resource pattern, retry policy, streaming, the gateway contract (headers, body fields, catalog), admin route table, error handling |

Read `architecture.md` before making structural changes to the SDK.

---

## Related Repositories

- [ferro-labs/ai-gateway](https://github.com/ferro-labs/ai-gateway) — The backend gateway (Go). The SDK talks to its HTTP API.
- Admin API routes are defined in the `internal/admin/handlers` package (`server.go`, `Handlers.Routes`) in the gateway repo; the public routes in `internal/httpserver/router.go`.
