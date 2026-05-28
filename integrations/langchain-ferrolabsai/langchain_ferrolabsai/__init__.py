"""LangChain integration for Ferro Labs AI Gateway.

Public API::

    from langchain_ferrolabsai import FerroChatModel, FerroEmbeddings, FerroLLM

    chat = FerroChatModel(model="gpt-4o", api_key="sk-ferro-...")
    embed = FerroEmbeddings(model="text-embedding-3-small", api_key="sk-ferro-...")
    legacy = FerroLLM(model="gpt-4o", api_key="sk-ferro-...")

All three classes route through a Ferro Labs AI Gateway endpoint and expose
the gateway's ``trace_id`` (frozen contract since ``ai-gateway v1.1.0``) via
``response_metadata`` — the join key for the v1.2 observability bridge plugins
(LangSmith, Langfuse, Phoenix, …).
"""

from __future__ import annotations

from .chat_models import FerroChatModel
from .embeddings import FerroEmbeddings
from .llms import FerroLLM

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "FerroChatModel",
    "FerroEmbeddings",
    "FerroLLM",
]
