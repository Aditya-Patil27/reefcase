# Story 2.2: Job runner, event bus and SSE

Owner: B (lead-b) · Priority: P0 · Depends on: 2.1 · Status: in-progress

## Story (verbatim from epics.md)

As a diver,
I want to see progress live,
So that I know the investigation is working (NFR2).

- Owner: B · Priority: P0 · Depends on: 2.1
- Files: `src/reefcase/pipeline/{runner,bus}.py`, `src/reefcase/api/routes/events.py`, `src/reefcase/store/migrations/002_events_index.sql`, `tests/pipeline/test_bus.py`, `tests/api/test_sse.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** a submitted survey whose stages are stubbed
**When** a client opens `/api/surveys/{id}/events`
**Then** it receives `survey_started` within 5 s, with `id:` equal to `seq`

**Given** a client reconnecting with `Last-Event-ID: 3`
**When the stream reopens**
**Then** it receives events from seq 4 onward with no gaps or duplicates

**Given** a stage raising an exception
**When** the job runs
**Then** the survey becomes `failed` and `survey_failed` is emitted with the reason

## Architecture sections this story touches

### §6.1 — JobRunner (`pipeline/runner.py`)

- An in-process `asyncio` runner with a **concurrency limit of 2 surveys**.
- `submit(survey_id)`, then the stages run in order: `ingest → segment → assess → investigate`.
- Any exception moves the survey to FAILED and emits `survey_failed`.
- CPU/GPU-heavy work runs in `asyncio.to_thread` (2.2's stubs are instant; 2.3+ fills the stages).

### §6.2 — Event bus (`pipeline/bus.py`)

`publish(event)` persists the event to the `events` table first, then fans it out to live
subscribers. `subscribe(survey_id, after_seq)` yields stored events after `after_seq`, then live
ones. So SSE reconnects (the `Last-Event-ID` header) replay without gaps.

### §6.3 — GET `/api/surveys/{id}/events`

`text/event-stream`, `id:` = seq, `event:` = type, `data:` = JSON.

### §4.3 — events (frozen from 1.2)

`SurveyStarted(survey_id, seq, ts, site_id)`, `SurveyFailed(survey_id, seq, ts, reason)`; the
`events` table and `EventRepo.append/next_seq/list` already exist (1.4).

## Contract notes / decisions (do not deviate)

1. **Do not guess the API shape.** §6.1/§6.2 name the classes and the two methods; the epics
   nowhere wire the runner into the upload route, so `POST /api/surveys` stays as 2.1 shipped it
   (`queued` only) and the tests drive `JobRunner` directly. Wiring submit into the upload flow is
   left for the stories that add stages (2.3+), or the demo. No stage is registered in 2.2's
   `create_app` — stage implementations arrive with their stories.
2. **Bus contract (§6.2), read strictly**: `publish(event)` = persist via `EventRepo.append`
   (duplicate seq → `StoreError`, per 1.4), then fan out to subscribers of that survey id.
   `subscribe(survey_id, after_seq)` = an async generator: replay `EventRepo.list(survey_id,
   after_seq)` first, then live events as they are published, ending with the sentinel.
   Replay-then-live is seamless because `next_seq` reads the same table the replay reads.
   For a published event, `seq` is allocated *by the publisher* via `next_seq` before
   `publish` — `publish` itself never invents a seq (keeps `events` the single source of truth
   and makes replay-vs-live dedup trivial: replay covers seq ≤ N at subscribe time, live covers
   seq > N).
3. **Dedup semantics**: a live event is dropped by the stream if `event.seq <= last_emitted_seq`,
   so a poller that starts between "list" and "fanout" cannot produce a duplicate, and the
   seq-per-survey uniqueness (PK) makes gaps impossible as long as seqs are allocated via
   `next_seq` under the store lock.
4. **SSE framing**: `id:` = `seq`, `event:` = `type`, `data:` = the event JSON on one line
   (`json.dumps(..., separators=(",", ":"))`); frames separated by `\n\n`. Header
   `text/event-stream; charset=utf-8`, `Cache-Control: no-store`. `Last-Event-ID` header (a
   plain header in the ASGI test, whatever the browser does to populate it) → `after_seq`.
   Unknown survey → 404 (same shape as 2.1's GET survey). **The stream terminates** (sends the
   `stream_end` sentinel as a comment and returns) when the survey leaves `running` (2.1 leaves
   new surveys `queued`, so a stream opened before the runner picks the survey up ends with the
   sentinel and 200 — the AC's success case keeps the stream open until completion). ASGI
   response bodies are buffered by the transports in this repo (httpx `ASGIResponseStream`
   joins all chunks; our sync transport joins too), so the tests read *every* chunk the route
   produced and assert on the joined body.
5. **Runner contract**: `JobRunner(store, run_stages)` — an injectable async callable
   `(store, survey_id) -> None`; no stage classes exist yet (2.3+). Poll loop: every 0.05 s
   (tunable via constructor) it claims one queued survey (oldest first) while under the
   concurrency limit (2), flips it to RUNNING, emits `survey_started` (payload `site_id`),
   runs stages, then DONE. The 5 s AC is met because the poll interval (0.05 s) is tiny
   relative to it, and the test asserts the event arrives in a joined body of a bounded wait
   (0.75 s cap), well under 5 s. Failure path: `SurveyStatus.FAILED` + `failure_reason =
   str(exc)` + `survey_failed` event, and the stage chain stops (no DONE after FAILED).
6. **002_events_index.sql**: `CREATE INDEX IF NOT EXISTS events_survey_seq_idx ON events
   (survey_id, seq);` — the PK already covers (survey_id, seq) lookups, but §6.2's replay path
   is a range scan on (survey_id, seq) so the index is the story's named file; apply idempotence
   is `IF NOT EXISTS` per 001's style. Note 001's PK is on `(survey_id, seq)`, so the new index
   is technically redundant — but the story file names it, so it ships.
7. **Layering**: `pipeline` → `store` → `core` only (no `api` imports in `pipeline`);
   `api/routes/events.py` imports `pipeline.bus` and `core`. The import-linter layers contract
   already lists `pipeline` above `store`; a new `pipeline/__init__.py` exists (1.5 scaffold).
8. **A live web client must not hang**: the mock SSE body in `web/src/mocks/handlers.ts` is
   standard `id:`/`event:`/`data:` framing, which this route reproduces exactly — no custom
   fields, no keepalive comments (a keepalive `:`-comment would appear in the joined test body;
   it is harmless for `EventSource` but adds a parse hazard, so none is sent).
9. **Sync transports + asyncio.run**: our `SyncASGITransport` runs each request on a private
   loop via `asyncio.run` — an SSE route that leaves a poller task behind is fine (the loop
   closes after the response), but the *sampler* must live inside the request handler so it
   cannot outlive the request. Async tests use `httpx.ASGITransport` (2.1's `client_for`).

## Exact shape to implement

### `src/reefcase/pipeline/bus.py`

```python
_STREAM_END = "stream_end"   # module-level sentinel (not exported as part of the bus API)

