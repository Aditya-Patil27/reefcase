# Story 4.1: Tool framework and result cache

## Story (verbatim from `epics.md`)

### Story 4.1: Tool framework and result cache

As the agent,
I want tools with typed params that persist every result,
So that each piece of evidence has an ID to cite (FR8, FR10).

- Owner: B · Priority: P0 · Depends on: 1.4
- Files: `src/reefcase/tools/{http,registry}.py`, `src/reefcase/store/migrations/005_tool_results.sql`, `tests/tools/test_registry.py`
- Done when: gate passes

**Acceptance Criteria:**

**Given** a tool called twice with the same params
**When** the second call runs
**Then** it returns the stored `ToolResult` with the same `tr_…` ID and makes no HTTP request

**Given** `GET /api/tool-results/{id}`
**When** called
**Then** it returns that `ToolResult`

## Files (lead's decision — extended to satisfy the ACs)

The two ACs need storage, a repo and an HTTP route, which the verbatim `Files`
line does not list. These additions are **additive only**; no existing file is
restructured.

| File | Change |
|---|---|
| `src/reefcase/store/migrations/005_tool_results.sql` | new — the `tool_results` table + cache index |
| `src/reefcase/tools/http.py` | new — `ToolContext`, `build_client`, `get_json` |
| `src/reefcase/tools/registry.py` | new — `ToolParams`, `ToolSpec`, `ToolRegistry`, `canonical_params`, `registry`, `call_tool` |
| `src/reefcase/store/repos.py` | **add** `ToolResultRepo` (do not touch the existing repos) |
| `src/reefcase/store/db.py` | **add** `self.tool_results = ToolResultRepo(self)` in `Store.__init__` |
| `src/reefcase/api/routes/tool_results.py` | new — `GET /api/tool-results/{tool_result_id}` |
| `src/reefcase/api/main.py` | **add** `app.include_router(tool_results.router, prefix="/api")` |
| `tests/tools/test_registry.py` | new — AC 1 + framework tests |
| `tests/api/test_tool_results.py` | new — AC 2 |

No new dependency: `httpx>=0.28.1` is already in `pyproject.toml`.

## Architecture (frozen — §4, §5.4, §6.3, §6.4)

### §4.1 IDs
`tr_…` is the tool-result prefix; `new_id(TOOL_RESULT)` already exists in
`reefcase.core.ids`. All ids come from there — never hand-build one.

### §4.2 Schema (already implemented in `reefcase.core.schemas` — do not edit)
```python
class ToolResult(BaseModel): id; tool: str; params: dict; data: dict; source_url: str; retrieved_at
```
`params` and `data` are `dict[str, Any]`, `retrieved_at` is `AwareDatetime`.

### §5.4 Tools — exact interface (verbatim)
> Each tool is an async function `(params: XParams, ctx: ToolContext) -> ToolResult`,
> where `ToolContext` holds the `httpx.AsyncClient`, the store and the settings.
> `registry.py` exposes them to the agent. Every result is persisted and cached:
> the key is `(tool, canonical JSON params)` and cache hits return the stored `ToolResult`.

Also from §5.4 that later stories rely on (not built here): `vessel_activity` holds a
process-wide `asyncio.Semaphore(1)`; `reef_map`/`mpa_boundary` make no network calls.

### §6.3 HTTP API (verbatim row)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/tool-results/{id}` | `ToolResult` |

### §6.4 Storage
One DuckDB file, numbered SQL migrations applied in order and tracked in
`schema_migrations`, each story adds only the tables it needs, all writes
through the single `Store` connection guarded by its `asyncio.Lock`. Every
repo goes through `Store.execute`/`fetch*` — no repo touches the connection
directly and none nests `locked()`.

## Signatures to implement

```python
# src/reefcase/tools/http.py
DEFAULT_TIMEOUT_S: float = 30.0
USER_AGENT: str = "reefcase/0.1"

@dataclass(slots=True)
class ToolContext:
    http: httpx.AsyncClient
    store: Store
    settings: Settings

def build_client() -> httpx.AsyncClient:
    """An AsyncClient with DEFAULT_TIMEOUT_S and USER_AGENT."""

async def get_json(
    ctx: ToolContext, url: str, params: Mapping[str, Any] | None = None
) -> Any:
    """GET url, return the decoded JSON body.

    Raises ExternalServiceError (reefcase.core.errors) on a non-2xx status
    (status_code, url, retry_after from the Retry-After header when present)
    and on httpx.HTTPError. Never raises httpx's own exception types out.
    """
```

