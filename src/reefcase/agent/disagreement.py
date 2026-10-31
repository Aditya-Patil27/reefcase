"""Teacher/student segmentation disagreement (architecture §5.6, FR11).

When ReefStudent and SAM 3 segment the same frame, their masks are compared on
the two classes the investigation hinges on, live and bleached coral. A mean IoU
under ``IOU_THRESHOLD`` marks the frame uncertain, and the SAM 3 mask wins.
"""

import numpy as np

from reefcase.core.schemas import MASK_INDEX, SegClass

__all__ = ["CORAL_CLASSES", "IOU_THRESHOLD", "coral_iou", "disagrees", "iou_per_class"]

IOU_THRESHOLD = 0.5
CORAL_CLASSES = (SegClass.LIVE_CORAL, SegClass.BLEACHED_CORAL)


def iou_per_class(mask_a: np.ndarray, mask_b: np.ndarray) -> dict[SegClass, float]:
    """IoU of two class maps for each class present in either; absent classes are left out."""
    if mask_a.shape != mask_b.shape:
        raise ValueError(f"mask shapes differ: {mask_a.shape} vs {mask_b.shape}")
    scores: dict[SegClass, float] = {}
    for cls, index in MASK_INDEX.items():
        in_a = mask_a == index
        in_b = mask_b == index
        union = int(np.count_nonzero(in_a | in_b))
        if union:
            scores[cls] = int(np.count_nonzero(in_a & in_b)) / union
    return scores


def coral_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Mean IoU over the coral classes either mask contains; 1.0 when neither has coral."""
    scores = iou_per_class(mask_a, mask_b)
    coral = [scores[cls] for cls in CORAL_CLASSES if cls in scores]
    return sum(coral) / len(coral) if coral else 1.0


def disagrees(iou: float) -> bool:
    """Whether a coral IoU is low enough for the SAM 3 mask to win."""
    return iou < IOU_THRESHOLD
