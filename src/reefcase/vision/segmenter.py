from typing import Literal, Protocol, runtime_checkable

import numpy as np

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.fake import FakeSegmenter

__all__ = ["Segmenter", "build_segmenter", "cover_from_mask"]


@runtime_checkable
class Segmenter(Protocol):
    name: Literal["sam3", "student", "fake"]

    def segment(self, image: np.ndarray) -> np.ndarray:
        """Map an HxWx3 RGB image to an HxW class map."""
        ...


def build_segmenter(settings: Settings) -> Segmenter:
    """Build the configured segmentation backend."""
    if settings.segmenter == "fake":
        return FakeSegmenter()
    if settings.segmenter == "sam3_local":
        from reefcase.vision.sam3 import Sam3Segmenter

        return Sam3Segmenter(settings.sam_model_id)
    raise ConfigError(f"segmenter backend {settings.segmenter!r} is not available yet")
