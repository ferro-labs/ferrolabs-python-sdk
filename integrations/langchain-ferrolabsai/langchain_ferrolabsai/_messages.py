"""Conversion helpers between LangChain ``BaseMessage`` types and the
OpenAI-compatible dicts the Ferro gateway expects.

Kept tiny and dependency-light so the same module can be reused by the chat
model, the legacy ``FerroLLM`` adapter, and tests.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


def message_to_ferro_dict(message: BaseMessage) -> dict[str, Any]:
    """Convert a single LangChain ``BaseMessage`` to the OpenAI message shape.

    The Ferro gateway forwards this dict verbatim to the upstream provider,
    so the encoding must match the OpenAI chat-completions schema.
    """
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}

    if isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}

    if isinstance(message, AIMessage):
        d: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": tc.get("args", "")
                        if isinstance(tc.get("args"), str)
                        else _json_dumps(tc.get("args") or {}),
                    },
                }
                for tc in tool_calls
            ]
        return d

    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }

    if isinstance(message, FunctionMessage):
        # Legacy LangChain function-style messages map onto OpenAI ``function`` role.
        return {"role": "function", "name": message.name, "content": message.content}

    if isinstance(message, ChatMessage):
        return {"role": message.role, "content": message.content}

    raise TypeError(f"Unsupported LangChain message type: {type(message).__name__}")


def messages_to_ferro_dicts(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Convert a list of LangChain messages, preserving order."""
    return [message_to_ferro_dict(m) for m in messages]


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), default=str)
