import numpy as np

from reefcase.core.schemas import MASK_INDEX, SegClass

__all__ = ["cover_from_mask"]

_CLASS_BY_INDEX = {index: member for member, index in MASK_INDEX.items()}


def cover_from_mask(mask: np.ndarray) -> dict[SegClass, float]:
    """Return the fraction of pixels assigned to each segmentation class."""
    if mask.ndim != 2:
        raise ValueError("segmentation mask must be 2-D")
    pixel_count = mask.size
    if pixel_count == 0:
        raise ValueError("segmentation mask must not be empty")

    values, counts = np.unique(mask, return_counts=True)
    unknown = [int(value) for value in values if int(value) not in _CLASS_BY_INDEX]
    if unknown:
        raise ValueError(f"segmentation mask contains unknown class ids: {unknown}")

    counts_by_index = dict(zip(values.tolist(), counts.tolist(), strict=True))
    return {
        member: counts_by_index.get(index, 0) / pixel_count for member, index in MASK_INDEX.items()
    }
