"""Quality scoring for extracted transect frames (Story 2.4; § 4.2, § 6.1, FR2, FR3)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from reefcase.core.errors import ReefCaseError
from reefcase.core.schemas import QualityScore

__all__ = [
    "BLUR_THRESHOLD",
    "COLOR_CAST_THRESHOLD",
    "TURBIDITY_THRESHOLD",
    "QualityError",
    "score",
]

BLUR_THRESHOLD: float = 100.0  # Minimum variance of Laplacian
TURBIDITY_THRESHOLD: float = 0.90  # Maximum turbidity (1 - RMS contrast)
COLOR_CAST_THRESHOLD: float = 60.0  # Maximum mean |a*| + |b*| in CIELAB


class QualityError(ReefCaseError):
    """Raised when quality scoring fails or footage fails quality thresholds."""


def _rgb_to_lab(image: np.ndarray[Any, Any]) -> NDArray[np.float64]:
    """Convert an sRGB uint8 image to CIELAB (D65)."""
    rgb: NDArray[np.float64] = image.astype(np.float64) / 255.0
    rgb = np.where(
        rgb <= 0.04045,
        rgb / 12.92,
        ((rgb + 0.055) / 1.055) ** 2.4,
    )
    xyz: NDArray[np.float64] = np.einsum(
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
    delta = 6.0 / 29.0
    transformed: NDArray[np.float64] = np.where(
        xyz > delta**3,
        np.cbrt(xyz),
        xyz / (3.0 * delta**2) + 4.0 / 29.0,
    )
    return np.stack(
        (
            116.0 * transformed[..., 1] - 16.0,
            500.0 * (transformed[..., 0] - transformed[..., 1]),
            200.0 * (transformed[..., 1] - transformed[..., 2]),
        ),
        axis=-1,
    )


def score(image: np.ndarray[Any, Any]) -> QualityScore:
    """Score an RGB image for blur, color cast, and turbidity.

    Args:
        image: RGB uint8 ndarray of shape HxWx3.

    Returns:
        QualityScore with computed metrics and pass/fail decision from the
        module thresholds.

    Raises:
        ValueError: If ``image`` is not a 3D array of shape HxWx3.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"image must have shape HxWx3, got {image.shape}")

    # Convert to grayscale luminance
    gray = 0.299 * image[..., 0] + 0.587 * image[..., 1] + 0.114 * image[..., 2]

    # Blur: variance of discrete 4-neighbour Laplacian
    if gray.shape[0] >= 3 and gray.shape[1] >= 3:
        lap = (
            gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
            - 4.0 * gray[1:-1, 1:-1]
        )
        blur = float(np.var(lap))
    else:
        blur = 0.0

    # Turbidity: 1 - RMS contrast (RMS contrast = std of normalized intensities)
    rms_contrast = float(np.std(gray / 255.0))
    turbidity = float(1.0 - rms_contrast)

    # Color cast: mean |a*| + |b*| in CIELAB
    lab = _rgb_to_lab(image)
    color_cast = float(np.mean(np.abs(lab[..., 1]) + np.abs(lab[..., 2])))

    reasons: list[str] = []
    if blur < BLUR_THRESHOLD:
        reasons.append("too blurry")
    if turbidity > TURBIDITY_THRESHOLD:
        reasons.append("too murky")
    if color_cast > COLOR_CAST_THRESHOLD:
        reasons.append("colour cast")

    passed = len(reasons) == 0
    reason = reasons[0] if reasons else None

    return QualityScore(
        blur=round(blur, 2),
        color_cast=round(color_cast, 2),
        turbidity=round(turbidity, 4),
        passed=passed,
        reason=reason,
    )
