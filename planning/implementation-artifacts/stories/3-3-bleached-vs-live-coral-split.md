---
status: in-progress
---

# Story 3.3: Bleached vs live coral split

As a park manager,
I want coral pixels split into live and bleached,
So that bleaching is measured, not guessed (FR4).

- Owner: A · Priority: P0 · Depends on: 3.1
- Files: `src/reefcase/vision/bleaching.py`, `tests/vision/test_bleaching.py`
- Done when: gate passes

## Acceptance Criteria

**Given** a coral mask and an image
**When** `classify_coral_pixels` runs
**Then** pixels with L* ≥ 80 and chroma ≤ 12 become `bleached_coral`, and others `live_coral`

**Given** pure-white and saturated-brown synthetic patches
**When** classified
**Then** they are bleached and live respectively

## Architecture contract

From §5.1, coral pixels are split with
`classify_coral_pixels(image, coral_mask)`. CIELAB L* ≥ 80 and chroma ≤ 12 is
bleached; all other coral pixels are live. The returned coral class map uses
`MASK_INDEX[SegClass.LIVE_CORAL]` and `MASK_INDEX[SegClass.BLEACHED_CORAL]`.

## Tasks

1. [ ] Add tests for threshold classification and white/brown synthetic patches.
2. [ ] Implement RGB-to-CIELAB classification for coral pixels.
3. [ ] Run `uv run poe gate`.
4. [ ] Review the diff against the reviewer contract.

## Lessons

None relevant beyond the repository rules.

## Library check

No third-party API is introduced by this story; the conversion uses NumPy.
