"""Shared test fixtures for langchain-ferrolabsai.

Follows the same pytest-httpx mocking pattern as the parent ferrolabsai SDK so
no real gateway is required to run the suite.
"""

from __future__ import annotations

from typing import Any

import pytest

BASE_URL = "http://test-gateway:8080"
API_KEY = "sk-ferro-test"


def make_chat_completion(
    *,
    content: str = "Hello back",
    model: str = "gpt-4o",
    provider: str = "openai",
    trace_id: str = "trace-abc-123",
    latency_ms: int = 42,
    cost_usd: float = 0.000123,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a Ferro chat-completion response payload for use with httpx_mock."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "total_tokens": 8,
            "cost_usd": cost_usd,
            "provider": provider,
        },
        "x_ferro_trace_id": trace_id,
        "x_ferro_provider": provider,
        "x_ferro_latency_ms": latency_ms,
    }


def make_embedding_response(
    *,
    vectors: list[list[float]],
    model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    return {
        "object": "list",
        "model": model,
        "data": [
            {"index": i, "embedding": v, "object": "embedding"} for i, v in enumerate(vectors)
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
    }


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def api_key() -> str:
    return API_KEY