```python
# src/reefcase/tools/registry.py
class ToolParams(BaseModel):
    """Base for every tool's params model; unknown fields are an error."""
    model_config = ConfigDict(extra="forbid")

ToolFn = Callable[[Any, ToolContext], Awaitable[ToolResult]]

@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    params_type: type[ToolParams]
    fn: ToolFn
    description: str = ""

def canonical_params(params: BaseModel) -> str:
    """json.dumps(params.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))"""

class ToolRegistry:
    def register(self, spec: ToolSpec) -> ToolSpec: ...
    def spec(self, name: str) -> ToolSpec: ...          # ToolError when unknown
    def names(self) -> list[str]: ...                    # sorted
    async def call(
        self, name: str, params: ToolParams | Mapping[str, Any], ctx: ToolContext
    ) -> ToolResult: ...

registry = ToolRegistry()

def tool(name: str, params_type: type[ToolParams], *, description: str = "") -> Callable[[ToolFn], ToolFn]:
    """Decorator: register fn under name and return it unchanged."""

async def call_tool(
    name: str, params: ToolParams | Mapping[str, Any], ctx: ToolContext
) -> ToolResult:
    """registry.call(...)"""
```

`ToolRegistry.call` behaviour, in order:
1. `spec = self.spec(name)` (unknown → `ToolError`).
2. Validate: a `ToolParams` instance is re-validated through `spec.params_type`
   (so a foreign model or extra field is a `pydantic.ValidationError`);
   a mapping goes through `spec.params_type.model_validate(...)`.
3. `key = canonical_params(validated)`; `hit = await ctx.store.tool_results.find(name, key)`;
   if `hit is not None`, return it **without calling `spec.fn`** (AC 1: no HTTP).
4. `result = await spec.fn(validated, ctx)`.
5. Enforce `result.tool == name` and `result.params == validated.model_dump(mode="json")`
   (else `ToolError`), then `await ctx.store.tool_results.save(result, key)`.
6. Return `result`.

```python
# src/reefcase/store/repos.py  (additive)
class ToolResultRepo:
    def __init__(self, store: Store) -> None: ...
    async def save(self, result: ToolResult, params_key: str) -> None:
        """INSERT ... ON CONFLICT (tool, params_key) DO NOTHING."""
    async def get(self, tool_result_id: str) -> ToolResult:
        """The result, or NotFoundError."""
    async def find(self, tool: str, params_key: str) -> ToolResult | None: ...
```

```sql
-- src/reefcase/store/migrations/005_tool_results.sql
CREATE TABLE IF NOT EXISTS tool_results (
    id VARCHAR PRIMARY KEY,
    tool VARCHAR NOT NULL,
    params_key VARCHAR NOT NULL,   -- canonical JSON of params (the cache key half)
    params VARCHAR NOT NULL,       -- JSON object, as validated
    data VARCHAR NOT NULL,         -- JSON object the tool returned
    source_url VARCHAR NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS tool_results_cache_idx ON tool_results (tool, params_key);
```

```python
# src/reefcase/api/routes/tool_results.py
router = APIRouter()

@router.get("/tool-results/{tool_result_id}", response_model=ToolResult)
async def get_tool_result(tool_result_id: str, request: Request) -> ToolResult:
    """Return the stored result, or 404 (NotFoundError → HTTPException)."""
```

## Tasks (tests first)

1. `tests/tools/test_registry.py`:
   - [ ] **AC 1, no HTTP:** register a fake tool whose body calls `get_json` through
     an `httpx.MockTransport` that counts requests and returns `{"ok": true}`.
     Call it twice with the same params; assert the two results are equal, the
     returned id starts with `tr_`, the transport saw **one** request, and the
     fake's own counter is 1.
   - [ ] **Canonical key:** `{"site_id": ..., "start": ..., "end": ...}` in two
     different insertion orders hits the cache (one tool invocation).
   - [ ] **Different params miss:** a changed `end` produces a second call, a
     different `tr_` id, and two rows in `store.tool_results`.
   - [ ] **Persistence:** after a call, `await store.tool_results.get(result.id)`
     round-trips equal (params/data/source_url/retrieved_at), and `find(tool, key)`
     returns the same row.
   - [ ] **Unknown tool** → `ToolError`; **foreign params model / extra field** →
     `ValidationError`; **`result.tool` mismatch** → `ToolError`.
   - [ ] **`get_json` error mapping:** `MockTransport` returning 500 (with and
     without `Retry-After`) → `ExternalServiceError` carrying `status_code`/`url`/
     `retry_after`; a transport raising `httpx.ConnectError` → `ExternalServiceError`.
   - [ ] **`canonical_params`** is order-independent and stable for nested dicts.
