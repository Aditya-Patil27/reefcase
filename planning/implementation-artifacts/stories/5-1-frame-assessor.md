---
status: review
---

# Story 5.1: Frame assessor

As the pipeline,
I want a structured health assessment per frame from Muse Spark Open,
So that the agent reasons over consistent evidence (FR7).

- Owner: B · Priority: P0 · Depends on: 1.3, 3.5
- Files: `src/reefcase/llm/assess.py`, `src/reefcase/pipeline/stages.py` (assess stage), `src/reefcase/store/migrations/006_assessments.sql`, `tests/llm/test_assess.py`
- Done when: gate passes

## Acceptance Criteria

**Given** a frame, its image and its segmentation
**When** `assess_frame` runs with a `FunctionModel` returning valid JSON
**Then** a `FrameAssessment` is stored and an `assessed` event is emitted

**Given** the Agent definition
**When** inspected
**Then** it uses tool-call output, not `NativeOutput` (architecture §5.2)

**Given** a real Baseten key (manual, not in CI)
**When** `uv run python -m reefcase.llm.assess --smoke tests/fixtures/frames/01.jpg` runs
**Then** it returns a valid `FrameAssessment`. Record the working values in `.env.example`.

**Given** the model returns invalid output twice
**When** assessing
**Then** the frame is skipped with a logged warning, and the stage continues

**Given** 24 frames
**When** the stage runs
**Then** assessments run with concurrency 4

## Architecture contract

- §5.2: tool-call output only (`output_type=SomeModel`); `NativeOutput` is forbidden.
- §5.3: `assess_frame(model, frame, image_bytes, seg) -> FrameAssessment`; the Agent's
  output is `FrameAssessment` minus id/frame_id; the prompt holds the image and the cover.
- §4.1 env: the assessor is the `teacher` role (`REEFCASE_LLM_TEACHER_*`).
- §6.1: stages run `ingest → segment → assess → investigate`.

## Decisions

- The draft (`AssessmentDraft`) also drops `model`: the caller fills it from
  `model.model_name`, so the stored name is the real one, not the LLM's guess.
  A test pins the draft's fields to `FrameAssessment` minus id/frame_id/model.
- `retries=1` on the Agent: one retry after invalid output, so a second invalid
  output raises `UnexpectedModelBehavior`, which the stage logs and skips.
- The stage runs the LLM calls under `asyncio.Semaphore(4)` but saves and
  publishes under one lock, because `events.next_seq` + `publish` is not atomic.
- `run_stages` skips the assess stage with a warning when the teacher role is
  unconfigured, so the pipeline (and its tests) still runs without keys; the
  health endpoint already reports `teacher_llm: false`.
- `AssessmentRepo.list_by_survey` (joined through `frames`, ordered by `t_sec`)
  is what 5.2 will read.

## Tasks

1. [x] Tests: draft fields, tool-call output, valid run, two invalid outputs,
   stage stores + emits, skip with warning, concurrency 4, `run_stages` chain.
2. [x] `006_assessments.sql`, `AssessmentRepo`, `Store.assessments`.
3. [x] `llm/assess.py` with `--smoke`.
4. [x] `assess_stage` + `run_stages`.
5. [x] `uv run poe gate`.
6. [x] Review against `.opencode/agents/reviewer.md`.

## Human step (why status is review)

Run the smoke test with the real Baseten key in `.env`:
`uv run python -m reefcase.llm.assess --smoke tests/fixtures/frames/01.jpg`.
On success, put the working model slug / base URL shape (no key) in `.env.example`.

## Lessons

- Migration-version lists in `tests/store/test_store.py` must grow with each migration.
- The test-review checklist forbids `sleep`; a concurrency test needs only
  `asyncio.sleep(0)` to let in-flight calls overlap.

## Library check

pydantic-ai 2.62.0: `Agent(output_type=..., instructions=..., retries=...)`,
`agent.run([text, BinaryContent(data, media_type)], model=...)`,
`FunctionModel` + `AgentInfo.output_tools` / `allow_text_output`,
`UnexpectedModelBehavior` after retries run out.
