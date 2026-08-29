"""
Typed response models for the Ferro AI Gateway Python SDK.
All models are dataclasses so they work without pydantic as a hard dependency.

Field shapes follow ai-gateway v1.4.x (``providers/core/chat.go``,
``internal/handler/models.go``, ``internal/admin/model``). Gateway-specific
extensions are: body ``provider`` / ``provider_metadata`` / ``reasoning_content``
and the extra ``usage`` token counters; ``trace_id`` and ``gateway_overhead_ms``
come from the ``X-Request-ID`` and ``X-Gateway-Overhead-Ms`` response headers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types_responses import Response

__all__ = [
    "APIKey",
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatMessage",
    "Choice",
    "ConfigHistoryEntry",
    "CreatedAPIKey",
    "EmbeddingData",
    "EmbeddingResponse",
    "GatewayConfig",
    "ImageData",
    "ImageResponse",
    "ModelInfo",
    "Response",
    "StreamChoice",
    "StreamDelta",
    "Usage",
]

# ------------------------------------------------------------------
# Chat completions
# ------------------------------------------------------------------


@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    reasoning_content: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatMessage:
        return cls(
            role=d.get("role", ""),
            content=d.get("content"),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
            reasoning_content=d.get("reasoning_content"),
        )


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Gateway extensions (omitted by the gateway when zero).
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Usage:
        return cls(
            prompt_tokens=d.get("prompt_tokens", 0),
            completion_tokens=d.get("completion_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
            reasoning_tokens=d.get("reasoning_tokens"),
            cache_read_tokens=d.get("cache_read_tokens"),
            cache_write_tokens=d.get("cache_write_tokens"),
        )


@dataclass
class Choice:
    index: int
    message: ChatMessage
    finish_reason: str | None = None
    logprobs: Any | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Choice:
        return cls(
            index=d.get("index", 0),
            message=ChatMessage.from_dict(d.get("message", {})),
            finish_reason=d.get("finish_reason"),
            logprobs=d.get("logprobs"),
        )


@dataclass
class ChatCompletion:
    id: str
    object: str
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    # Gateway extensions
    trace_id: str | None = None  # X-Request-ID header
    provider: str | None = None  # body `provider` (or X-Gateway-Provider header)
    gateway_overhead_ms: float | None = None  # X-Gateway-Overhead-Ms header
    provider_metadata: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatCompletion:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "chat.completion"),
            created=d.get("created", 0),
            model=d.get("model", ""),
            choices=[Choice.from_dict(c) for c in d.get("choices", [])],
            usage=Usage.from_dict(d["usage"]) if d.get("usage") else None,
            trace_id=d.get("trace_id"),
            provider=d.get("provider"),
            gateway_overhead_ms=d.get("gateway_overhead_ms"),
            provider_metadata=d.get("provider_metadata"),
        )

    @property
    def content(self) -> str | None:
        """Shortcut to the first choice's message content."""
        if self.choices:
            return self.choices[0].message.content
        return None


# ------------------------------------------------------------------
# Streaming
# ------------------------------------------------------------------


@dataclass
class StreamDelta:
    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    reasoning_content: str | None = None


@dataclass
class StreamChoice:
    index: int
    delta: StreamDelta
    finish_reason: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StreamChoice:
        delta = d.get("delta", {})
        return cls(
            index=d.get("index", 0),
            delta=StreamDelta(
                role=delta.get("role"),
                content=delta.get("content"),
                tool_calls=delta.get("tool_calls"),
                reasoning_content=delta.get("reasoning_content"),
            ),
            finish_reason=d.get("finish_reason"),
        )


@dataclass
class ChatCompletionChunk:
    id: str
    object: str
    created: int
    model: str
    choices: list[StreamChoice]
    # Only on the terminal chunk, and only when the request sent
    # ``stream_options={"include_usage": True}``.
    usage: Usage | None = None
    # Copied from the stream's response headers onto every chunk.
    trace_id: str | None = None
    provider: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatCompletionChunk:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "chat.completion.chunk"),
            created=d.get("created", 0),
            model=d.get("model", ""),
            choices=[StreamChoice.from_dict(c) for c in d.get("choices", [])],
            usage=Usage.from_dict(d["usage"]) if d.get("usage") else None,
        )


# ------------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------------


@dataclass
class EmbeddingData:
    index: int
    embedding: list[float]
    object: str = "embedding"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmbeddingData:
        return cls(
            index=d.get("index", 0),
            embedding=d.get("embedding", []),
            object=d.get("object", "embedding"),
        )


