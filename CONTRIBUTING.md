# Contributing to ferrolabsai

Thanks for your interest in contributing to the official Python SDK for [Ferro Labs AI Gateway](https://github.com/ferro-labs/ai-gateway). This document explains how to propose changes, set up your environment, and get your pull request merged.

## Code of Conduct

By participating in this project you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to `hello@ferrolabs.ai`.

## Ways to Contribute

- **Report bugs.** Open an issue with a minimal reproduction, the SDK version, Python version, and the gateway version you are targeting.
- **Propose features.** Open an issue describing the use case before sending a PR for anything non-trivial — it saves everyone time.
- **Improve docs.** Typos, clarifications, and new examples are always welcome.
- **Fix issues.** Look for issues labeled `good first issue` or `help wanted`.

## Development Setup

Requires Python 3.9 or newer.

```bash
git clone https://github.com/ferro-labs/ferrolabs-python-sdk.git
cd ferrolabs-python-sdk

python -m venv .venv
source .venv/bin/activate

make install
```

`make install` installs the package in editable mode with the `dev` extras (pytest, mypy, ruff).

## Make Targets

| Command        | Purpose                                    |
| -------------- | ------------------------------------------ |
| `make install` | Install the package in editable mode       |
| `make format`  | Format code with ruff                      |
| `make lint`    | Run ruff and mypy                          |
| `make test`    | Run the pytest suite                       |
| `make build`   | Build the sdist and wheel                  |
| `make clean`   | Remove build artifacts and tool caches     |

Run `make format lint test` before every commit.

## Coding Standards

- **Python 3.9+ syntax.** Use `dict[str, X]`, `X | None`, and `from __future__ import annotations` in new modules.
- **Type annotations are required** on every public function, method, and class attribute. `mypy --strict` must pass.
- **Ruff** handles both linting and formatting. Do not hand-format — run `make format`.
- **Keep files small.** Prefer several focused modules over one large file.
- **Immutability by default.** Do not mutate arguments; return new objects.
- **No hardcoded secrets** in code, tests, or fixtures.

## Tests

- Every bug fix needs a regression test.
- Every new feature needs unit tests, and integration tests when it touches the HTTP layer.
- Use `pytest-httpx` to mock gateway responses — do not hit real providers in tests.
- Target 80%+ coverage on new code.

Run the suite with:

```bash
make test
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

<optional body explaining the "why">
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.

Keep the subject line under 72 characters. Explain the motivation in the body when the change is not obvious.

## Pull Request Process

1. Fork the repo and create a feature branch off `development`.
2. Make focused commits — one logical change per commit where practical.
3. Run `make format lint test` locally.
4. Update `CHANGELOG.md` under the `Unreleased` section.
5. Open a PR against `development` with:
   - A clear description of what changed and why.
   - Links to related issues.
   - A short test plan showing what you verified.
6. Ensure CI passes. Address review feedback promptly.

PRs are squash-merged by default. Keep them reviewable — split large changes into smaller PRs when possible.

## Release Process

Releases are cut from `main`. Maintainers handle version bumps, tagging, and PyPI publication. If a change requires a release, mention it in the PR description.

## Questions

- Open a [GitHub Discussion](https://github.com/ferro-labs/ferrolabs-python-sdk/discussions) for design questions.
- Open an [issue](https://github.com/ferro-labs/ferrolabs-python-sdk/issues) for bugs and feature requests.
- Email `hello@ferrolabs.ai` for anything that needs a private channel.
