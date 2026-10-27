# Story 2.1: Survey upload endpoint

Owner: B (lead-b) · Priority: P0 · Depends on: 1.4 · Status: in-progress

## Story (verbatim from epics.md)

As a diver,
I want to upload a clip with a location and date,
So that my dive becomes a survey (FR1).

- Owner: B · Priority: P0 · Depends on: 1.4
- Files: `src/reefcase/api/main.py`, `src/reefcase/api/routes/surveys.py`, `tests/api/test_upload.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** a valid mp4 ≤ 500 MB with lat, lon and dive_date
**When** POSTed to `/api/surveys`
**Then** the response is `201` with a `Survey` in status `queued`, and the video is stored at
`blobs/{survey_id}/video.mp4`

**Given** lat outside −90..90, or a non-video file
**When** POSTed
**Then** the response is `422` with a field-level error

## Architecture sections this story touches

### §6.3 — HTTP API (this endpoint)

| POST | `/api/surveys` | multipart: `video`, `lat`, `lon`, `dive_date`, optional `site_name` → `201 Survey` |

Also on the same router in later stories (not now): GET `/api/surveys/{id}` (2.2+),
`/events` (2.2), `/investigation` + `/frames` (5.4).

### §5.1 / §6.1 — app wiring the endpoint needs

- The API app needs a `Store` (1.4) at startup. §6.1's JobRunner is Story 2.2 — **2.1 only
  persists the survey as `queued` and stores the video blob**; nothing runs the job yet.
- Site handling: the AC has no `site_id` field, so 2.1 creates a Site per upload. Story 2.5 adds
  `find_site_near` grouping; until then every upload makes its own site named `site_name` or
  `"Reef @ lat,lon"` (2.5's naming rule, applied here so 2.5 is a refactor, not a rewrite).
- §6.3: `GET /api/health` → provider configuration status. Minimal shape: `{"segmenter": …,
  "agent_llm": bool, "teacher_llm": bool}` — enough to prove the app boots with settings.

### §3 — layout / layering

- `src/reefcase/api/main.py` (app factory), `src/reefcase/api/routes/surveys.py` (router).
  `api` → `pipeline` → … layering: `api` may import `store`, `core` (and `pipeline` once 2.2
  exists). `core` and `store` are frozen/untouched.

### §4 — schemas/config used

- `Survey` (`status=QUEUED`, `source="upload"`, `video_path=blobs/…`), `Site`, `GeoPoint`
  (lat −90..90, lon −180..180 — pydantic already enforces), `SurveyStatus`.
- `new_id("srv")` / `new_id("site")` from `core.ids`.
- `Settings` via env; `REEFCASE_DATA_DIR` selects where `Store.open` points.
- `Blobs.save_video(survey_id, data)` writes `blobs/{survey_id}/video.mp4` and returns the ref.

## Contract notes / decisions (do not deviate)

1. **FastAPI multipart upload**: `UploadFile` for `video`, `Form()` for the rest. The deps added
   are `fastapi` and `python-multipart` (needed for multipart parsing) plus `httpx` for the ASGI
   test client. `uv add fastapi python-multipart httpx` and `uv add --dev pytest ...` (already
   there). Nothing else.
2. **Validation → 422 with field-level errors.** FastAPI maps pydantic/Form validation errors to
   422 with `detail` entries naming the field, so bad `lat`, missing `dive_date`, or a
   non-video file must be *validated*, not crashed on. Non-video is checked by suffix
   (`.mp4`, `.mov`, `.avi`, `.webm`, `.mkv`) — a 500 MB cap is enforced by reading the upload in
   chunks and rejecting past the cap with 413 (the AC says "≤ 500 MB"; over-size is out of the
   422 set, so 413 Payload Too Large is the honest code).
3. **App factory + lifespan**: `create_app(settings: Settings | None = None) -> FastAPI` with a
   lifespan that opens `Store.open(settings.data_dir)` into `app.state.store` and closes it on
   exit. Tests build the app with `Settings(data_dir=tmp_path)`; production `main.py` module
   exposes `app = create_app()` reading env. **The store handle is passed to the router via
   `request.app.state.store`** — no globals, no import-time side effects.
4. **Response is the `Survey` pydantic model** (`response_model=Survey`), so OpenAPI matches §4.2
   exactly. `201` status on create.
5. **Sync writes in async route**: the store API is async (`await store.sites.save(...)`), so the
   route is `async def`. The video blob write (`save_video`) is sync file I/O — it runs in the
   route via `await asyncio.to_thread(...)`. Keep total work tiny (temp file → bytes → blob).
6. **Tests use `httpx.AsyncClient(transport=ASGITransport(app=app))`** (architecture §11 api
   row). Offline, no network. A tiny real mp4 comes from the 1.5 fixture clip
   (`tests/fixtures/clip_10s.mp4`, 162 KB); the non-video case uploads a text file renamed to
   `.mp4`... no — non-video is enforced by *suffix*, so the test uploads a file named `notes.txt`
   and expects 422 on `video`.

## Exact shape to implement

### `src/reefcase/api/main.py`

```python
def create_app(settings: Settings | None = None) -> FastAPI: ...
app: FastAPI  # module-level create_app() for uvicorn
```

- lifespan: `store = await asyncio.to_thread(Store.open, settings.data_dir)`; `app.state.store`,
  `app.state.settings`; yield; `store.close()`.
- routers: `surveys.router` under `/api` (and, from this story, a `/api/health` route here).

### `src/reefcase/api/routes/surveys.py`

```python
router = APIRouter()

