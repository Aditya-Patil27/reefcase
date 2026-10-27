---
status: in-progress
---

# Story 3.1: Segmenter interface and cover computation

As the pipeline,
I want one segmenter interface and a cover calculator,
So that backends are interchangeable (FR5, FR6).

- Owner: A · Priority: P0 · Depends on: 1.5
- Files: `src/reefcase/vision/{segmenter,cover}.py`, `tests/vision/test_cover.py`
- Done when: gate passes

## Acceptance Criteria

**Given** a mask with known class counts
**When** `cover_from_mask` runs
**Then** the fractions match and sum to 1.0 (±1e-6)

**Given** `REEFCASE_SEGMENTER=fake`
**When** `build_segmenter` is called
**Then** it returns `FakeSegmenter`

## Architecture contract

From §5.1, `Segmenter` is a protocol with `name: Literal["sam3", "student", "fake"]` and
`segment(image: np.ndarray) -> np.ndarray`; `build_segmenter(settings: Settings) -> Segmenter`;
and `cover_from_mask(mask: np.ndarray) -> dict[SegClass, float]`.
Mask indices are defined by `reefcase.core.schemas.MASK_INDEX`, and every class must be
represented in the result.

## Tasks

1. [ ] Add tests for exact class fractions, sum-to-one behavior, invalid masks, and fake backend selection.
2. [ ] Implement the segmenter protocol, backend factory, and cover calculator.
3. [ ] Run `uv run poe gate`.
4. [ ] Review the diff against the reviewer contract.

## Lessons

None relevant beyond the repository rules.

## Library check

No third-party API is introduced by this story.