class EventBus:
    def __init__(self, store: Store) -> None: ...
    async def publish(self, event: Event) -> None: ...
    async def subscribe(self, survey_id: str, after_seq: int = 0,
                        *, timeout: float = 0.05) -> AsyncGenerator[Event | None]: ...
```

- `publish`: `EventRepo.append` (persist first, per §6.2), then for every subscriber queue of
  that `survey_id`, `put_nowait(event)`.
- `subscribe`: replay = `store.events.list(survey_id, after_seq)`; track `last`; then live:
  pull from the queue with `wait_for(q.get(), timeout)`, on `TimeoutError` re-read the store
  (another process's publish lands in the table but not in our queue) and on `_STREAM_END`
  stop. `finally`: unregister. Per-survey `dict[str, list[asyncio.Queue]]`.

### `src/reefcase/pipeline/runner.py`

```python
class JobRunner:
    def __init__(self, store: Store, run_stages: RunStages, *, poll_interval: float = 0.05,
                 concurrency: int = 2) -> None: ...
    async def submit(self, survey_id: str) -> None: ...
    async def run_forever(self) -> None: ...
    async def run_once(self) -> bool: ...
    def close(self) -> None: ...
```

- `submit` enqueues and wakes the poller (`asyncio.Event` + `None` sentinel trick to break the
  sleep). `run_forever` polls until `close`; `run_once` claims at most one queued survey.
- Claim = re-read status under the store lock (single writer); flip to RUNNING; emit
  `survey_started`; `await run_stages(store, survey_id)`; DONE; failure → FAILED +
  `survey_failed` with `str(exc)`.
- `RunStages: TypeAlias = Callable[[Store, str], Awaitable[None]]`.

### `src/reefcase/api/routes/events.py`

```python
router = APIRouter()

