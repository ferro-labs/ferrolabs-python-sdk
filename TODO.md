# TODO — ferrolabsai v0.1.x Release Fixes

Items that **must ship** before promoting v0.1.0 as stable. All are bugs or
correctness issues discovered during the SDK audit.

---

## P0 — Must Fix (blocks GA)

### 1. Streaming error handling leaks raw httpx exceptions
- **Files:** `client.py:169-175`, `completions/async_resource.py:62-73`
- Both sync `_stream_request()` and async `_stream()` call
  `response.raise_for_status()` directly, which raises raw
  `httpx.HTTPStatusError` instead of mapped `FerroAuthError`,
  `FerroRateLimitError`, etc.
- Wrap the `raise_for_status()` call in a `try/except` and route through
  `_raise_api_error()` so streaming and non-streaming paths have identical
  error behaviour.

### 2. Async `Completions.create()` missing `route_tag`, `frequency_penalty`, `presence_penalty`
- **File:** `completions/async_resource.py:16-53`
- Sync `Completions.create()` has `route_tag`, `frequency_penalty`, and
  `presence_penalty` parameters; async is missing all three.
- Copy the missing params and the `x_route_tag` body assignment from the sync
  version.

### 3. BYOC `http_client` ignores auth headers
- **File:** `client.py:91-95`
- When users pass their own `httpx.Client`, the SDK stores it directly but
  never merges `Authorization`, `Content-Type`, or `User-Agent` headers.
- Fix: either `http_client.headers.update(self._default_headers)` or document
  that BYOC users must set headers themselves (and add a test proving it).

---

## P1 — Should Fix (before v0.2.0)

### 4. `AsyncFerroClient` missing `images`, `models`, `admin` namespaces
- **File:** `client.py:259-262`
- Only `chat` and `embeddings` are wired on the async client.
- Users calling `client.models.list()` or `client.admin.health()` on
  `AsyncFerroClient` get `AttributeError` at runtime.
- Add async variants for the simple request/response resources (images,
  models, admin) or share the sync resource classes with async `_request`.

### 5. `AsyncFerroClient` missing `http_client` parameter
- **File:** `client.py:224-231`
- Sync client accepts `http_client: httpx.Client | None`; async doesn't
  accept `http_client: httpx.AsyncClient | None`.
- Add the parameter to parity with sync.

### 6. Verify `route_tag` / `template_id` wire format against gateway
- **File:** `completions/resource.py:121`
- SDK sends `body["x_route_tag"]` but no reference to `x_route_tag`,
  `route_tag`, or `template_id` was found in the `ai-gateway` Go codebase.
- Confirm with the gateway team whether these are implemented and what field
  names the gateway expects. Update the SDK or add a note if they're planned
  features.

### 7. `_raise_api_error` never populates `request_id`
- **File:** `client.py:308-334`
- `FerroAPIError` has a `request_id` field but it's always `None`.
- Read `x-request-id` from the response headers or `request_id` / `trace_id`
  from the body and pass it through.

### 8. CHANGELOG says Python 3.8; pyproject.toml says 3.9
- **File:** `CHANGELOG.md:29`
- Fix: change "Python 3.8–3.12" → "Python 3.9–3.12".

### 9. Ruff config uses deprecated top-level `select`
- **File:** `pyproject.toml:58`
- Move `select = [...]` under `[tool.ruff.lint]` to silence the deprecation
  warning.

---

## P2 — Nice to Have (v0.2.0+)

### 10. Add retry backoff
- **File:** `client.py:140-167`
- Currently retries fire immediately. Add simple exponential backoff
  (e.g. `time.sleep(0.5 * attempt)`).

### 11. Single-source version
- **Files:** `pyproject.toml:7`, `__init__.py:109`, `client.py:183`
- Version is duplicated in three places. Use `importlib.metadata` as the
  single source or a `hatch-vcs` / `hatch-regex` plugin.

### 12. Add `py.typed` marker (PEP 561)
- Downstream consumers won't get type information without this file.
- Create an empty `ferrolabsai/py.typed` and add it to the wheel.

---

## How to Use This File

Check off items as they're completed:
```
### 1. ~~Streaming error handling leaks raw httpx exceptions~~ ✅ (PR #XX)
```

Move items between priority tiers if scope changes.
