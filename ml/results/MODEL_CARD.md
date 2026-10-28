# ReefStudent model card

## Training data

- Coralscapes train + val split (test split excluded).
- NOAA NCRMP non-demo-region imagery.
- Labels generated with SAM 3 pseudo-labelling (`ml/kaggle/pseudo_label.py`).

## Licences

- Coralscapes: Apache-2.0.
- NOAA NCRMP: US Gov.
- SAM 3 teacher model licence acknowledged in `data/LICENSES.md`.

## Metrics

Metrics are reported in [`eval.json`](./eval.json): per-class IoU and mIoU for
ReefStudent and SAM 3, plus timing on Kaggle T4 and RTX 3050 for ReefStudent.

## Known failure modes

- Thin branching coral can collapse into `rubble` under motion blur.
- Very shallow glare can over-predict `bleached_coral`.
- Sediment plumes reduce separation between `sand` and `other`.
