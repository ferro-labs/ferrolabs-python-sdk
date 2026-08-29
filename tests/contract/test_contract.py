"""Contract tests against a real ai-gateway (see conftest.py and scripts/with-gateway.sh).

Every field the README's observability section names is asserted non-empty
here; if the gateway changes a header or body field, this suite goes red
before a user does.
"""

from __future__ import annotations

import re

import pytest

from ferrolabsai import (
    AsyncFerroClient,
    FerroAPIError,
    FerroAuthError,
    FerroClient,
    FerroNotFoundError,
    FerroPermissionError,
)

from .conftest import BASE_URL, CHAT_MODEL, EMBED_MODEL

HEX32 = re.compile(r"^[0-9a-f]{32}$")
MESSAGES = [{"role": "user", "content": "ping"}]


class TestProbes:
    def test_health(self, client: FerroClient):
        health = client.health()
        assert health["status"]
        assert health["version"]
        assert isinstance(health["providers"], list)

    def test_ready(self, client: FerroClient):
        ready = client.ready()
        assert ready["status"] == "ready", ready
        assert any(t["routable"] for t in ready["targets"])

    def test_live(self, client: FerroClient):
        assert client.live() == {"status": "ok"}

    def test_capabilities(self, client: FerroClient):
        caps = client.capabilities()
        assert "openai" in caps["providers"]
        assert set(caps["providers"]["openai"].values()) <= {"forward", "translate", "unsupported"}


class TestModels:
    def test_list_returns_enriched_model_info(self, client: FerroClient):
        models = client.models.list()
        by_id = {m.id: m for m in models}
        assert CHAT_MODEL in by_id and EMBED_MODEL in by_id
        chat = by_id[CHAT_MODEL]
        assert chat.owned_by == "openai" and chat.provider == "openai"
        assert chat.object == "model"
        assert isinstance(chat.created, int)
        assert isinstance(chat.capabilities, list)
        assert isinstance(chat.deprecated, bool)
        # Catalog enrichment (internal/handler/models.go) — present for a real OpenAI id.
        assert chat.mode == "chat"
        assert chat.context_window and chat.context_window > 0

    def test_filters_are_client_side(self, client: FerroClient):
        assert {m.owned_by for m in client.models.list(provider="openai")} == {"openai"}
        assert client.models.list(provider="no-such-provider") == []
        # The catalog is a union of live discovery and the static model catalog,
        # so more embedding ids than the stub's one show up.
        found = [m.id for m in client.models.search("EMBEDDING")]
        assert EMBED_MODEL in found and all("embedding" in m for m in found)
        assert client.models.retrieve(CHAT_MODEL).id == CHAT_MODEL

    def test_retrieve_never_reaches_upstream(self, client: FerroClient, stub_requests):
        before = len(stub_requests())
        client.models.retrieve(CHAT_MODEL)
        with pytest.raises(FerroNotFoundError) as exc_info:
            client.models.retrieve("no-such-model")
        assert exc_info.value.code == "model_not_found"
        assert exc_info.value.status_code == 404
        new = stub_requests()[before:]
        assert not [r for r in new if "/v1/models/" in r], new


class TestChat:
    def test_non_streaming_carries_gateway_metadata(self, client: FerroClient):
        response = client.chat.completions.create(model=CHAT_MODEL, messages=MESSAGES)
        assert response.content == "stub reply"
        assert response.model
        # README "Observability" table — every row asserted here.
        assert response.trace_id and HEX32.match(response.trace_id)
        assert response.provider == "openai"
        assert response.gateway_overhead_ms is not None and response.gateway_overhead_ms > 0
        assert response.usage is not None
        assert response.usage.prompt_tokens == 5
        assert response.usage.completion_tokens == 2
        assert response.usage.total_tokens == 7

    def test_streaming_carries_trace_id_and_terminal_usage(self, client: FerroClient):
        stream = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=MESSAGES,
            stream=True,
            stream_options={"include_usage": True},
        )
        assert stream.trace_id and HEX32.match(stream.trace_id)
        chunks = list(stream)
        assert chunks, "no chunks"
        text = "".join(c.choices[0].delta.content or "" for c in chunks if c.choices)
        assert text == "stub reply"
        assert all(c.trace_id == stream.trace_id for c in chunks)
        assert chunks[-1].usage is not None and chunks[-1].usage.total_tokens == 7
        assert stream.response.is_closed

    def test_streaming_usage_chunk_policy(self, client: FerroClient):
        # The gateway always requests usage upstream for metering and forwards the
        # terminal usage chunk unless the client explicitly opts out
        # (providers/openai/openai.go streamOptions, internal/streamwrap.Meter).
        default = list(
            client.chat.completions.create(model=CHAT_MODEL, messages=MESSAGES, stream=True)
        )
        assert default[-1].usage is not None and default[-1].usage.total_tokens == 7
        opted_out = list(
            client.chat.completions.create(
                model=CHAT_MODEL,
                messages=MESSAGES,
                stream=True,
                stream_options={"include_usage": False},
            )
        )
        assert opted_out and all(c.usage is None for c in opted_out)

    def test_embeddings(self, client: FerroClient):
        response = client.embeddings.create(model=EMBED_MODEL, input=["a", "b"])
        assert [d.index for d in response.data] == [0, 1]
        assert response.trace_id and HEX32.match(response.trace_id)

    def test_responses_create(self, client: FerroClient):
        response = client.responses.create(model=CHAT_MODEL, input="ping")
        assert response.id == "resp_stub"
        assert response.status == "completed"
        assert response.output[0]["content"][0]["text"] == "stub reply"
        assert response.trace_id and HEX32.match(response.trace_id)
        assert response.provider == "openai"

    def test_responses_id_routes_are_501_without_responses_target(self, client: FerroClient):
        with pytest.raises(FerroAPIError) as exc_info:
            client.responses.retrieve("resp_stub")
        assert exc_info.value.status_code == 501
        assert exc_info.value.code == "responses_not_configured"

    async def test_async_chat_and_stream(self, async_client: AsyncFerroClient):
        async with async_client:
            response = await async_client.chat.completions.create(
                model=CHAT_MODEL, messages=MESSAGES
            )
            assert response.content == "stub reply" and response.provider == "openai"
            stream = await async_client.chat.completions.create(
                model=CHAT_MODEL, messages=MESSAGES, stream=True
            )
            assert stream.trace_id and HEX32.match(stream.trace_id)
            chunks = [c async for c in stream]
            text = "".join(c.choices[0].delta.content or "" for c in chunks if c.choices)
            assert text == "stub reply"


