---
status: done
---

# Story 3.5: Segmentation stage

As a diver,
I want masks to appear live as frames are processed,
So that I can see the reef being analysed.

- Owner: A · Priority: P0 · Depends on: 2.4, 3.1, 3.3
- Files: `src/reefcase/pipeline/stages.py` (segment stage), `src/reefcase/store/migrations/004_segmentations.sql`, `tests/pipeline/test_segment_stage.py`
- Done when: gate passes

## Acceptance Criteria

**Given** kept frames and the `FakeSegmenter`
**When** the segment stage runs
**Then** each frame gets a stored mask PNG, a `Segmentation` row and a `segmented` event with `mask_url`

**Given** all frames are segmented
**When** the stage ends
**Then** `survey.cover` is the pixel-weighted mean of the frame covers

## Architecture contract

- §5.1: `Segmenter.segment(image)` maps HxWx3 uint8 RGB to an HxW uint8 class map
  (§4.2 `MASK_INDEX`); `cover_from_mask(mask)` gives per-class fractions.
- §6.1: stages run `ingest → segment → assess → investigate`; segmentation is
  CPU/GPU-heavy, so it runs in `asyncio.to_thread`.
- §4.3: `segmented` carries `frame_id`, `backend`, `cover`, `mask_url`.
- §6.4: masks go to `var/blobs/{survey_id}/masks/{frame_id}.png`; each story adds
  only the tables it needs (`004_segmentations.sql`). `/media/{path}` serves the
  blob dir, so `mask_url` is `/media/{survey_id}/masks/{frame_id}.png`.

## Decisions

- The mask PNG is a **palette PNG**: pixel values are the §4.2 class ids (so the
  file round-trips to the class map), and the palette holds the `docs/agents/ui.md`
  reef colours, so the web's `<img>` overlay renders it directly at 55% opacity.
- `segmentations` adds `SegmentationRepo` to `store/repos.py` (needed to store
  the row; mirrors 2.4 adding `FrameRepo`).
- `JobRunner._run` re-reads the survey after the stages before marking it DONE
  or FAILED. Without this the runner saved its pre-stage copy and wiped the
  `cover` this stage writes (AC2 would hold in the unit test but not in the app).

## Tasks

1. [x] Tests for AC1 (mask PNG, row, event per frame) and AC2 (pixel-weighted
   cover across frames of different sizes), a repo round trip, and the full
   chain through `JobRunner`.
2. [x] Migration `004_segmentations.sql` and `SegmentationRepo`.
3. [x] `segment_stage` and wire it into `run_stages` after ingest.
4. [x] Runner re-reads the survey after stages.
5. [x] `uv run poe gate`.
6. [x] Review the diff against `.opencode/agents/reviewer.md`.

## Lessons

- Stages own the survey row while they run; anything holding a survey object
  across `run_stages` must re-read it before saving.

## Library check

No new third-party API: Pillow palette PNGs (`Image.putpalette`, mode `P`) and NumPy.