MAX_VIDEO_BYTES = 500 * 1024 * 1024
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".webm", ".mkv"}

@router.post("/surveys", response_model=Survey, status_code=201)
async def create_survey(
    request: Request,
    video: UploadFile,
    lat: float = Form(...),
    lon: float = Form(...),
    dive_date: date = Form(...),
    site_name: str | None = Form(None),
) -> Survey: ...
```

Behaviour: validate suffix (422 field error on `video`); read in ≤ 1 MiB chunks, 413 past
`MAX_VIDEO_BYTES`; build `Site` (name = `site_name` or `f"Reef @ {lat:.5f}, {lon:.5f}"`) and
`Survey(status=QUEUED, source="upload")`; save blob ref into `video_path`; persist site + survey
through the store; return the Survey. pydantic's `GeoPoint` is *not* used in the form (a bad lat
must be a 422 from the endpoint, not a ValidationError leak) — validate with explicit bounds
checks returning `HTTPException(422, ...)` with the field name in `detail`. FastAPI wraps
HTTPException detail as `{"detail": "..."}`; the test asserts the field name appears in the
response body.

## Tasks (tests first, then code)

1. `uv add fastapi python-multipart httpx`.
2. `tests/api/test_upload.py` (red first; module builds app per test with tmp data dir +
   `make_settings`):
   - AC 1 — `test_upload_creates_queued_survey_and_stores_video`: POST the fixture clip as
     `video` with valid lat/lon/dive_date → 201; body matches `Survey` (id starts `srv_`, status
     `queued`, `source` `upload`, `video_path` == `blobs/{srv}/video.mp4`, `site_id` starts
     `site_`); blob bytes on disk equal the uploaded bytes; `store.surveys.get(id)` round-trips;
     a `Site` exists named `"Reef @ lat,lon"` when `site_name` omitted, and the given
     `site_name` when present.
   - AC 1 — `test_upload_accepts_site_name` (covered above, but assert both name paths).
   - AC 2 — `test_upload_rejects_lat_out_of_range`: lat=95 → 422, body names `lat`.
   - AC 2 — `test_upload_rejects_lon_out_of_range`: lon=-200 → 422 naming `lon`.
   - AC 2 — `test_upload_rejects_non_video_file`: `notes.txt` → 422 naming `video`.
   - AC 2 — `test_upload_rejects_missing_dive_date` → 422 naming `dive_date`.
   - 413 — `test_upload_rejects_oversized_video`: monkeypatch `MAX_VIDEO_BYTES` down to 1 KB and
     upload the clip → 413.
   - health — `test_health_reports_provider_config`: GET `/api/health` → 200 with `segmenter`
     and the two llm booleans reflecting the settings the app was built with.
3. `src/reefcase/api/routes/surveys.py` then `src/reefcase/api/main.py`.
4. `uv run poe gate` until green (import-linter: `api` → `store`/`core` only).
5. Self-review (six items), commit `2.1: Survey upload endpoint`, integrate.

## Lessons (relevant)

- [test] (1-3) use the `make_settings` conftest factory; never construct `Settings` bare in a test.
- [test] (1-4) async tests get `@pytest.mark.asyncio`.
- [python] (1-2) `Field(default_factory=list[Foo])` typing rule (no new models here — schemas are
  frozen).

## Library check (researcher-confirmed patterns for this stack)

- **FastAPI 0.162 / multipart**: `UploadFile` + `Form(...)` in one endpoint requires
  `python-multipart`; `UploadFile` is spooled to disk, so chunked `await file.read(size)` is the
  size-capped read path. `HTTPException(status_code=422, detail=...)` renders as
  `{"detail": "<msg>"}`. Request validation of Form fields renders
  `{"detail": [{"loc": [...,"lat"], "msg": ...}]}` — both shapes are asserted loosely (field name
  appears in the body text).
- **httpx ASGI testing**: `httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
  base_url="http://test")` — no network, no port. File upload via `files={"video": (name, bytes,
  mime)}` and `data={...}` for form fields.
- Nothing exotic beyond these two; no `researcher` round needed.
