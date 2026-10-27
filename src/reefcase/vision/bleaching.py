from typing import cast

import numpy as np
from numpy.typing import NDArray

from reefcase.core.schemas import MASK_INDEX, SegClass

__all__ = ["classify_coral_pixels"]


def classify_coral_pixels(image: np.ndarray, coral_mask: np.ndarray) -> np.ndarray:
    """Classify coral pixels as live or bleached using CIELAB thresholds."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must have shape HxWx3")
    if coral_mask.ndim != 2 or coral_mask.shape != image.shape[:2]:
        raise ValueError("coral_mask must have shape HxW matching image")

    lab = _rgb_to_lab(image)
    lightness = lab[..., 0]
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    bleached = coral_mask & (lightness >= 80.0) & (chroma <= 12.0)

    classes = np.zeros(coral_mask.shape, dtype=np.uint8)
    classes[coral_mask] = MASK_INDEX[SegClass.LIVE_CORAL]
    classes[bleached] = MASK_INDEX[SegClass.BLEACHED_CORAL]
    return classes


def _rgb_to_lab(image: np.ndarray) -> np.ndarray:
    rgb = image.astype(np.float64) / 255.0
    rgb = np.where(
        rgb <= 0.04045,
        rgb / 12.92,
        ((rgb + 0.055) / 1.055) ** 2.4,
    )
    xyz = np.einsum(
        "...c,dc->...d",
        rgb,
        np.array(
            [
                [0.4124564, 0.3575761, 0.1804375],
                [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041],
            ]
        ),
    )
    xyz /= np.array([0.95047, 1.0, 1.08883])
    delta = 6 / 29
    transformed = cast(
        NDArray[np.float64],
        np.where(
            xyz > delta**3,
            np.cbrt(xyz),
            xyz / (3 * delta**2) + 4 / 29,
        ),
    )
    return np.stack(
        (
            116 * transformed[..., 1] - 16,
            500 * (transformed[..., 0] - transformed[..., 1]),
            200 * (transformed[..., 1] - transformed[..., 2]),
        ),
        axis=-1,
    )
