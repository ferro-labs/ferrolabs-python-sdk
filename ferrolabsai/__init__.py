"""
ferrolabsai — Official Python SDK for Ferro Labs AI Gateway

pip install ferrolabsai

Compatibility: ferrolabsai 0.3.x ↔ ai-gateway ≥ v1.4.0.

Quick start::

    from ferrolabsai import FerroClient

    client = FerroClient(api_key="fgw_...")

    # OpenAI-compatible — just change base_url
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.content, response.provider, response.trace_id)

    # Route to ANY provider by model name — Ferro handles it
    response = client.chat.completions.create(
        model="claude-3-5-sonnet-20241022",  # → Anthropic
        messages=[{"role": "user", "content": "Hello"}],
    )

Async::

    from ferrolabsai import AsyncFerroClient

    async with AsyncFerroClient(api_key="fgw_...") as client:
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
    client = FerroClient(api_key="fgw_...")
"""

from ._version import __version__
from .client import AsyncFerroClient, FerroClient
from .exceptions import (
    FerroAPIError,
    FerroAuthError,
    FerroBudgetExceededError,
    FerroConnectionError,
    FerroError,
    FerroNotFoundError,
    FerroPermissionError,
    FerroRateLimitError,
    FerroServerError,
    FerroStreamError,
)
from .streaming import AsyncStream, Stream
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
    Response,
    StreamChoice,
    StreamDelta,
    Usage,
)

__all__ = [
    "__version__",
    # Clients
    "FerroClient",
    "AsyncFerroClient",
    # Exceptions
    "FerroError",
    "FerroAPIError",
    "FerroAuthError",
    "FerroBudgetExceededError",
    "FerroPermissionError",
    "FerroRateLimitError",
    "FerroNotFoundError",
    "FerroServerError",
    "FerroConnectionError",
    "FerroStreamError",
    # Streaming
    "Stream",
    "AsyncStream",
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
    "Response",
    # Admin types
    "APIKey",
    "CreatedAPIKey",
    "GatewayConfig",
    "ConfigHistoryEntry",
]
