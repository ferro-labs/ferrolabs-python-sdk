"""Shared test fixtures for langchain-ferrolabsai.

Follows the same pytest-httpx mocking pattern as the parent ferrolabsai SDK so
no real gateway is required to run the suite. Payloads mirror what
ai-gateway v1.4.x returns: `provider` in the chat body, `X-Request-ID` and
`X-Gateway-Overhead-Ms` as response headers.
"""

from __future__ import annotations

from typing import Any

import pytest

BASE_URL = "http://test-gateway:8080"
API_KEY = "sk-ferro-test"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
GATEWAY_HEADERS = {"X-Request-ID": TRACE_ID, "X-Gateway-Overhead-Ms": "1.5"}


def make_chat_completion(
    *,
    content: str = "Hello back",
    model: str = "gpt-4o",
    provider: str = "openai",
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a gateway chat-completion body for use with httpx_mock."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": model,
        "provider": provider,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
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


def sse_chunks(*contents: str, finish: bool = True) -> bytes:
    import json

    frames = [
        {
            "id": "1",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": c}, "finish_reason": None}],
        }
        for c in contents
    ]
    if finish:
        frames.append(
            {
                "id": "1",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-4o",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
        )
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
    return body.encode("utf-8")


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def api_key() -> str:
    return API_KEY
