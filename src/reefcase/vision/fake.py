"""The offline segmenter used by every pipeline test (architecture §5.1, §11).

``FakeSegmenter`` implements the ``Segmenter`` protocol with a deterministic,
content-independent class map: a pure function of the image shape, so tests can
assert exact covers. The pattern is row bands in cover order — SAND 0.5,
LIVE_CORAL 0.25, ALGAE 0.125, RUBBLE 0.125 — with a two-column BLEACHED_CORAL
strip and a one-column OTHER strip so all six §4.2 classes are always present.
"""

import numpy as np

from reefcase.core.schemas import MASK_INDEX, SegBackend, SegClass

__all__ = ["FakeSegmenter"]


class FakeSegmenter:
    """Deterministic stand-in for the SAM 3 / ReefStudent backends."""

    name: SegBackend = "fake"

    def segment(self, image: np.ndarray) -> np.ndarray:
        """Map an HxWx3 uint8 RGB image to an HxW uint8 class map (§4.2 indices)."""
        height, width = image.shape[:2]
        sand_end = height // 2
        live_coral_end = sand_end + height // 4
        algae_end = live_coral_end + height // 8

        mask = np.full((height, width), MASK_INDEX[SegClass.RUBBLE], dtype=np.uint8)
        mask[:algae_end] = MASK_INDEX[SegClass.ALGAE]
        mask[:live_coral_end] = MASK_INDEX[SegClass.LIVE_CORAL]
        mask[:sand_end] = MASK_INDEX[SegClass.SAND]
        mask[sand_end:live_coral_end, : min(2, width)] = MASK_INDEX[SegClass.BLEACHED_CORAL]
        mask[:sand_end, :1] = MASK_INDEX[SegClass.OTHER]
        return mask
