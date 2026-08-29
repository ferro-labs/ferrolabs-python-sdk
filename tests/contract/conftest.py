"""Contract-suite fixtures. Everything here talks to a real ai-gateway.

Set by ``scripts/with-gateway.sh``:
    FERRO_CONTRACT_BASE_URL    gateway URL (e.g. http://127.0.0.1:18080)
    FERRO_CONTRACT_MASTER_KEY  the gateway's MASTER_KEY (admin bearer)
    FERRO_CONTRACT_STUB_URL    the stub upstream (optional; enables the
                               "never reached upstream" assertions)

Without FERRO_CONTRACT_BASE_URL the whole directory is skipped, so the plain
``pytest`` run stays offline.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest

from ferrolabsai import AsyncFerroClient, FerroClient

BASE_URL = os.environ.get("FERRO_CONTRACT_BASE_URL")
MASTER_KEY = os.environ.get("FERRO_CONTRACT_MASTER_KEY", "")
STUB_URL = os.environ.get("FERRO_CONTRACT_STUB_URL")

CHAT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if BASE_URL:
        return
    skip = pytest.mark.skip(reason="FERRO_CONTRACT_BASE_URL not set (run scripts/with-gateway.sh)")
    for item in items:
        if "tests/contract" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def client() -> Iterator[FerroClient]:
    with FerroClient(api_key=MASTER_KEY, base_url=BASE_URL, max_retries=0) as c:
        yield c


@pytest.fixture(scope="session")
def admin_guard(client: FerroClient) -> Iterator[str]:
    """The gateway refuses to revoke/delete the last admin *record* (409) — the
    MASTER_KEY is not a record — so tests that delete admin keys need one
    extra admin key parked for the whole session."""
    key_id = client.admin.keys.create(name="contract-guard", scopes=["admin"]).id
    try:
        yield key_id
    finally:
        try:
            client.admin.keys.delete(key_id)
        except Exception:
            pass  # teardown must never mask a test failure


@pytest.fixture
async def async_client() -> AsyncFerroClient:
    return AsyncFerroClient(api_key=MASTER_KEY, base_url=BASE_URL, max_retries=0)


@pytest.fixture
def stub_requests():
    """Callable returning the stub upstream's request log (``["GET /v1/models", ...]``)."""
    if not STUB_URL:
        pytest.skip("FERRO_CONTRACT_STUB_URL not set")

    def _read() -> list[str]:
        return list(httpx.get(f"{STUB_URL}/_requests", timeout=5).json()["data"])

    return _read
