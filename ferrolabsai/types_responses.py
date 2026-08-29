"""Response type for the OpenAI-style Responses API (``POST /v1/responses``).

The Responses object is large and evolving, so only the stable top-level
fields are typed; ``raw`` keeps the full body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Response:
    id: str
    object: str = "response"
    created_at: int = 0
    status: str | None = None  # "completed", "in_progress", "failed", ...
    model: str = ""
    output: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] | None = None
    # Gateway extensions
    trace_id: str | None = None  # X-Request-ID header
    provider: str | None = None  # X-Gateway-Provider header
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Response:
        return cls(
            id=d.get("id", ""),
            object=d.get("object", "response"),
            created_at=d.get("created_at", 0),
            status=d.get("status"),
            model=d.get("model", ""),
            output=d.get("output") or [],
            usage=d.get("usage"),
            trace_id=d.get("trace_id"),
            provider=d.get("provider"),
            raw=d,
        )
