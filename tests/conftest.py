"""Shared fixtures for the ferrolabsai unit suite.

All HTTP is mocked with pytest-httpx — no gateway required. The contract
suite under ``tests/contract`` is the one place a real gateway is used.
"""

from __future__ import annotations

from typing import Any

import pytest

from ferrolabsai import AsyncFerroClient, FerroClient

BASE_URL = "http://localhost:8080"
API_KEY = "sk-ferro-testkey123"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"

COMPLETION_RESPONSE: dict[str, Any] = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o",
    "provider": "openai",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello from Ferro!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}

EMBEDDING_RESPONSE: dict[str, Any] = {
    "object": "list",
    "data": [
        {"index": 0, "object": "embedding", "embedding": [0.1, 0.2, 0.3]},
        {"index": 1, "object": "embedding", "embedding": [0.4, 0.5, 0.6]},
    ],
    "model": "text-embedding-3-small",
    "usage": {"prompt_tokens": 8, "total_tokens": 8},
}

IMAGE_RESPONSE: dict[str, Any] = {
    "created": 1700000000,
    "data": [{"url": "https://example.com/image.png", "revised_prompt": "A polished prompt"}],
}

# Shape of GET /v1/models: EnrichedModelInfo (ai-gateway internal/handler/models.go).
MODELS_RESPONSE: dict[str, Any] = {
    "object": "list",
    "data": [
        {
            "id": "gpt-4o",
            "object": "model",
            "created": 0,
            "owned_by": "openai",
            "mode": "chat",
            "context_window": 128000,
            "max_output_tokens": 16384,
            "capabilities": ["vision", "function_calling", "streaming"],
            "status": "active",
        },
        {
            "id": "claude-3-5-sonnet-20241022",
            "object": "model",
            "created": 0,
            "owned_by": "anthropic",
            "mode": "chat",
            "context_window": 200000,
            "capabilities": ["function_calling", "streaming"],
            "deprecated": True,
        },
        {
            "id": "text-embedding-3-small",
            "object": "model",
            "created": 0,
            "owned_by": "openai",
            "mode": "embedding",
        },
    ],
}


def sse(*frames: dict[str, Any] | str) -> bytes:
    """Encode dict frames (or raw payload strings) as an SSE body ending in [DONE]."""
    import json

    lines = [
        f"data: {frame if isinstance(frame, str) else json.dumps(frame)}\n\n" for frame in frames
    ]
    return "".join(lines).encode() + b"data: [DONE]\n\n"


def chunk(content: str | None = None, **extra: Any) -> dict[str, Any]:
    delta: dict[str, Any] = {} if content is None else {"content": content}
    return {
        "id": "c1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "gpt-4o",
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        **extra,
    }


@pytest.fixture
def client() -> FerroClient:
    return FerroClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0)


@pytest.fixture
def async_client() -> AsyncFerroClient:
    return AsyncFerroClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0)
