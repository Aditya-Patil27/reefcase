---
status: done
---

# Story 7.2: Train ReefStudent

As the vision engineer,
I want a small U-Net trained on the pseudo-labels,
So that segmentation runs in real time on a laptop GPU.

- Owner: A · Priority: P1 · Depends on: 7.1
- Files: `ml/kaggle/train_student.py`, `ml/kaggle/train_student.ipynb`
- Done when: it produces `reefstudent.pt` and a loss curve

## Acceptance Criteria

**Given** the manifest
**When** training runs on a Kaggle GPU
**Then** it uses a 90/10 split by source (no leakage between frames from the same video), saves the best checkpoint by val mIoU, and logs per-class IoU

## Architecture contract

ReefStudent keeps the six-class mask contract and training traces are written as
artifacts (`reefstudent.pt`, curve JSON). Split is by source-group, never by
individual frame.

## Tasks

1. [ ] Add tests for grouped 90/10 split and best-checkpoint selection.
2. [ ] Implement training CLI and artifact writing.
3. [ ] Add notebook scaffold and run `uv run poe gate`.

## Lessons

None relevant beyond repository rules.

## Library check

The script is storage-and-metrics focused for offline reproducibility and does
not introduce new third-party APIs.
