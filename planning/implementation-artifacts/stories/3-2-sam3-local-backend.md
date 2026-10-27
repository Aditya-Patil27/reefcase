---
status: in-progress
---

# Story 3.2: SAM 3 local backend

As the pipeline,
I want SAM 3 text-prompted segmentation turned into a class map,
So that frames get real reef segmentation (FR4).

- Owner: A · Priority: P0 · Depends on: 3.1
- Files: `src/reefcase/vision/sam3.py`, `tests/vision/test_sam3.py` (marked `gpu`)
- Done when: gate passes; `pytest -m gpu tests/vision/test_sam3.py` passes on a Kaggle T4

## Acceptance Criteria

**Given** a fixture frame
**When** `Sam3Segmenter.segment` runs
**Then** it returns an HxW uint8 map, painted in priority order sand < rubble < algae < coral (architecture §5.1)

**Given** the hand masks in `tests/fixtures/masks`
**When** compared with SAM 3 output
**Then** mean IoU for coral vs non-coral ≥ 0.5 (printed in the test output)

**Given** the four text prompts
**When** one frame is segmented
**Then** vision features are computed once and reused for every prompt (architecture §5.1)

**Given** the RTX 3050 (6 GB)
**When** the gpu test runs once in fp16
**Then** peak VRAM and ms/frame are recorded in the story's dev notes, or the OOM is. This decides the laptop fallback (architecture §12).

## Architecture contract

`Sam3Segmenter` uses `Sam3Model` and `Sam3Processor` from Transformers with
`facebook/sam3`, computes `get_vision_features` once per image, and applies the
prompts `coral`, `algae`, `sand`, `rubble`. Masks are painted in the order
sand, rubble, algae, coral; coral pixels are split by
`bleaching.classify_coral_pixels`.

## Tasks

1. [ ] Add GPU-marked tests for class-map shape, priority, feature reuse, and coral IoU.
2. [ ] Implement lazy SAM 3 loading and one-feature-per-frame inference.
3. [ ] Run `uv run poe gate`; record GPU results when hardware is available.
4. [ ] Review the diff against the reviewer contract.

## Lessons

None relevant beyond the repository rules.

## Library check

Confirmed against the current Hugging Face SAM3 documentation:
`Sam3Model.from_pretrained`, `Sam3Processor.from_pretrained`,
`processor(images=..., text=..., return_tensors="pt")`,
`model.get_vision_features(...)`, and
`processor.post_process_instance_segmentation(...)`.
The real model test is GPU-only and never runs in the offline gate.