class TestErrorEnvelope:
    def test_401(self):
        with FerroClient(api_key="fgw_" + "0" * 32, base_url=BASE_URL, max_retries=0) as bad:
            with pytest.raises(FerroAuthError) as exc_info:
                bad.models.list()
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "invalid_api_key"
        assert exc_info.value.request_id and HEX32.match(exc_info.value.request_id)

    def test_404_unknown_model(self, client: FerroClient):
        with pytest.raises(FerroNotFoundError) as exc_info:
            client.chat.completions.create(model="no-such-model", messages=MESSAGES)
        assert exc_info.value.code == "model_not_found"

    def test_403_read_only_scope(self, client: FerroClient):
        created = client.admin.keys.create(name="contract-read-only", scopes=["read_only"])
        try:
            with FerroClient(api_key=created.key, base_url=BASE_URL, max_retries=0) as ro:
                assert isinstance(ro.admin.keys.list(), list)
                with pytest.raises(FerroPermissionError) as exc_info:
                    ro.admin.keys.create(name="should-fail")
            assert exc_info.value.status_code == 403
            assert exc_info.value.code == "insufficient_scope"
        finally:
            client.admin.keys.delete(created.id)


class TestAdmin:
    def test_keys_lifecycle(self, client: FerroClient, admin_guard: str):
        created = client.admin.keys.create(name="contract-key", scopes=["admin"])
        assert created.key.startswith("fgw_")
        try:
            fetched = client.admin.keys.retrieve(created.id)
            assert fetched.id == created.id and fetched.active
            assert fetched.key and fetched.key != created.key and "..." in fetched.key
            assert (
                client.admin.keys.update(created.id, name="contract-key-2").name == "contract-key-2"
            )
            rotated = client.admin.keys.rotate(created.id)
            assert rotated.key.startswith("fgw_") and rotated.key != created.key
            client.admin.keys.revoke(created.id)
            assert client.admin.keys.retrieve(created.id).active is False
            assert any(k.id == created.id for k in client.admin.keys.list())
            assert "summary" in client.admin.keys.usage(limit=5)
        finally:
            client.admin.keys.delete(created.id)
        with pytest.raises(FerroNotFoundError):
            client.admin.keys.retrieve(created.id)

    def test_config_get(self, client: FerroClient):
        cfg = client.admin.config.get()
        assert any(t.get("virtual_key") == "openai" for t in cfg.targets)
        assert cfg.raw["strategy"] == cfg.strategy

    def test_logs_list_and_stats(self, client: FerroClient):
        response = client.chat.completions.create(model=CHAT_MODEL, messages=MESSAGES)
        logs = client.admin.logs.list(limit=20, model=CHAT_MODEL)
        assert any(e.get("trace_id") == response.trace_id for e in logs["data"]), logs
        # The master key is logged as "master-key:<hash>", not "none".
        key_id = logs["data"][0]["api_key_id"]
        assert key_id.startswith("master-key:")
        filtered = client.admin.logs.list(limit=5, stage="all", api_key_id=key_id)["data"]
        assert filtered and all(e["api_key_id"] == key_id for e in filtered)
        stats = client.admin.logs.stats(buckets=4)
        assert isinstance(stats, dict) and stats

    def test_providers_and_plugins(self, client: FerroClient):
        assert any(p.get("name") == "openai" for p in client.admin.providers.list())
        catalog = client.admin.providers.catalog()
        openai = next(p for p in catalog if p["id"] == "openai")
        assert openai["registered"] is True
        assert isinstance(client.admin.plugins.list(), list)
        assert any(p.get("name") for p in client.admin.plugins.catalog())

    def test_audit_list(self, client: FerroClient, admin_guard: str):
        created = client.admin.keys.create(name="contract-audit", scopes=["admin"])
        client.admin.keys.delete(created.id)
        audit = client.admin.audit.list(limit=50)
        assert audit["summary"]["total_entries"] >= 1
        assert any(e.get("actor_id") for e in audit["data"])
        action = audit["data"][0]["action"]
        assert all(e["action"] == action for e in client.admin.audit.list(action=action)["data"])

    def test_dashboard_and_health(self, client: FerroClient):
        assert client.admin.dashboard()
        assert client.admin.health()["status"]
