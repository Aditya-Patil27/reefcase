# ReefStudent model card

ReefStudent is the fast segmenter behind `REEFCASE_SEGMENTER=student`: a U-Net with an
EfficientNet-B0 encoder (`segmentation-models-pytorch` 0.6.0, ImageNet init), six output
classes in the `MASK_INDEX` order (`other, live_coral, bleached_coral, algae, rubble, sand`).
Input is RGB / 255, resized so the long side is 1024 on a 32-pixel grid.

Two students were trained with the same recipe (`ml/kaggle/train_student.py`, 30 epochs, Kaggle
T4) and scored on the same held-out test split. The better one ships.

| Student | Trained on | Test mIoU |
|---|---|---|
| **supervised** (shipped) | Coralscapes human labels, mapped to the six classes | **0.683** |
| distilled | SAM 3 pseudo-labels of the same frames (no human labels) | 0.291 |
| SAM 3 itself (the teacher) | — | 0.300 |

The distillation result is honest but modest: the distilled student matches its teacher
(0.291 vs 0.300) at about 8× the speed, and inherits its mistakes. Human labels more than
double the mIoU at the same speed, so the supervised student ships.

## Training data

- Coralscapes train + val, 1,683 frames at 1024×2048 from Red Sea dive sites. The test split
  (392 frames) is never trained on.
- Split by dive site: site10, site11 and site12 are validation (210 frames); the other 1,473
  frames train.
- Supervised labels: the Coralscapes human masks, remapped from its 39 classes with
  [`ml/coralscapes_map.json`](../coralscapes_map.json). Unlabelled pixels (id 0) are ignored
  in the loss.
- Distilled labels: SAM 3 text-prompted masks ([`ml/kaggle/pseudo_label.py`](../kaggle/pseudo_label.py),
  run on Modal by `ml/modal/pseudo_label_run.py`); one manifest row per frame in
  [`pseudo_label_manifest.jsonl`](./pseudo_label_manifest.jsonl).
- Story 7.1 asked for ≥ 2,000 frames including NCRMP images from non-demo regions. Only the
  1,683 Coralscapes frames were used; no NCRMP imagery is in the training set.

Training curves: [`train_supervised.json`](./train_supervised.json) (best val mIoU 0.641,
epoch 30) and [`train_distilled.json`](./train_distilled.json) (best val mIoU 0.530 against
SAM 3 labels, epoch 29).

## Licences

- Coralscapes: Apache-2.0. Cite *The Coralscapes Dataset: Semantic Scene Understanding in
  Coral Reefs* (Sauder et al., 2025), https://huggingface.co/datasets/EPFL-ECEO/coralscapes.
- SAM 3 (teacher of the distilled student only): SAM License; acknowledged in
  [`data/LICENSES.md`](../../data/LICENSES.md).
- The weights are not committed; they come from the Kaggle kernel
  `aditya32211/reefcase-train-student` and load from `REEFCASE_STUDENT_WEIGHTS`.

## Metrics

All numbers are in [`eval.json`](./eval.json): the 392-frame Coralscapes test split, mapped to
the six classes.

| Class | Supervised | Distilled | SAM 3 |
|---|---|---|---|
| other | 0.813 | 0.606 | 0.599 |
| live_coral | 0.715 | 0.394 | 0.366 |
| bleached_coral | 0.577 | 0.111 | 0.111 |
| algae | 0.561 | 0.000 | 0.023 |
| rubble | 0.637 | 0.000 | 0.053 |
| sand | 0.797 | 0.636 | 0.650 |
| **mIoU** | **0.683** | **0.291** | **0.300** |

Speed per 1024×2048 frame:

| Model | Kaggle T4 | RTX 3050 6 GB laptop |
|---|---|---|
| ReefStudent (supervised) | 161 ms | 135 ms (197 MiB peak) |
| ReefStudent (distilled) | 161 ms | — |
| SAM 3 | 1,247 ms | — |

The SAM 3 time was measured on a Modal T4 (the same GPU model) during pseudo-labelling, not
inside the Kaggle kernel. RTX 3050 times are the mean of 50 timed runs after 2 warm-ups.

## Known failure modes

- **Domain shift.** Every training frame is from the Red Sea. The demo footage (NCRMP, Hawaii)
  has different species, light and camera; expect lower accuracy there than the test numbers.
- **Algae and bleached coral are the weakest classes** (IoU 0.56 and 0.58). Turf algae over
  dead coral and pale-but-alive colonies are the usual confusions.
- **Class mapping is coarse.** Coralscapes classes without a clear home (for example
  Millepora fire coral and Turbinaria) map to `other`, so they never count as coral cover.
- **The distilled student copies SAM 3's errors**: on validation, SAM 3 sends bleached pixels
  to `live_coral` and algae and rubble to `other`, and the distilled student scores 0 IoU on
  algae and rubble.
