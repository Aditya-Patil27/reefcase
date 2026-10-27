# Story 1.4: Store foundation

Owner: Opus (lead-b) · Priority: P0 · Depends on: 1.2 · Status: in-progress

## Story (verbatim from epics.md)

As a developer,
I want a DuckDB store with migrations, repos and blob paths,
So that every stage persists through one writer.

- Owner: Opus · Priority: P0 · Depends on: 1.2
- Files: `src/reefcase/store/{db,repos,blobs}.py`, `src/reefcase/store/migrations/001_sites_surveys_events.sql`, `tests/store/test_store.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** an empty data dir
**When** `Store.open(path)` runs
**Then** migrations are applied once, the spatial extension is loaded, and `schema_migrations` lists `001`

**Given** a site and a survey
**When** saved and re-read via the repos
**Then** they equal the originals

**Given** two concurrent writes
**When** issued through `Store`
**Then** both succeed (serialized by the lock)

## Architecture sections this story touches

### §6.4 — Storage (`store/`) — the contract for this story

> - One DuckDB file, with the `spatial` extension loaded on connect.
> - Migrations are numbered SQL files in `store/migrations/`, applied in order at startup and
>   tracked in `schema_migrations`.
> - Each story adds only the tables it needs.
> - Blobs go to `var/blobs/{survey_id}/frames/{frame_id}.jpg`, `…/masks/{frame_id}.png` and
>   `…/video.<ext>`.
> - DuckDB has a single writer. All writes go through one `Store` object holding one connection
>   guarded by an `asyncio.Lock`.

Also relevant, §6.2 (written by Story 2.2, but it fixes this story's event column shape): "`publish(event)`
persists the event to the `events` table first, then fans it out to live subscribers.
`subscribe(survey_id, after_seq)` yields stored events after `after_seq`, then live ones. So SSE
reconnects … replay without gaps."

### §3 — Repository layout, layering (constraint)

```
api, bot ──► pipeline ──► agent ──► tools, llm ──► store ──► core
                     └──► vision, ingest ─────────► store ──► core
