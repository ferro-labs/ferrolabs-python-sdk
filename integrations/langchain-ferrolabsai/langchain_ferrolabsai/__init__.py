"""LangChain integration for Ferro Labs AI Gateway.

Public API::

    from langchain_ferrolabsai import FerroChatModel, FerroEmbeddings, FerroLLM

    chat = FerroChatModel(model="gpt-4o", api_key="sk-ferro-...")
    embed = FerroEmbeddings(model="text-embedding-3-small", api_key="sk-ferro-...")
    legacy = FerroLLM(model="gpt-4o", api_key="sk-ferro-...")

All three classes route through a Ferro Labs AI Gateway endpoint (ai-gateway
≥ v1.4.0). Chat responses expose the gateway's ``trace_id`` (the ``X-Request-ID``
response header), ``provider`` and ``gateway_overhead_ms`` via
``response_metadata`` — ``trace_id`` is the join key for the gateway's request
log and its observability exporters (LangSmith, Langfuse, Phoenix, …).
"""

from __future__ import annotations

from .chat_models import FerroChatModel
from .embeddings import FerroEmbeddings
from .llms import FerroLLM

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "FerroChatModel",
    "FerroEmbeddings",
    "FerroLLM",
]
