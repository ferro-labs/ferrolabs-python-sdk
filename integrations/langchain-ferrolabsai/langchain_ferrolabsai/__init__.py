"""LangChain integration for Ferro Labs AI Gateway.

This is a 0.0.1 placeholder release. The full adapter (FerroChatModel,
FerroEmbeddings, FerroLLM) is under active development. Track progress at:

    https://github.com/ferro-labs/ai-gateway-workspace/blob/main/docs/OSS-ECOSYSTEM-ROADMAP.md

Once shipped, the public API will be:

    from langchain_ferrolabsai import FerroChatModel, FerroEmbeddings, FerroLLM
"""

from __future__ import annotations

__version__ = "0.0.1"

__all__ = ["__version__"]


def _not_implemented(name: str) -> None:
    raise NotImplementedError(
        f"langchain_ferrolabsai.{name} is not implemented in 0.0.1. "
        "This release reserves the package name. "
        "Track progress at https://github.com/ferro-labs/ai-gateway-workspace."
    )


def __getattr__(name: str) -> object:
    if name in {"FerroChatModel", "FerroEmbeddings", "FerroLLM"}:
        _not_implemented(name)
    raise AttributeError(f"module 'langchain_ferrolabsai' has no attribute {name!r}")
