#!/usr/bin/env python3
"""Stub OpenAI-compatible upstream for the contract suite (stdlib only).

The gateway is pointed at this server with ``OPENAI_BASE_URL`` so chat,
streaming, embeddings, and the Responses API can be exercised end to end
without provider credentials. It serves a fixed model list and canned
replies, and records every request at ``GET /_requests`` so tests can prove
what did (and did not) reach upstream — e.g. that ``models.retrieve()`` never
turns into a pass-through ``GET /v1/models/{id}``.

    python3 tests/contract/stub_upstream.py --port 18081
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODELS = ["gpt-4o-mini", "text-embedding-3-small"]
REPLY = ("stub", " reply")
USAGE = {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
_requests: list[str] = []
_lock = threading.Lock()


def _chunk(model: str, delta: dict[str, Any], finish: str | None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:  # keep stdout quiet
        pass

    def _record(self) -> None:
        with _lock:
            _requests.append(f"{self.command} {self.path}")

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw or b"{}")
        return data if isinstance(data, dict) else {}

    def _not_found(self) -> None:
        self._json(
            404,
            {
                "error": {
                    "message": f"stub has no route {self.command} {self.path}",
                    "type": "invalid_request_error",
                    "code": "not_found",
                }
            },
        )

    def do_GET(self) -> None:
        self._record()
        if self.path == "/v1/models":
            data = [
                {"id": m, "object": "model", "created": 1700000000, "owned_by": "openai"}
                for m in MODELS
            ]
            self._json(200, {"object": "list", "data": data})
        elif self.path == "/_requests":
            with _lock:
                self._json(200, {"data": list(_requests)})
        else:
            self._not_found()

    def do_POST(self) -> None:
        self._record()
        body = self._read_body()
        model = str(body.get("model", "gpt-4o-mini"))
        if self.path == "/v1/chat/completions":
            if body.get("stream"):
                include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
                self._sse(model, include_usage)
            else:
                self._json(
                    200,
                    {
                        "id": "chatcmpl-stub",
                        "object": "chat.completion",
                        "created": 1700000000,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "".join(REPLY)},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": USAGE,
                    },
                )
        elif self.path == "/v1/embeddings":
            inputs = body.get("input", [])
            count = len(inputs) if isinstance(inputs, list) else 1
            self._json(
                200,
                {
                    "object": "list",
                    "model": model,
                    "data": [
                        {"index": i, "object": "embedding", "embedding": [0.1, 0.2, 0.3]}
                        for i in range(count)
                    ],
                    "usage": {"prompt_tokens": count, "total_tokens": count},
                },
            )
        elif self.path == "/v1/responses":
            self._json(
                200,
                {
                    "id": "resp_stub",
                    "object": "response",
                    "created_at": 1700000000,
                    "status": "completed",
                    "model": model,
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "".join(REPLY)}],
                        }
                    ],
                    "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
                },
            )
        else:
            self._not_found()

    def _sse(self, model: str, include_usage: bool) -> None:
        frames = [_chunk(model, {"role": "assistant", "content": REPLY[0]}, None)]
        frames.append(_chunk(model, {"content": REPLY[1]}, None))
        frames.append(_chunk(model, {}, "stop"))
        if include_usage:
            terminal = _chunk(model, {}, None)
            terminal["choices"] = []
            terminal["usage"] = USAGE
            frames.append(terminal)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for frame in frames:
            self.wfile.write(f"data: {json.dumps(frame)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"stub upstream listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
