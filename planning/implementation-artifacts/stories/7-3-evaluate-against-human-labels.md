---
status: done
---

# Story 7.3: Evaluate against human labels

As a judge,
I want honest accuracy numbers,
So that the distillation claim is credible (FR21).

- Owner: A · Priority: P1 · Depends on: 7.2
- Files: `ml/kaggle/eval_student.py`, `ml/results/eval.json`, `ml/results/MODEL_CARD.md`
- Done when: `eval.json` is committed

## Acceptance Criteria

**Given** the Coralscapes test split mapped with `ml/coralscapes_map.json` (architecture §9.8)
**When** the evaluation runs
**Then** `eval.json` holds per-class IoU and mIoU for both ReefStudent and SAM 3, ms/frame for both on a Kaggle T4, and ReefStudent ms/frame on the RTX 3050

**Given** the model card
**When** read
**Then** it states the training data, licences, metrics and known failure modes

## Architecture contract

Evaluation output names and class labels match §4.2/§5.1 segmentation contract.

## Tasks

1. [ ] Add tests for IoU aggregation and output shape.
2. [ ] Implement eval script and commit generated `ml/results/eval.json`.
3. [ ] Update `ml/results/MODEL_CARD.md` with data/licence/metrics/failure modes.
4. [ ] Run `uv run poe gate`.

## Lessons

None relevant beyond repository rules.

## Library check

No new external APIs; script uses JSON + NumPy calculations.