```

- `store/` imports `reefcase.core` only (schemas, events, ids, errors) plus `duckdb`. It must **not**
  import `reefcase.pipeline`, `agent`, `tools`, `llm`, `vision`, `ingest`, `api` or `bot`.
- `src/reefcase/core/` is **frozen**: this story must not touch `schemas.py`, `events.py`, `ids.py`,
  `config.py` or `errors.py`. If something there seems to need a change, stop and report it — that
  is a blocker, not an edit.
- Layout (§3): `store/` = `db.py`, `migrations/*.sql`, `repos.py`, `blobs.py`. Runtime data lives in
  `var/` (`var/reefcase.duckdb`, `var/blobs/`), git-ignored.

### §4.1 / §4.2 / §4.3 — the types that cross the store boundary

- `ids.py`: ids are prefixed ULIDs (`site_…`, `srv_…`, `frm_…`, `tr_…`, `inv_…`) — plain strings here.
- `schemas.py` (as implemented by Story 1.2, read it before writing repos):
  `Site{id,name,location:GeoPoint,mpa_id:str|None,created_at}`, `Survey{id,site_id,dive_date:date,
  status:SurveyStatus,source:Literal["upload","bot","historical"],video_path:str|None,
  cover:dict[SegClass,float]|None,failure_reason:str|None,created_at}`,
  `QualityScore`, `Frame`, `Segmentation`, `FrameAssessment`, `EvidenceRef`, `ToolResult`, `Finding`,
  `Hypothesis`, `Investigation`. `created_at` is an `AwareDatetime`; `cover` is keyed by `SegClass`.
- `events.py`: `Event` is a discriminated union on `type`; every event has `survey_id`, `seq: int >= 1`
  and an aware `ts`. Parse with `EventAdapter`, never with per-class guessing.

### §4.4 — `REEFCASE_DATA_DIR`

`Settings.data_dir: Path`, default `var/`. The store is opened with it (`Store.open(settings.data_dir)`)
— **no new environment variable** is introduced by this story.

### §10 — pinned toolchain

`duckdb 2.0.0` ("spatial does not autoload: `INSTALL spatial; LOAD spatial;`"). Testing strategy §11:
"store — Temp-dir DuckDB per test".

## Contract notes / decisions (do not deviate)

1. **`Store.open(path)` takes the data *directory*.** The AC says "given an empty data dir, when
   `Store.open(path)` runs", so `path` is `REEFCASE_DATA_DIR` (a directory, created if missing). The
   DB file is `<data_dir>/reefcase.duckdb` and the blob root is `<data_dir>/blobs` — exactly the two
   artifacts §3 puts in `var/`. Do **not** take a `.duckdb` file path.
2. **One connection, one `asyncio.Lock`, reads and writes both through it.** `Store` owns the only
   `duckdb.DuckDBPyConnection`; `locked()` is an `@asynccontextmanager` that holds an `asyncio.Lock`
   for the whole body. `execute`/`executemany`/`fetchall`/`fetchone` all go through it (serialising
   reads is harmless — the DB is local and every query is microseconds). Repos never touch the
   connection directly and never nest `locked()`.
3. **The store API is async** (`await store.sites.save(site)`, `await store.surveys.get(id)`), because
   §6.4 mandates the `asyncio.Lock` and API/pipeline callers are async. `Store.open`/`close` stay
   synchronous.
4. **`duckdb.Error` never escapes `store/`.** Wrap every `duckdb.Error` in
   `reefcase.core.errors.StoreError` (chained with `from exc`). Unknown ids raise
   `reefcase.core.errors.NotFoundError` from the repos, not `KeyError`.
5. **Timestamps are UTC-aware.** Open the connection with `config={"TimeZone": "UTC"}` and store
   `created_at`/`ts` as `TIMESTAMPTZ`. Python's `pytz` must be a runtime dependency or **fetching any
   TIMESTAMPTZ raises `InvalidInputException: Required module 'pytz' failed to import`** (verified,
   see Library check). Round-trip equality is by instant, so an input `+05:30` datetime compares equal
   to the UTC value returned.
6. **JSON payloads are `VARCHAR` columns of JSON text**, encoded with `json.dumps` and decoded with
   `json.loads` in the repo (`Survey.cover`, the event payload). Do not use DuckDB's `JSON` type: it
   only brings extra type coercion at the boundary and still returns `str`. Column names must avoid
   DuckDB keywords — `at`, `type`… **`at` is a reserved word in 2.0** (`Parser Error: syntax error at
   or near "at"`); use `ts`. (`type`, `data`, `seq`, `status`, `source` are all fine — verified.)
7. **Blob references stored in schemas are data-dir-relative POSIX strings**, e.g.
   `blobs/srv_01J…/frames/frm_01J….jpg`. Absolute paths would break the Docker/Fly seed from
   `data/demo/` (§12). `Blobs` builds absolute `Path`s for I/O and converts with `ref()`/`resolve()`;
   `resolve()` rejects anything that escapes the data dir.
8. **Spatial is bootstrapped on every connection** with the 2.0 one-liner `INSTALL AND LOAD spatial;`
   and verified via `duckdb_extensions()`. It is *not* bundled in the wheel and *not* autoloadable, so
   the first run downloads it into `~/.duckdb/extensions/…` (that needs network once; see handoff).
   Do not swallow the failure: raise `StoreError` naming the extension.
9. **`pytest-asyncio` in strict mode with an explicit `@pytest.mark.asyncio` per async test.** It is
   added as a dev dependency only; **do not edit `[tool.pytest.ini_options]`** (the gate config is not
   this story's to change). With `pytest-asyncio 1.4.1` the marker alone works on pytest 9.1.1 —
   verified, no `asyncio_mode` needed.
10. **`tests/conftest.py` is Story 1.5's file — do not create it.** Use a module-local fixture in
    `tests/store/test_store.py`.

## Exact shape to implement

### `src/reefcase/store/db.py`

```python
"""One DuckDB file, migrations, and the single writer (architecture §6.4)."""

import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import duckdb

from reefcase.core.errors import StoreError

DB_FILENAME = "reefcase.duckdb"
MIGRATIONS_DIR = Path(__file__).with_name("migrations")
SPATIAL_BOOTSTRAP = "INSTALL AND LOAD spatial;"
#: ``schema_migrations`` is created by code, not by a migration, so 001 is the first row.
_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL
);
"""

class Store:
    """The only writer to the DuckDB file, serialised by one asyncio lock."""

    def __init__(self, data_dir: Path, connection: duckdb.DuckDBPyConnection) -> None: ...

    @classmethod
    def open(cls, data_dir: Path | str, *, migrations_dir: Path | str | None = None) -> Store:
        """Open (or create) ``<data_dir>/reefcase.duckdb``, load spatial, apply migrations."""

    @property
    def data_dir(self) -> Path: ...
    @property
    def db_path(self) -> Path: ...
    @property
    def blobs(self) -> Blobs: ...       # from .blobs
    @property
    def sites(self) -> SiteRepo: ...    # from .repos, cached on the instance
    @property
    def surveys(self) -> SurveyRepo: ...
    @property
    def events(self) -> EventRepo: ...

    @asynccontextmanager
    async def locked(self) -> AsyncGenerator[duckdb.DuckDBPyConnection]: ...

    async def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> None: ...
    async def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None: ...
    async def fetchall(
        self, sql: str, parameters: Sequence[Any] | None = None
    ) -> list[tuple[Any, ...]]: ...
    async def fetchone(
        self, sql: str, parameters: Sequence[Any] | None = None
    ) -> tuple[Any, ...] | None: ...

    def close(self) -> None: ...
    def __enter__(self) -> Store: ...   # ``with Store.open(...) as store:``
    def __exit__(self, *exc_info: object) -> None: ...
```

Behaviour:
- `open`: `data_dir = Path(data_dir)`; raise `StoreError` when it exists and is not a directory;
  `mkdir(parents=True, exist_ok=True)`; `duckdb.connect(str(data_dir / DB_FILENAME), config={"TimeZone": "UTC"})`;
  run `SPATIAL_BOOTSTRAP`, then assert `SELECT loaded FROM duckdb_extensions() WHERE extension_name = 'spatial'`
  returns `(True,)`; execute `_SCHEMA_MIGRATIONS_DDL`; apply migrations; build the `Store`. Any
  `duckdb.Error` → `StoreError`.
- migrations: `sorted(migrations_dir.glob("*.sql"))`; `version = path.stem.split("_")[0]` (so
  `001_sites_surveys_events.sql` → `"001"`); skip versions already in `schema_migrations`; otherwise
  `BEGIN` → the whole file in one `execute()` (multi-statement execute is supported and `--` comments
  and trailing semicolons are fine — verified) → `INSERT INTO schema_migrations VALUES (?, ?)` with
  `datetime.now(UTC)` → `COMMIT`; on error `ROLLBACK` and raise `StoreError`. Ordering and
  applied-once are both observable in `schema_migrations`.
- `fetchone` may be implemented directly with `fetchone()` (verified safe, no
  `ResourceInUseException` in 2.0 for this pattern) or via `fetchall`; either is acceptable.
- `close` must be idempotent and must not raise.

### `src/reefcase/store/repos.py`

```python
class SiteRepo:
    def __init__(self, store: Store) -> None: ...
    async def save(self, site: Site) -> None: ...          # upsert on id
    async def get(self, site_id: str) -> Site: ...         # NotFoundError when absent
    async def list(self) -> list[Site]: ...                # ordered by id

class SurveyRepo:
    def __init__(self, store: Store) -> None: ...
    async def save(self, survey: Survey) -> None: ...      # upsert on id
    async def get(self, survey_id: str) -> Survey: ...     # NotFoundError when absent
    async def list(self) -> list[Survey]: ...              # ordered by id
    async def by_site(self, site_id: str) -> list[Survey]: ...   # ordered by dive_date, id

class EventRepo:
    def __init__(self, store: Store) -> None: ...
    async def append(self, event: Event) -> None: ...      # INSERT; duplicate (survey_id, seq) -> StoreError
    async def next_seq(self, survey_id: str) -> int: ...   # coalesce(max(seq), 0) + 1
    async def list(self, survey_id: str, after_seq: int = 0) -> list[Event]: ...  # seq ascending, seq > after_seq
```

- `save` uses `INSERT … ON CONFLICT (id) DO UPDATE SET …` (verified working in 2.0).
- Reading rebuilds the pydantic model **field by field** (`Site(id=row[0], name=row[1],
  location=GeoPoint(lat=row[2], lon=row[3]), mpa_id=row[4], created_at=row[5])`) — never
  `Site.model_validate(row)`; column order is in the SELECT list, spelled out in the query.
- `Survey.cover` is `json.dumps({key.value: value for key, value in cover.items()})` on the way in and
  `{SegClass(key): value for key, value in json.loads(raw).items()}` on the way out; `None` stays `NULL`.
- `EventRepo.append`: `payload = event.model_dump(mode="json")`; strip `survey_id`, `seq`, `ts`, `type`;
  store those four in their own columns and `json.dumps(payload)` in `data`; bind `event.ts` (a
  datetime) directly to the `TIMESTAMPTZ` column.
- `EventRepo.list`: `EventAdapter.validate_python({"survey_id": …, "seq": …, "ts": row_ts,
  "type": …, **json.loads(data)})`.
- Every SQL string that a repo writes stays inline in `repos.py`; no string building from user input
  (all values are `?` parameters).

### `src/reefcase/store/blobs.py`

```python
BLOBS_DIRNAME = "blobs"

class Blobs:
    """Paths and bytes under ``<data_dir>/blobs`` (architecture §6.4)."""

    def __init__(self, data_dir: Path) -> None: ...
    @property
    def root(self) -> Path: ...                                   # <data_dir>/blobs
    def survey_dir(self, survey_id: str) -> Path: ...             # <root>/<survey_id>
    def frame_path(self, survey_id: str, frame_id: str) -> Path: ...   # …/frames/<frame_id>.jpg
    def mask_path(self, survey_id: str, frame_id: str) -> Path: ...    # …/masks/<frame_id>.png
    def video_path(self, survey_id: str, suffix: str = ".mp4") -> Path: ...  # …/video<.ext>
    def ref(self, path: Path) -> str: ...                         # data-dir-relative POSIX string
    def resolve(self, ref: str) -> Path: ...                      # inverse of ref(); StoreError if it escapes
    def save_frame(self, survey_id: str, frame_id: str, data: bytes) -> str: ...   # returns ref
    def save_mask(self, survey_id: str, frame_id: str, data: bytes) -> str: ...    # returns ref
    def save_video(self, survey_id: str, data: bytes, suffix: str = ".mp4") -> str: ...  # returns ref
    def read(self, ref: str) -> bytes: ...
```

- `suffix` is normalised to a leading dot and lower-cased; `save_video` for an upload writes
  `blobs/<survey_id>/video.mp4` (Story 2.1's AC).
- `save_*` create parent directories, write bytes, return `ref(path)`.
- `resolve`: `(self.data_dir / ref).resolve()` must be inside `self.data_dir.resolve()`
  (`Path.is_relative_to`), else `raise StoreError(f"blob path escapes the data dir: {ref}")`.

### `src/reefcase/store/migrations/001_sites_surveys_events.sql`

```sql
-- 001: sites, surveys and the event log (architecture §4.2, §4.3, §6.2, §6.4).
-- ``schema_migrations`` itself is created by ``store/db.py`` before any migration runs.

CREATE TABLE IF NOT EXISTS sites (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    lat DOUBLE NOT NULL,
    lon DOUBLE NOT NULL,
    mpa_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS surveys (
    id VARCHAR PRIMARY KEY,
    site_id VARCHAR NOT NULL,
    dive_date DATE NOT NULL,
    status VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    video_path VARCHAR,
    cover VARCHAR,              -- JSON object: class -> fraction (§4.2)
    failure_reason VARCHAR,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    survey_id VARCHAR NOT NULL,
    seq INTEGER NOT NULL,
    type VARCHAR NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    data VARCHAR NOT NULL,       -- JSON payload, the §4.3 fields minus survey_id/seq/ts/type
    PRIMARY KEY (survey_id, seq)
);
```

No other tables (frames = `003_frames.sql` in Story 2.3, the events index = `002_events_index.sql` in
Story 2.2). Do not add columns "for later".

### `pyproject.toml` / dependencies

- `uv add "duckdb>=2.0.0" pytz` (runtime) and `uv add --dev "pytest-asyncio>=1.4.1"`.
- Nothing else: no `pyarrow`, no `pandas`, no `sqlalchemy`, no ini/config edits.

## Tasks (tests first, then code)

1. `uv add "duckdb>=2.0.0" pytz` and `uv add --dev "pytest-asyncio>=1.4.1"`; commit `uv.lock` with the
   change batch. Confirms `duckdb==2.0.0` resolves (no cp314 wheel needed: 2.0 ships `cp312-abi3`).
2. `tests/store/test_store.py` — write it **before** `store/db.py` exists. Module-local fixture:
   ```python
   @pytest.fixture
   def data_dir(tmp_path: Path) -> Path:
       return tmp_path / "var"          # does not exist yet: the AC starts from an empty data dir
   ```
   and a `open_store(data_dir)` helper returning `Store.open(...)`. Every async test gets
   `@pytest.mark.asyncio` and `-> None`/typed returns (pyright checks tests in `standard` mode).
   1. AC 1 — `test_open_creates_db_applies_001_and_loads_spatial`: `Store.open(data_dir)` on a
      non-existent dir creates `data_dir/reefcase.duckdb`; `schema_migrations` has exactly one row and
      its version is `"001"`; `SELECT extension_name FROM duckdb_extensions() WHERE loaded` contains
      `"spatial"`.
   2. AC 1 — `test_migrations_run_once`: capture `applied_at`; `close()`; `Store.open(data_dir)` again;
      still one `001` row with the *same* `applied_at`; a site written before the reopen is still
      readable (the file, not an in-memory DB, is reused).
   3. AC 1 — `test_migrations_apply_in_order_and_record_prefixes`: `Store.open(data_dir,
      migrations_dir=<tmp dir with 001_a.sql, 002_b.sql created by the test>)`; both versions are
      listed in `schema_migrations`; reopening adds nothing; a broken migration raises `StoreError`
      **and** leaves no row for that version (rolled back).
   4. AC 2 — `test_site_round_trips`: a `Site` with `mpa_id=None` and a `+05:30` `created_at` saved
      then `get` → `==` the original; `list()` contains it; `mpa_id="mpa_1"` variant too.
   5. AC 2 — `test_survey_round_trips`: a `Survey` with `cover={SegClass.LIVE_CORAL: 0.42,
      SegClass.SAND: 0.58}`, `video_path`, `failure_reason=None`, `status=SurveyStatus.DONE`,
      `source="upload"` → equal after `get`; also the all-`None` variant (`cover=None`,
      `video_path=None`, `failure_reason="too blurry"`).
   6. AC 2 — `test_repos_raise_not_found`: `store.sites.get("site_missing")` and
      `store.surveys.get("srv_missing")` raise `NotFoundError`.
   7. AC 2 — `test_save_is_an_upsert`: saving the same `Site` id twice with a new `name` leaves one
      row and `get` returns the second version.
   8. AC 3 — `test_concurrent_writes_are_serialised`: two coroutines each
      `async with store.locked(): events.append("enter …"); await asyncio.sleep(0); events.append("exit …")`
      via `asyncio.gather` → the recorded order is `enter a, exit a, enter b, exit b` (no interleaving).
      Then `asyncio.gather(store.sites.save(a), store.sites.save(b))` → both rows readable (the literal
      AC: two concurrent writes through `Store` both succeed).
   9. Events — `test_events_round_trip_and_resume`: append `SurveyStarted`(seq 1), `FramesExtracted`
      (seq 2), `Segmented` (seq 3, with `cover={SegClass.LIVE_CORAL: 0.5}`) and an `Assessed` (seq 4,
      nested `FrameAssessment`); `list(survey_id)` returns them in seq order and each `==` the
      original; `list(survey_id, after_seq=2)` returns seq 3 and 4 only (the §6.2 reconnect contract);
      `next_seq(survey_id) == 5`; `next_seq("srv_other") == 1`.
   10. Events — `test_duplicate_event_seq_is_a_store_error`: appending the same `(survey_id, seq)`
       twice raises `StoreError` (the PK violation is wrapped), and the first row survives.
   11. Blobs — `test_blob_paths_match_6_4`: `store.blobs.frame_path("srv_1", "frm_1")` ==
       `data_dir/"blobs"/"srv_1"/"frames"/"frm_1.jpg"`, masks `.png`, `video_path("srv_1")` ==
       `…/srv_1/video.mp4`, `video_path("srv_1", "mov")` == `…/video.mov`.
   12. Blobs — `test_blob_bytes_round_trip`: `ref = store.blobs.save_frame("srv_1", "frm_1", b"jpeg")`
       → `ref == "blobs/srv_1/frames/frm_1.jpg"` (POSIX, relative), file exists and `read(ref)` returns
       `b"jpeg"`; same for `save_mask` and `save_video`.
   13. Blobs — `test_resolve_rejects_escape`: `resolve("../secrets.txt")` raises `StoreError`;
       `resolve(ref)` returns the absolute path.
   14. `test_store_error_wraps_duckdb`: `await store.execute("SELEC nonsense")` raises `StoreError`
       (never `duckdb.Error`), and the store still works afterwards.
3. `src/reefcase/store/blobs.py`, then `repos.py`, then `db.py` (the import direction inside the
   package is `db` → `repos`/`blobs`; use `TYPE_CHECKING` for the `Store` annotation in `repos.py`
   if you want to avoid the cycle — import-linter only forbids crossing *layers*).
4. `src/reefcase/store/migrations/001_sites_surveys_events.sql` exactly as above.
5. Run `uv run poe gate` until green (ruff, ruff format, pyright strict, lint-imports, pytest).
   - `ruff format` must be clean on every new file; keep lines ≤ 100.
   - pyright strict applies to all of `src/reefcase`; `duckdb` ships `py.typed` + `_duckdb-stubs`, so
     `duckdb.DuckDBPyConnection` resolves cleanly. `execute`/`executemany` take `parameters: object`,
     so pass `list[Any]`; `fetchall()` returns `list[tuple[Any, ...]]`.
   - **Do not annotate an `@asynccontextmanager`/`@contextmanager` with `Iterator`/`AsyncIterator`** —
     pyright 1.1.414 reports it as deprecated (`reportDeprecated`) and fails the gate. Use
     `AsyncGenerator[DuckDBPyConnection, None]` / `Generator[...]` instead (verified).
6. Confirm `uv run lint-imports` still reports both contracts kept and that `store/` imports only
   `reefcase.core`.
7. Report the files you changed, any deviation, and the last gate output.

## Lessons (from `ops/*/learnings.md`, relevant to this story)

- [python] (1-1) RULE: When `ruff check .` fails only inside frozen vendored trees, widen
  `[tool.ruff] extend-exclude` — never narrow the gate command. (Already done; do not touch it.)
- [test] (1-1) RULE: Every import-linter layer needs an `__init__.py`; `store/__init__.py` exists —
  leave the contract in `pyproject.toml` alone.
- [python] (1-2) RULE: `planning` is already excluded from ruff; this story writes a story file
  there, so no action.
- [python] (1-2) RULE: On a pydantic model field, write `Field(default_factory=list[Foo])`, not
  `Field(default_factory=list)`. (No models are added here; relevant if you build test models.)
- [python] (1-3) RULE: In tests, never let a developer's real `.env` leak in. This story's tests never
  build `Settings`; if you do, use the `Settings(_env_file=None)` + clear-`REEFCASE_*` pattern.
- Standing rules from `AGENTS.md`: Python 3.14, always `uv run`, dependencies via `uv add`, every AC
  has a test written first, never edit `planning/planning-artifacts/**` or `docs/agents/**`,
  scratch work in `.scratch/`, never touch `src/reefcase/core/` after Epic 1.

## Library check (verified 2026-10-27 by the `researcher` subagent + local probes on duckdb 2.0.0)

**duckdb 2.0.0** (PyPI, released 2026-10-21; `requires-python >=3.11`). `uv add "duckdb>=2.0.0"`
resolves to 2.0.0. There is no cp314 wheel: 2.0 ships a `cp312-abi3` wheel per platform, which is what
Python 3.14 installs (verified by installing it in a 3.14 venv). The package ships `duckdb/py.typed`
and a `_duckdb-stubs` PEP 561 package, so pyright strict resolves `duckdb.DuckDBPyConnection`,
`connect`, `execute`, `executemany`, `fetchall`, `fetchone`, `close` with no ignores (verified with
pyright 1.1.414 strict).

```python
import duckdb

con = duckdb.connect(str(path), config={"TimeZone": "UTC"})   # creates the file; parent dir must exist
con.execute("CREATE TABLE t (i INTEGER); INSERT INTO t VALUES (1);")  # multi-statement: supported
row = con.execute("SELECT * FROM t").fetchall()               # list[tuple[Any, ...]]
con.close()
```

- **Exception hierarchy**: everything derives from `duckdb.Error` (`DatabaseError`,
  `OperationalError`, `ProgrammingError`, `ConstraintException`, `InvalidInputException`,
  `IOException`, `HTTPException`, …). `duckdb.duckdb.Error` does **not** exist — catch
  `duckdb.Error`. A duplicate primary key raises `duckdb.ConstraintException` ("Duplicate key …").
- **Multiple statements**: one `execute()` call runs the whole string; `--` comments and trailing
  semicolons are fine; only the last statement's result is fetchable. Do not split on `;`.
- **Types** (verified locally): `VARCHAR`→`str`, `INTEGER`→`int`, `DOUBLE`→`float`, `DATE`→
  `datetime.date`, `TIMESTAMPTZ`→**tz-aware** `datetime` in the session timezone (set
  `TimeZone: "UTC"` for determinism), microseconds preserved, equality is by instant so a `+05:30`
  input compares equal to the returned UTC value. Params: `execute(sql, [a, b])` with `?`;
  `executemany(sql, [row, row, …])` accepts a list of tuples.
- **`pytz` is mandatory for TIMESTAMPTZ fetches.** Without it, every fetch of a TIMESTAMPTZ column
  raises `duckdb.InvalidInputException: Invalid Input Error: Required module 'pytz' failed to import`
  (reproduced locally on 2.0.0). Hence `uv add pytz`.
- `INSERT … ON CONFLICT (id) DO UPDATE SET x = excluded.x` works in 2.0 (verified); explicit
  `BEGIN`/`COMMIT`/`ROLLBACK` works; `NULL` binds fine. `at` is a **reserved keyword** in 2.0
  (`Parser Error: syntax error at or near "at"`); `type`, `data`, `seq`, `status`, `source` are not.
- **Spatial**: not bundled in the wheel and explicitly **not autoloadable**, so `LOAD spatial` alone
  fails on a clean machine. duckdb 2.0 adds the one-liner `INSTALL AND LOAD spatial;` (skips whichever
  step is done); cache is `~/.duckdb/extensions/v2.0.0/<platform>/spatial.duckdb_extension` (verified:
  it installs and loads here). Offline with no cache, `INSTALL` raises `duckdb.HTTPException`
  (an `IOException`/`OperationalError`). Check with
  `SELECT extension_name, loaded FROM duckdb_extensions()` (`loaded`/`installed` are BOOLEAN columns).
- **Connections**: same process + same file + same config → a second `connect()` succeeds (no lock
  error); *different* config (e.g. `read_only`) → `duckdb.ConnectionException`. Tests use one store
  per temp dir, so this never bites. `".memory:"` / `":memory:name"` also exist.
- **`pytest-asyncio 1.4.1`** (released 2026-10-25) requires `pytest>=8.4,<10` → compatible with
  pytest 9.1.1 on Python 3.14. In strict mode (the default, no ini config) an
  `@pytest.mark.asyncio` marker is enough — verified locally with pytest 9.1.1 (no warnings, no
  `asyncio_mode` needed). `asyncio_mode = "auto"` + `asyncio_default_fixture_loop_scope =
  "function"` would be the alternative; **not** used here because this story must not edit the gate
  config.