2. `tests/api/test_tool_results.py` (follow `tests/api/test_upload.py`):
   - [ ] Build the app with `create_app(make_settings(data_dir=..., segmenter="fake"))`,
     persist a result through `app.state.store.tool_results.save(...)`, then
     `GET /api/tool-results/{id}` with `httpx.ASGITransport` → 200 and a body equal
     to `result.model_dump(mode="json")`.
   - [ ] Unknown id → 404.
3. Write `migrations/005_tool_results.sql`, then `ToolResultRepo` + `Store.__init__` wiring.
4. Write `tools/http.py`, then `tools/registry.py`.
5. Write `api/routes/tool_results.py` and include the router in `create_app`.
6. `uv run poe gate` until green.

## Lessons (from `ops/*/learnings.md`, relevant here)

- [test] (2-1) **RULE:** Under `httpx.ASGITransport`, FastAPI's lifespan does not run,
  so build the app with `create_app(...)` and read `app.state.store` — never rely on
  a lifespan-created store. WHY: a lifespan-only store made every ASGI request hit
  `AttributeError: app.state.store`.
- [test] (1-4) **RULE:** async tests need `pytest-asyncio` and an explicit
  `@pytest.mark.asyncio` on each `async def test_…`; do not edit
  `[tool.pytest.ini_options]`. WHY: strict mode works unconfigured on pytest 9.1.1,
  and the ini block is gate config a story may not loosen.
- [python] (1-2) **RULE:** a pydantic field with a container default uses
  `Field(default_factory=list[Foo])`, not bare `list`, or pyright strict infers
  `list[Unknown]` and fails the gate.
- [store] (1-4) **RULE:** every `Store.open` bootstraps spatial with
  `INSTALL AND LOAD spatial;` and `TIMESTAMPTZ` needs `pytz` (already a dependency);
  a new migration therefore only adds its own table and must not touch the bootstrap.
- [python] (2-1) **RULE:** set `PYTHONIOENCODING=utf-8` when running `uv run poe gate`
  on this Windows box. WHY: import-linter's rich spinner crashes under cp1252 and
  the crash looks like a gate failure.
- [python] (1-1, 1-2) **RULE:** never narrow the gate command and never edit frozen
  files; ruff excludes `planning`, `web`, `ml`, `var`, `.scratch` already.

## Library check

Call sites and their confirmed usage at the pinned versions (architecture §10):

- `httpx>=0.28.1` — `httpx.AsyncClient(timeout=..., headers={"User-Agent": ...})`,
  `httpx.MockTransport(handler)` as `AsyncClient(transport=...)`, and
  `httpx.ASGITransport(app=app)` (async-only). `response.raise_for_status()` is
  sync `httpx.HTTPStatusError`; check `response.is_success` and read
  `response.headers.get("Retry-After")` yourself so the error carries `retry_after`.
- `pydantic` v2 — `BaseModel.model_validate(...)`, `model_dump(mode="json")`,
  `ConfigDict(extra="forbid")`, `model_copy`. No research needed; the repo already
  uses all of these.
- `duckdb>=2.0.0` — `VARCHAR` JSON columns are written as `json.dumps(...)` strings
  (the `events` table already does this). `TIMESTAMPTZ` columns read back as
  tz-aware datetimes; pass `datetime.now(UTC)` (pytz present).
- `fastapi>=0.162.0` — `APIRouter`, `response_model=ToolResult`, `Request`, and
  `HTTPException(status_code=404)` on `NotFoundError`, exactly as
  `api/routes/surveys.py` does.

No new package, no cassette, no live call. Nothing here needs the `researcher`.
