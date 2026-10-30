---
status: done
---

# Story 7.1: Training corpus and SAM 3 pseudo-labels

As the vision engineer,
I want a licensed corpus of reef frames labelled by SAM 3,
So that the student has training data (FR20).

- Owner: A · Priority: P1 · Depends on: 3.2, 3.3
- Files: `ml/kaggle/pseudo_label.py`, `ml/kaggle/pseudo_label.ipynb`, `data/LICENSES.md`
- Done when: the script runs locally on 10 frames and on Kaggle on the full set; manifest committed (not the images)

## Acceptance Criteria

**Given** ≥ 2,000 licensed reef frames: the Coralscapes train + val splits (1,683; never the test split) plus NCRMP images from the non-demo regions (architecture §9.5, §9.8)
**When** `pseudo_label.py --in frames/ --out labels/` runs on Kaggle
**Then** it writes one class-map PNG per frame plus `manifest.jsonl` (frame, source, licence, cover), resuming if interrupted

## Architecture contract

The pseudo-labelling output mask uses the §4.2 class-map contract and cover
fractions from `cover_from_mask`. Sources and licences are tracked in
`manifest.jsonl`; datasets are listed in `data/LICENSES.md`.

## Tasks

1. [ ] Add unit tests for manifest writing, cover fields, and resume behavior.
2. [ ] Implement pseudo-label CLI with resumable writes and one PNG per frame.
3. [ ] Add a notebook scaffold and licence/source rows for training corpus data.
4. [ ] Run `uv run poe gate`.

## Lessons

None relevant beyond repository rules.

## Library check

No new external API beyond existing project modules and Pillow file I/O.
