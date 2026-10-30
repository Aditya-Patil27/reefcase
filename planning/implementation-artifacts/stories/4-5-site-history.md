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
- Tool table row (verbatim): `| site_history | site_id | past surveys with dates and cover, ordered by date |`
- So the only parameter is `site_id`. The survey under investigation is RUNNING while the
  investigator runs (`pipeline/runner.py` sets DONE only after the stages), so keeping DONE
  surveys excludes it.
- Returns `data = {"surveys": [{"survey_id", "dive_date", "cover"}]}` in `by_site` order.
- The investigator only offers registered tools, so `agent/investigator.py` must import
  `reefcase.tools.history` (`_TOOL_MODULES`).
- Reads `ctx.store.surveys.by_site(site_id)`; makes no network calls.

(Guide review 2026-10-30: the first draft of this section quoted extra
`current_survey_id`/`exclude_survey_id` params that §5.4 does not have.)

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