@router.get("/surveys/{survey_id}/events")
async def survey_events(request: Request, survey_id: str, response: Response,
                        last_event_id: str | None = Header(None, alias="Last-Event-ID")) -> StreamingResponse
```

- Verify the survey exists (`store.surveys.get` → 404 via `NotFoundError`), parse
  `Last-Event-ID` (`ValueError` → 422), build an `EventBus` for the request
  (`request.app.state.store`) and stream via `StreamingResponse`; the generator sends
  `id:`/`event:`/`data:` frames and, when the survey leaves `running`, one
  `: stream_end` comment then returns.

### `src/reefcase/api/main.py`

Register `events.router` under `/api`.

### `src/reefcase/store/migrations/002_events_index.sql`

```sql
-- 002: replay index for the event log (architecture §6.2).
CREATE INDEX IF NOT EXISTS events_survey_seq_idx ON events (survey_id, seq);
```

## Tasks (tests first, then code)

1. `tests/pipeline/test_bus.py` (red): publish persists + allocates no seq; subscribe replays
   after seq and yields live events in order; `_STREAM_END` ends the generator; duplicate seq
   append still raises `StoreError` through the bus.
2. `tests/api/test_sse.py` (red): all four AC scenarios (§AC mapping below) — survey_started
   within the wait window with `id: 1`; reconnect with `Last-Event-ID: 3` yields 4+ without
   gaps/dupes; failed stage → FAILED + survey_failed with the reason; 404 unknown survey;
   queued+timed-out survey stream ends with the sentinel.
3. `src/reefcase/pipeline/bus.py`, `src/reefcase/pipeline/runner.py`,
   `src/reefcase/api/routes/events.py`, `002_events_index.sql`, `main.py` include.
4. `uv run poe gate` until green.
5. Self-review (six items), commit `2.2: Job runner, event bus and SSE`, integrate.

### AC → test mapping

- AC 1 (survey_started within 5 s, id == seq): `test_sse_survey_started_within_5s`
- AC 2 (Last-Event-ID: 3 → seq 4+, no gaps/dupes):
  `test_sse_reconnect_from_last_event_id` + `test_bus_replay_after_seq_is_contiguous`
- AC 3 (failed stage → failed + survey_failed with reason):
  `test_failed_stage_marks_survey_failed_and_emits_event`

## Lessons (relevant)

- [test] (2-1) FastAPI lifespan does not run under ASGI test transports; build-time open.
- [python] (2-1) `set PYTHONIOENCODING=utf-8&&` for the gate.
- [test] (1-3)/(1-4) `make_settings`; `@pytest.mark.asyncio`.

## Library check (researcher-confirmed patterns for this stack)

- **httpx ASGI transports buffer**: httpx 0.28.1's `ASGITransport` collects `body_parts` and
  `ASGIResponseStream.__aiter__` yields one joined chunk after the app returns; the repo's
  `SyncASGITransport` does the same. Therefore `StreamingResponse` tests assert on the *joined*
  body, and a stream that never terminates would hang the test — every SSE generator in these
  tests terminates (sentinel on non-running survey, or the stages completing → DONE → sentinel).
- **pytest-asyncio 1.4 strict mode**: `@pytest.mark.asyncio` on each async test (no
  `asyncio_mode=auto` in the ini).
- **httpx `Last-Event-ID`**: sent as a plain request header in tests
  (`client.get(..., headers={"Last-Event-ID": "3"})`).
- **pydantic `TypeAdapter`**: `EventAdapter.validate_python` round-trips stored events
  (already exercised by 1.4's tests).
