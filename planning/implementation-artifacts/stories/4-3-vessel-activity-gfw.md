# Story 4.3: vessel_activity (Global Fishing Watch)

Owner: D (lead-d) · Priority: P0 · Depends on: 4.1 · Status: in-progress

## Story (verbatim from epics.md)

As the agent,
I want satellite-radar vessel detections and fishing effort near the site,
So that I can test the fishing-pressure and physical-damage hypotheses.

- Owner: B · Priority: P0 · Depends on: 4.1
- Files: `src/reefcase/tools/vessels.py`, `tests/tools/test_vessels.py`, `tests/cassettes/vessels/*.yaml`
- Done when: gate passes with `--record-mode=none`

### Acceptance Criteria (verbatim)

**Given** a site, `radius_km` ≤ 20 and a date range
**When** `vessel_activity` runs against the GFW endpoints in architecture §9
**Then** `data` has `sar_detections.total`, `sar_detections.unmatched_to_ais` with points, and `fishing_hours`

**Given** `radius_km` > 20
**When** called
**Then** validation fails before any HTTP call

**Given** the result
**When** it is serialized
**Then** it contains no vessel names, MMSI or IMO numbers (activity patterns only — PRD §8)

**Given** two concurrent `vessel_activity` calls
**When** they run
**Then** GFW reports are requested one at a time, and a 524 is recovered via the last-report endpoint (architecture §9.1)

## Architecture sections this story touches

### §3 — Layering
- `src/reefcase/tools/vessels.py` lives in the `tools` layer.
- May import `reefcase.core` and `reefcase.tools.{http,registry}`.
- May not import `api` or `pipeline`.

### §4.2 — Schemas (`src/reefcase/core/schemas.py`)
- `ToolResult(id: str, tool: str, params: dict[str, Any], data: dict[str, Any], source_url: str, retrieved_at: AwareDatetime)`
- `Site(id: str, name: str, location: GeoPoint, ...)`
- `GeoPoint(lat: float, lon: float)`

### §4.4 — Configuration (`src/reefcase/core/config.py`)
- `Settings.gfw_token: SecretStr | None` maps to `REEFCASE_GFW_TOKEN`.

### §5.4 — Tools (`src/reefcase/tools/`)
- Tool signature: `async def vessel_activity(params: VesselActivityParams, ctx: ToolContext) -> ToolResult`
- Parameter model:
  ```python
  class VesselActivityParams(BaseModel):
      site_id: str
      radius_km: float = Field(le=20.0, gt=0.0)
      start: date
      end: date
  ```
- Tool result data contract:
  - `sar_detections`:
    - `total`: int
    - `unmatched_to_ais`: dict with `count`: int, `points`: list[dict[str, float]] (lat/lon points)
  - `fishing_hours`: float
- Concurrency limit: module-level / process-wide `asyncio.Semaphore(1)` guarding GFW report calls (§9.1).
- Timeouts & retries: On HTTP 524 Gateway Timeout, fetch status and result via `GET https://gateway.api.globalfishingwatch.org/v3/4wings/last-report`.
- Anonymization rule: Strip/exclude any vessel names, MMSI, or IMO numbers from returned data and params.

### §9.1 — Global Fishing Watch API v3
- Endpoint: `POST https://gateway.api.globalfishingwatch.org/v3/4wings/report`
- Headers: `Authorization: Bearer <token>`
- Body: `{"geojson": <polygon FeatureCollection bounding the circle radius_km around site>}`
- Query parameters:
  - `format=JSON` (response is zip archive, unzipped in memory via `zipfile.ZipFile`)
  - `group-by=FLAG`
  - `temporal-resolution=ENTIRE`
  - `spatial-resolution=HIGH`
  - `date-range=YYYY-MM-DD,YYYY-MM-DD`
  - `datasets[0]=public-global-sar-presence:latest` (total SAR)
  - `filters[0]=matched='false'` (unmatched to AIS)
  - `datasets[0]=public-global-fishing-effort:latest` (fishing effort)
- Fallback/Recovery: `GET https://gateway.api.globalfishingwatch.org/v3/4wings/last-report`

## Tasks

1. Write unit tests in `tests/tools/test_vessels.py` covering:
   - AC 1: Successful `vessel_activity` query returning total SAR detections, unmatched detections with points, and fishing hours from synthetic fixtures/cassettes.
   - AC 2: Parameter validation failing with `ValidationError` when `radius_km > 20` without making HTTP calls.
   - AC 3: Result serialization verifying no vessel names, MMSI, or IMO numbers appear in output payload.
   - AC 4: Concurrent calls serialization via `asyncio.Semaphore(1)`, and recovery from HTTP 524 via `last-report` endpoint.
2. Build synthetic offline cassette fixtures under `tests/cassettes/vessels/` or minimal in-memory HTTP responses matching GFW zip JSON response shape.
3. Implement `src/reefcase/tools/vessels.py`:
   - Circle-to-polygon GeoJSON approximation generator for `radius_km` around `(lat, lon)`.
   - `VesselActivityParams` with `radius_km <= 20.0` validation.
   - Async GFW client logic using `ctx.client` (`httpx.AsyncClient`) with `Authorization: Bearer $REEFCASE_GFW_TOKEN`.
   - In-memory zip extraction of GFW JSON payloads.
   - Process-wide `asyncio.Semaphore(1)` for GFW reports.
   - 524 timeout recovery handler polling/fetching `/v3/4wings/last-report`.
   - Extraction of SAR detections (total & unmatched points) and fishing hours.
   - Sanitization of sensitive identifiers (MMSI, IMO, vessel name).
   - Packaging into `ToolResult`.
4. Run `uv run poe gate` and ensure ruff, format, pyright strict, import-linter, and pytest pass with `--record-mode=none`.
5. Add cassette recording command instructions to `ops/lead-d/handoff.md`.

## Lessons

- `[test] (1-4) RULE`: For async tests, put `@pytest.mark.asyncio` on each `async def test_...`; do not edit `[tool.pytest.ini_options]`.
- `[python] (1-3) RULE`: In tests, build `Settings` with `Settings(_env_file=None)  # pyright: ignore[reportCallIssue]` inside `make_settings()` helper, deleting inherited `REEFCASE_*` env vars.
- `[lead-d backend rule]`: Never record a cassette yourself: recording needs a live key. Write code plus hand-made minimal synthetic cassette, and list recording command in `ops/lead-d/handoff.md`.
- `[lead-d backend rule]`: The GFW client allows one report at a time per user (`asyncio.Semaphore(1)`). For a 524, retry through the last-report endpoint.

## Library check

Confirmed against Global Fishing Watch v3 4Wings API documentation:
- Report endpoint: `POST https://gateway.api.globalfishingwatch.org/v3/4wings/report`
- Last report endpoint: `GET https://gateway.api.globalfishingwatch.org/v3/4wings/last-report`
- Datasets: `public-global-sar-presence:latest` and `public-global-fishing-effort:latest`
- Filters for unmatched: `filters[0]=matched='false'`
- Zip handling: standard library `zipfile.ZipFile(io.BytesIO(response.content))` extracts the JSON files from memory.
- In-memory HTTP testing: `pytest-recording` / `vcrpy` with offline synthetic cassettes, ensuring no live API calls during gate execution.
