# Story 4.5: site_history

Owner: D (lead-d) · Priority: P0 · Depends on: 4.1, 2.5 · Status: in-progress

## Story (verbatim from epics.md)

As the agent,
I want past surveys of this site,
So that I can describe change, not just state.

- Owner: B · Priority: P0 · Depends on: 4.1, 2.5
- Files: `src/reefcase/tools/history.py`, `tests/tools/test_history.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** a site with 3 completed surveys
**When** `site_history` runs
**Then** it returns them ordered by dive_date with cover, excluding the current survey

## Architecture sections this story touches

### §3 — Layering
- `src/reefcase/tools/history.py` lives in `reefcase.tools`.
- May import `reefcase.core` and `reefcase.tools.{http,registry}`.
- May not import `api` or `pipeline`.

### §4.2 — Schemas (`src/reefcase/core/schemas.py`)
- `ToolResult(id: str, tool: str, params: dict[str, Any], data: dict[str, Any], source_url: str, retrieved_at: AwareDatetime)`
- `Site(id: str, name: str, location: GeoPoint, ...)`
- `Survey(id: str, site_id: str, dive_date: date, status: SurveyStatus, cover: dict[SegClass, float] | None, ...)`
- `SurveyStatus` (`QUEUED`, `RUNNING`, `DONE`, `FAILED`)

### §5.4 — Tools (`src/reefcase/tools/`)
- Tool signature: `async def site_history(params: SiteHistoryParams, ctx: ToolContext) -> ToolResult`
- Parameter model:
  ```python
  class SiteHistoryParams(ToolParams):
      site_id: str
      current_survey_id: str | None = None
      exclude_survey_id: str | None = None
  ```
- Returns in `data`:
  - `surveys`: list of surveys ordered by `dive_date` ascending with `cover`, `live_coral`, `date`/`dive_date`, `id`/`survey_id`.
  - Excludes the current survey (by explicit `current_survey_id` / `exclude_survey_id` or by incomplete survey status).
- Runtime constraint: reads directly from DuckDB store (`ctx.store.surveys.by_site(site_id)`). Makes no network calls.

## Tasks

1. Write unit tests in `tests/tools/test_history.py`:
   - AC 1: Given a site with 3 completed surveys and 1 current survey (passed via `current_survey_id` or with `status=RUNNING`), `site_history` returns the 3 completed surveys ordered by `dive_date` with their `cover`.
   - Test excluding current survey when explicitly passed or in-progress.
   - Test unknown `site_id` raises `NotFoundError`.
   - Test empty history returns empty list `surveys: []`.
   - Test tool registry registration: `registry.call("site_history", ...)`.
   - Test offline execution (zero HTTP requests).
2. Implement `src/reefcase/tools/history.py`:
   - `SiteHistoryParams(ToolParams)`.
   - Tool `site_history(params, ctx) -> ToolResult`.
   - Query `ctx.store.surveys.by_site(params.site_id)`.
   - Filter completed surveys and exclude the current survey.
   - Return ordered surveys with cover and dates.
3. Run `uv run poe gate` and verify all tests pass.

## Lessons

- `[test] (1-4) RULE`: For async tests, put `@pytest.mark.asyncio` on each `async def test_...`; do not edit `[tool.pytest.ini_options]`.
- `[python] (1-3) RULE`: In tests, build `Settings` with `Settings(_env_file=None)  # pyright: ignore[reportCallIssue]` inside `make_settings()` helper.
- `[tools rule]`: `site_history` runs entirely offline via DuckDB store queries; makes no network calls.

## Library check

No external libraries used beyond standard library and repository store contracts (`ctx.store.surveys.by_site`).
