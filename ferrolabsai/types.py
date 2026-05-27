"""
Typed response models for the Ferro AI Gateway Python SDK.
All models are dataclasses so they work without pydantic as a hard dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatMessage:
        return cls(
            role=d.get("role", ""),
            content=d.get("content"),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Ferro extras
    cost_usd: float | None = None
    cache_hit: bool | None = None
    provider: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Usage:
        return cls(
            prompt_tokens=d.get("prompt_tokens", 0),
            completion_tokens=d.get("completion_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
            cost_usd=d.get("cost_usd"),
            cache_hit=d.get("cache_hit"),
            provider=d.get("provider"),
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
    # Ferro-specific extras
    trace_id: str | None = None
    provider: str | None = None
    latency_ms: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatCompletion:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "chat.completion"),
            created=d.get("created", 0),
            model=d.get("model", ""),
            choices=[Choice.from_dict(c) for c in d.get("choices", [])],
            usage=Usage.from_dict(d["usage"]) if d.get("usage") else None,
            trace_id=d.get("x_ferro_trace_id") or d.get("trace_id"),
            provider=d.get("x_ferro_provider") or d.get("provider"),
            latency_ms=d.get("x_ferro_latency_ms") or d.get("latency_ms"),
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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatCompletionChunk:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "chat.completion.chunk"),
            created=d.get("created", 0),
            model=d.get("model", ""),
            choices=[StreamChoice.from_dict(c) for c in d.get("choices", [])],
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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmbeddingResponse:
        return cls(
            object=d.get("object", "list"),
            data=[EmbeddingData.from_dict(e) for e in d.get("data", [])],
            model=d.get("model", ""),
            usage=Usage.from_dict(d["usage"]) if d.get("usage") else None,
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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ImageResponse:
        return cls(
            created=d.get("created", 0),
            data=[ImageData.from_dict(i) for i in d.get("data", [])],
        )


# ------------------------------------------------------------------
# Admin — API Keys
# ------------------------------------------------------------------
#
# Field shape matches admin.APIKey in
# ai-gateway/internal/admin/keys.go. On retrieve (GET /admin/keys/{id})
# the gateway masks `key` to `<first 8 chars>...`. On create / rotate the
# full key is returned exactly once — captured by CreatedAPIKey below.


@dataclass
class APIKey:
    id: str
    name: str
    scopes: list[str] = field(default_factory=list)
    created_at: str = ""
    active: bool = True
    usage_count: int = 0
    key: str | None = None  # masked (e.g. "fgw_abcd...") on retrieve
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
# Model catalog
# ------------------------------------------------------------------


@dataclass
class ModelInfo:
    id: str
    object: str
    provider: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    capabilities: list[str] | None = None
    status: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelInfo:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "model"),
            provider=d.get("owned_by") or d.get("provider", ""),
            context_window=d.get("context_window"),
            max_output_tokens=d.get("max_output_tokens"),
            input_cost_per_token=d.get("input_cost_per_token"),
            output_cost_per_token=d.get("output_cost_per_token"),
            capabilities=d.get("capabilities"),
            status=d.get("status"),
        )
