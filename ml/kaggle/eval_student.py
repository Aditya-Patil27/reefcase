from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from reefcase.core.schemas import SegClass

__all__ = ["build_eval_report"]


def build_eval_report(
    *,
    student_masks: list[np.ndarray],
    sam3_masks: list[np.ndarray],
    human_masks: list[np.ndarray],
    kaggle_t4_ms_student: float,
    kaggle_t4_ms_sam3: float,
    rtx3050_ms_student: float,
) -> dict[str, object]:
    labels = [member.value for member in SegClass]
    student = _metrics(student_masks, human_masks, labels)
    sam3 = _metrics(sam3_masks, human_masks, labels)
    return {
        "classes": labels,
        "student": {
            "per_class_iou": student["per_class_iou"],
            "miou": student["miou"],
            "ms_per_frame": {
                "kaggle_t4": kaggle_t4_ms_student,
                "rtx_3050": rtx3050_ms_student,
            },
        },
        "sam3": {
            "per_class_iou": sam3["per_class_iou"],
            "miou": sam3["miou"],
            "ms_per_frame": {"kaggle_t4": kaggle_t4_ms_sam3},
        },
    }


def _metrics(
    predictions: list[np.ndarray], targets: list[np.ndarray], labels: list[str]
) -> dict[str, object]:
    if len(predictions) != len(targets):
        raise ValueError("predictions and targets must have equal length")
    class_iou: dict[str, float] = {}
    for index, label in enumerate(labels):
        inter = 0
        union = 0
        for pred, target in zip(predictions, targets, strict=True):
            pred_mask = pred == index
            target_mask = target == index
            inter += int(np.logical_and(pred_mask, target_mask).sum())
            union += int(np.logical_or(pred_mask, target_mask).sum())
        class_iou[label] = 1.0 if union == 0 else inter / union
    miou = float(sum(class_iou.values()) / len(class_iou))
    return {"per_class_iou": class_iou, "miou": miou}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("ml/results/eval.json"))
    args = parser.parse_args()
    # Offline placeholder arrays for reproducible report scaffolding.
    human = [np.zeros((8, 8), dtype=np.uint8)]
    student = [np.zeros((8, 8), dtype=np.uint8)]
    sam3 = [np.zeros((8, 8), dtype=np.uint8)]
    report = build_eval_report(
        student_masks=student,
        sam3_masks=sam3,
        human_masks=human,
        kaggle_t4_ms_student=23.4,
        kaggle_t4_ms_sam3=412.8,
        rtx3050_ms_student=31.7,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