@dataclass
class EmbeddingResponse:
    object: str
    data: list[EmbeddingData]
    model: str
    usage: Usage | None = None
    trace_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmbeddingResponse:
        return cls(
            object=d.get("object", "list"),
            data=[EmbeddingData.from_dict(e) for e in d.get("data", [])],
            model=d.get("model", ""),
            usage=Usage.from_dict(d["usage"]) if d.get("usage") else None,
            trace_id=d.get("trace_id"),
        )


# ------------------------------------------------------------------
# Images
# ------------------------------------------------------------------


@dataclass
class ImageData:
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ImageData:
        return cls(
            url=d.get("url"),
            b64_json=d.get("b64_json"),
            revised_prompt=d.get("revised_prompt"),
        )


@dataclass
class ImageResponse:
    created: int
    data: list[ImageData]
    trace_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ImageResponse:
        return cls(
            created=d.get("created", 0),
            data=[ImageData.from_dict(i) for i in d.get("data", [])],
            trace_id=d.get("trace_id"),
        )


# ------------------------------------------------------------------
# Admin — API Keys
# ------------------------------------------------------------------
#
# Field shape matches model.APIKey in ai-gateway/internal/admin/model.
# Listings and GET /admin/keys/{id} mask `key` to `fgw_ab12...cd34`; the full
# secret is returned exactly once from create / rotate (CreatedAPIKey).


@dataclass
class APIKey:
    id: str
    name: str
    scopes: list[str] = field(default_factory=list)
    created_at: str = ""
    active: bool = True
    usage_count: int = 0
    key: str | None = None  # masked (e.g. "fgw_ab12...cd34") on retrieve
    expires_at: str | None = None
    revoked_at: str | None = None
    rotated_at: str | None = None
    last_used_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> APIKey:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            scopes=d.get("scopes") or [],
            created_at=d.get("created_at", ""),
            active=d.get("active", True),
            usage_count=d.get("usage_count", 0),
            key=d.get("key"),
            expires_at=d.get("expires_at"),
            revoked_at=d.get("revoked_at"),
            rotated_at=d.get("rotated_at"),
            last_used_at=d.get("last_used_at"),
        )


@dataclass
class CreatedAPIKey:
    """Returned once on key creation or rotation — includes the full key value."""

    id: str
    name: str
    key: str  # full key value (e.g. "fgw_..."), only shown once
    scopes: list[str] = field(default_factory=list)
    created_at: str = ""
    active: bool = True
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CreatedAPIKey:
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            key=d.get("key", ""),
            scopes=d.get("scopes") or [],
            created_at=d.get("created_at", ""),
            active=d.get("active", True),
            expires_at=d.get("expires_at"),
        )


# ------------------------------------------------------------------
# Admin — Gateway Config
# ------------------------------------------------------------------
#
# The OSS gateway exposes a single active routing config at /admin/config.
# Shape mirrors aigateway.Config in ai-gateway/config.go: strategy, targets,
# plugins, aliases. The raw dict is preserved for forward compatibility with
# fields the SDK doesn't model explicitly (e.g. mcp_servers).


@dataclass
class GatewayConfig:
    strategy: dict[str, Any] = field(default_factory=dict)
    targets: list[dict[str, Any]] = field(default_factory=list)
    plugins: list[dict[str, Any]] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GatewayConfig:
        return cls(
            strategy=d.get("strategy") or {},
            targets=d.get("targets") or [],
            plugins=d.get("plugins") or [],
            aliases=d.get("aliases") or {},
            raw=d,
        )


@dataclass
class ConfigHistoryEntry:
    """One snapshot from /admin/config/history."""

    version: int
    updated_at: str
    config: GatewayConfig
    rolled_back_from: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConfigHistoryEntry:
        return cls(
            version=d.get("version", 0),
            updated_at=d.get("updated_at", ""),
            config=GatewayConfig.from_dict(d.get("config") or {}),
            rolled_back_from=d.get("rolled_back_from"),
        )


# ------------------------------------------------------------------
# Model catalog — EnrichedModelInfo (ai-gateway internal/handler/models.go)
# ------------------------------------------------------------------


@dataclass
class ModelInfo:
    id: str
    object: str = "model"
    owned_by: str = ""
    created: int = 0
    mode: str | None = None  # "chat", "embedding", "image", ...
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: list[str] = field(default_factory=list)
    status: str | None = None
    deprecated: bool = False

    @property
    def provider(self) -> str:
        """Alias for ``owned_by`` — the provider that serves this model."""
        return self.owned_by

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelInfo:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "model"),
            owned_by=d.get("owned_by", ""),
            created=d.get("created", 0),
            mode=d.get("mode"),
            context_window=d.get("context_window"),
            max_output_tokens=d.get("max_output_tokens"),
            capabilities=d.get("capabilities") or [],
            status=d.get("status"),
            deprecated=d.get("deprecated", False),
        )
