---
status: in-progress
---

# Story 7.4: ReefStudent backend in the app

As the pipeline,
I want ReefStudent available as a segmenter,
So that the demo shows the fast model live (FR6).

- Owner: A · Priority: P1 · Depends on: 7.2, 3.1
- Files: `src/reefcase/vision/student.py`, `tests/vision/test_student.py`
- Done when: gate passes

## Acceptance Criteria

**Given** `REEFCASE_SEGMENTER=student` and the weights path
**When** `segment` runs
**Then** it returns a class map with the same contract, on CUDA when available and on CPU otherwise

## Architecture contract

`StudentSegmenter` must satisfy the same HxWx3 uint8 → HxW uint8 contract as
`Segmenter`, including class index semantics from §4.2.

## Tasks

1. [ ] Add tests for CPU/CUDA selection and output class-map contract.
2. [ ] Implement ReefStudent loader with CUDA fallback and class-map output.
3. [ ] Wire `build_segmenter` to the student backend.
4. [ ] Run `uv run poe gate`.

## Lessons

None relevant beyond repository rules.

## Library check

Runtime dependencies (`torch`, `segmentation_models_pytorch`) are optional at
development time and imported lazily inside the backend.
