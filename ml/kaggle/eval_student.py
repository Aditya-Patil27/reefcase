"""Score ReefStudent and SAM 3 against the Coralscapes test split (Story 7.3).

Runs on a Kaggle T4 after training, with one ``--weights NAME=PATH`` per student:
    python ml/kaggle/eval_student.py --weights distilled=a.pt --weights supervised=b.pt \\
        --test test/ --sam3 sam3_test/ --out ml/results/eval.json

``test/`` holds ``frames/`` and the human ``labels/`` (Coralscapes ids, mapped with
``ml/coralscapes_map.json``); ``sam3_test/`` holds SAM 3's ``labels/`` and ``timing.json``
from ``ml/modal/pseudo_label_run.py``. RTX 3050 latency is measured locally with
``--rtx3050-ms`` because Kaggle has no such card.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from reefcase.core.schemas import MASK_INDEX

__all__ = ["build_eval_report", "human_lut"]

_CLASSES = len(MASK_INDEX)
IGNORE = 255
_MAP = Path(__file__).resolve().parents[1] / "coralscapes_map.json"


def human_lut(mapping: dict[str, str | None]) -> np.ndarray:
    """Coralscapes id -> ReefCase mask index; unmapped ids are ignored."""
    lut = np.full(256, IGNORE, dtype=np.uint8)
    index = {klass.value: value for klass, value in MASK_INDEX.items()}
    for coralscapes_id, name in mapping.items():
        if name is not None:
            lut[int(coralscapes_id)] = index[name]
    return lut


def build_eval_report(
    *,
    student_masks: dict[str, list[np.ndarray]],
    sam3_masks: list[np.ndarray],
    human_masks: list[np.ndarray],
    kaggle_t4_ms_student: dict[str, float],
    kaggle_t4_ms_sam3: float,
    rtx3050_ms_student: float | None,
) -> dict[str, object]:
    """Scores every student and SAM 3; ``shipped`` names the student with the best mIoU."""
    students: dict[str, dict[str, object]] = {}
    for name, masks in student_masks.items():
        metrics = _metrics(masks, human_masks)
        students[name] = {
            "per_class_iou": metrics["per_class_iou"],
            "miou": metrics["miou"],
            "ms_per_frame": {"kaggle_t4": kaggle_t4_ms_student[name]},
        }
    shipped = max(students, key=lambda name: float(students[name]["miou"]))  # type: ignore[arg-type]
    students[shipped]["ms_per_frame"]["rtx_3050"] = rtx3050_ms_student  # type: ignore[index]
    sam3 = _metrics(sam3_masks, human_masks)
    return {
        "classes": [klass.value for klass in MASK_INDEX],
        "frames": len(human_masks),
        "shipped": shipped,
        "students": students,
        "sam3": {
            "per_class_iou": sam3["per_class_iou"],
            "miou": sam3["miou"],
            "ms_per_frame": {"kaggle_t4": kaggle_t4_ms_sam3},
        },
    }


def _metrics(predictions: list[np.ndarray], targets: list[np.ndarray]) -> dict[str, object]:
    if len(predictions) != len(targets):
        raise ValueError("predictions and targets must have equal length")
    confusion = np.zeros((_CLASSES, _CLASSES), dtype=np.int64)
    for pred, target in zip(predictions, targets, strict=True):
        keep = target != IGNORE
        pairs = target[keep].astype(np.int64) * _CLASSES + pred[keep]
        confusion += np.bincount(pairs, minlength=_CLASSES * _CLASSES).reshape(_CLASSES, _CLASSES)
    inter = np.diag(confusion)
    union = confusion.sum(axis=0) + confusion.sum(axis=1) - inter
    class_iou = {
        klass.value: 1.0 if union[index] == 0 else float(inter[index] / union[index])
        for klass, index in MASK_INDEX.items()
    }
    return {"per_class_iou": class_iou, "miou": float(np.mean(list(class_iou.values())))}


def _student_masks(weights: Path, frames: list[Path]) -> tuple[list[np.ndarray], float]:
    import time

    import torch
    from PIL import Image

    from reefcase.core.config import Settings
    from reefcase.vision.student import StudentSegmenter

    segmenter = StudentSegmenter(
        Settings(_env_file=None, segmenter="student", student_weights=weights)
    )
    masks: list[np.ndarray] = []
    timings: list[float] = []
    for path in frames:
        image = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
        torch.cuda.synchronize()
        start = time.perf_counter()
        masks.append(segmenter.segment(image))
        torch.cuda.synchronize()
        timings.append((time.perf_counter() - start) * 1000)
    # The first frame pays for cuDNN autotuning; it is not a steady-state number.
    return masks, float(np.mean(timings[1:] or timings))


def main() -> None:
    from PIL import Image

    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", action="append", required=True, help="NAME=PATH")
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--sam3", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("ml/results/eval.json"))
    parser.add_argument("--rtx3050-ms", type=float, default=None)
    args = parser.parse_args()

    lut = human_lut(json.loads(_MAP.read_text(encoding="utf-8")))
    frames = sorted((args.test / "frames").iterdir())
    human = []
    sam3 = []
    for path in frames:
        label = np.asarray(Image.open(args.test / "labels" / path.name))
        if label.max() > 39:
            raise ValueError(f"{path.name}: label id {label.max()} is not a Coralscapes class")
        human.append(lut[label])
        sam3.append(np.asarray(Image.open(args.sam3 / "labels" / f"{path.stem}.png")))
    student: dict[str, list[np.ndarray]] = {}
    student_ms: dict[str, float] = {}
    for spec in args.weights:
        name, path = spec.split("=", maxsplit=1)
        student[name], student_ms[name] = _student_masks(Path(path), frames)
    sam3_timing = json.loads((args.sam3 / "timing.json").read_text(encoding="utf-8"))

    report = build_eval_report(
        student_masks=student,
        sam3_masks=sam3,
        human_masks=human,
        kaggle_t4_ms_student=student_ms,
        kaggle_t4_ms_sam3=sam3_timing["ms_per_frame_mean"],
        rtx3050_ms_student=args.rtx3050_ms,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
