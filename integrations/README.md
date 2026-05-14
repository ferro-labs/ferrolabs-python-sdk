# Ferro Labs — Framework Integrations

Sibling packages that adapt [`ferrolabsai`](https://pypi.org/project/ferrolabsai/) into popular AI frameworks.
Each sub-folder is an independently versioned, independently published Python package.

| Package | Folder | PyPI |
|---|---|---|
| `langchain-ferrolabsai` | [`langchain-ferrolabsai/`](./langchain-ferrolabsai/) | https://pypi.org/project/langchain-ferrolabsai/ |
| `llama-index-llms-ferrolabsai` | [`llama-index-llms-ferrolabsai/`](./llama-index-llms-ferrolabsai/) | https://pypi.org/project/llama-index-llms-ferrolabsai/ |

## Why a sub-folder layout?

- **One repo, one issue tracker, one CHANGELOG section per integration.**
- Each integration declares its own version + dependency pin on `ferrolabsai`.
- CI publishes each package independently when its folder's `pyproject.toml` version is bumped and a matching tag is pushed (e.g. `langchain-ferrolabsai-v0.1.0`).
- Mirrors the pattern used by Anthropic, Cohere, and the LangChain monorepo's `libs/partners/`.

## Building & publishing locally

```bash
cd integrations/langchain-ferrolabsai
python -m build
twine upload dist/*
```

CI workflows for each package live under `.github/workflows/publish-<package>.yml` (to be added).

## Upstream mirroring

- **`llama-index-llms-ferrolabsai`** — once stable, mirror as a PR to
  [`run-llama/llama_index`](https://github.com/run-llama/llama_index) under
  `llama-index-integrations/llms/llama-index-llms-ferrolabsai/`. Merge auto-publishes to PyPI.
- **`langchain-ferrolabsai`** — third-party publication is fine; optionally open a PR to
  `langchain-ai/langchain` under `libs/partners/ferrolabsai/` for first-party discoverability.
