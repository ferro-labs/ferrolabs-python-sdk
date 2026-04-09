"""
ferrolabsai — Official Python SDK for Ferro Labs AI Gateway

pip install ferrolabsai

Quick start::

    from ferrolabsai import FerroClient

    client = FerroClient(api_key="sk-ferro-...")

    # OpenAI-compatible — just change base_url
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.content)

    # Route to ANY provider by model name — Ferro handles it
    response = client.chat.completions.create(
        model="claude-3-5-sonnet-20241022",  # → Anthropic
        messages=[{"role": "user", "content": "Hello"}],
    )

Async::

    from ferrolabsai import AsyncFerroClient

    async with AsyncFerroClient(api_key="sk-ferro-...") as client:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

Migrate from openai in one line::

    # Before
    from openai import OpenAI
    client = OpenAI(api_key="sk-...")

    # After — all existing code works unchanged
    from ferrolabsai import FerroClient
    client = FerroClient(api_key="sk-ferro-...")
"""

from .client import AsyncFerroClient, FerroClient
from .exceptions import (
    FerroAPIError,
    FerroAuthError,
    FerroConnectionError,
    FerroError,
    FerroNotFoundError,
    FerroRateLimitError,
    FerroServerError,
    FerroStreamError,
)
from .types import (
    APIKey,
    ChatCompletion,
    ChatCompletionChunk,
    ChatMessage,
    Choice,
    ConfigHistoryEntry,
    CreatedAPIKey,
    EmbeddingData,
    EmbeddingResponse,
    GatewayConfig,
    ImageData,
    ImageResponse,
    ModelInfo,
    StreamChoice,
    StreamDelta,
    Usage,
)

__all__ = [
    # Clients
    "FerroClient",
    "AsyncFerroClient",
    # Exceptions
    "FerroError",
    "FerroAPIError",
    "FerroAuthError",
    "FerroRateLimitError",
    "FerroNotFoundError",
    "FerroServerError",
    "FerroConnectionError",
    "FerroStreamError",
    # Response types
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatMessage",
    "Choice",
    "StreamChoice",
    "StreamDelta",
    "Usage",
    "EmbeddingResponse",
    "EmbeddingData",
    "ImageResponse",
    "ImageData",
    "ModelInfo",
    # Admin types
    "APIKey",
    "CreatedAPIKey",
    "GatewayConfig",
    "ConfigHistoryEntry",
]

__version__ = "0.1.0"
