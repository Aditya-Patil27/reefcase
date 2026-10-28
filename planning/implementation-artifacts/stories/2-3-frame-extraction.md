# Story 2.3: Frame extraction

Owner: B (lead-b) · Priority: P0 · Depends on: 2.2 · Status: in-progress

## Story (verbatim from epics.md)

As the pipeline,
I want candidate frames sampled from the video,
So that later stages have images to analyse (FR2).

- Owner: B · Priority: P0 · Depends on: 2.2
- Files: `src/reefcase/ingest/frames.py`, `src/reefcase/store/migrations/003_frames.sql`, `tests/ingest/test_frames.py`
- Done when: gate passes

### Acceptance Criteria (verbatim)

**Given** `tests/fixtures/clip_10s.mp4`
**When** `extract_candidates(path, every_sec=0.5)` runs
**Then** it yields ~20 RGB frames with their `t_sec`, decoded with PyAV

**Given** a corrupt file
**When** extraction runs
**Then** it raises `IngestError("unreadable video")`

## Architecture sections this story touches

### §4.2 — Schemas (`schemas.py`)
- `Frame(id, survey_id, t_sec, image_path, quality)`
- QualityScore schema: `blur`, `color_cast`, `turbidity`, `passed`, `reason`

### §6.4 — Storage (`store/migrations/003_frames.sql`)
- Table `frames` with columns `id`, `survey_id`, `t_sec`, `image_path`, `quality`.

### §3 — Layering
- `ingest/frames.py` may import `core` and third-party `av`, `numpy`.
- `core/errors.py` has `ReefCaseError`. `IngestError` subclasses `ReefCaseError`.

## Tasks
1. Write tests in `tests/ingest/test_frames.py` covering candidate extraction, sampling interval, and corrupt file error handling.
2. Update `tests/store/test_store.py` to assert migration 003 is applied.
3. Write `src/reefcase/store/migrations/003_frames.sql`.
4. Implement `src/reefcase/ingest/frames.py` with `CandidateFrame`, `IngestError`, and `extract_candidates`.
5. Run `uv run poe gate` and verify all tests pass.
