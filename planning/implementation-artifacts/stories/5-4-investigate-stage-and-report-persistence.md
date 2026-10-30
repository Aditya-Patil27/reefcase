---
status: complete
---

# Story 5.4: Investigate stage and report persistence

As a diver,
I want the finished case file stored and announced,
So that the web view can show it.

- Owner: D · Priority: P0 · Depends on: 5.3
- Files: `src/reefcase/pipeline/stages.py` (investigate stage), `src/reefcase/store/migrations/007_investigations.sql`, `src/reefcase/store/repos.py`, `src/reefcase/store/db.py`, `src/reefcase/api/routes/surveys.py` (add `/investigation`, `/frames`), `tests/pipeline/test_e2e_fake.py`
- Done when: gate passes

## Acceptance Criteria

**Given** the fake segmenter, a `FunctionModel` and cassette-backed tools
**When** a survey runs end to end
**Then** the event stream ends in `report_ready`, `GET /investigation` returns it, and the survey is `done`

## Architecture contract

- §4.2: `Investigation(id, survey_id, findings, hypotheses, verdict, actions, uncertain_frames, model)`.
- §4.3: `ReportReady(survey_id, seq, ts, investigation_id)`, `FindingEvent(survey_id, seq, ts, finding)`.
- §5.5: `investigate(survey, frames, segs, assessments, ctx, emit) -> Investigation`.
- §6.1: JobRunner stage chain: `ingest → segment → assess → investigate`.
- §6.3:
  - `GET /api/surveys/{id}/investigation` returns `Investigation`, or 404 until ready.
  - `GET /api/surveys/{id}/frames` returns frames with quality, segmentation and assessment (`FrameDetail`).
- §6.4: One DuckDB file, migrations in `store/migrations/`. Single writer lock.

## Decisions

- `investigate_stage(store, survey_id, ...)` loads frames, segmentations, assessments, calls `investigate(...)`, persists `Investigation` to `store.investigations`, emits `FindingEvent` for each finding and `ReportReady` with `investigation_id`.
- `007_investigations.sql` creates table `investigations` with columns `(id, survey_id, findings, hypotheses, verdict, actions, uncertain_frames, model)` and unique index on `survey_id`.
- `InvestigationRepo` provides `save(investigation)`, `get(investigation_id)`, `get_by_survey(survey_id)`.
- `api/routes/surveys.py` exposes `GET /surveys/{survey_id}/investigation` and `GET /surveys/{survey_id}/frames`.
- `tests/pipeline/test_e2e_fake.py`: seeds `store.tool_results` with canonical params (cache hit, no network), uses `FakeSegmenter`, `FunctionModel` for teacher and agent, uploads video, runs runner, checks event stream ends in `report_ready`, checks `GET /investigation`, checks survey status is `done`, checks `GET /frames`.

## Tasks

1. [x] Migration `src/reefcase/store/migrations/007_investigations.sql`.
2. [x] `src/reefcase/store/repos.py` (`InvestigationRepo`) and `src/reefcase/store/db.py` (`Store.investigations`).
3. [x] `src/reefcase/pipeline/stages.py`: `investigate_stage` and update `run_stages`.
4. [x] `src/reefcase/api/routes/surveys.py`: `GET /surveys/{survey_id}/investigation` and `GET /surveys/{survey_id}/frames`.
5. [x] Tests in `tests/pipeline/test_e2e_fake.py`.
6. [x] Gate verification: `uv run poe gate` and `pnpm -C web run gate`.
7. [x] Review and integrate.

## Lessons

- [store] (4-4) RULE: DuckDB queries format parameters cleanly with `?` placeholders.
- [agent] (4-5) RULE: A new tool module must be imported in `agent/investigator.py` `_TOOL_MODULES`.
- [agent] (5-3) RULE: Check `ctx.retry >= ctx.max_retries` before raising `ModelRetry` on invalid output.
- (5-4) RULE: In `test_e2e_fake.py`, extract frame IDs from the prompt dynamically instead of inventing IDs, ensuring citations are valid.

## Library check

- `pydantic-ai 2.62.0`: `FunctionModel` returns scripted responses.
- `FastAPI`: route parameters and models.
