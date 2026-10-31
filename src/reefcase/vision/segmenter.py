from typing import Protocol, runtime_checkable

import numpy as np

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError
from reefcase.core.schemas import SegBackend
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.fake import FakeSegmenter

__all__ = ["Segmenter", "build_checker", "build_segmenter", "cover_from_mask"]


@runtime_checkable
class Segmenter(Protocol):
    @property
    def name(self) -> SegBackend: ...

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
    if settings.segmenter == "sam3_modal":
        from reefcase.vision.modal_client import ModalSegmenter

        return ModalSegmenter(settings)
    if settings.segmenter == "student":
        from reefcase.vision.student import StudentSegmenter

        return StudentSegmenter(settings)
    raise ConfigError(f"segmenter backend {settings.segmenter!r} is not available yet")


def build_checker(settings: Settings) -> Segmenter | None:
    """SAM 3 on Modal to cross-check ReefStudent (Story 5.5), or ``None``.

    Only when ``REEFCASE_DISAGREEMENT_CHECK`` is on, the segmenter is ``student`` and the
    Modal endpoint is configured.
    """
    if not settings.disagreement_check or settings.segmenter != "student":
        return None
    if settings.sam_modal_url is None or settings.sam_modal_token is None:
        return None
    from reefcase.vision.modal_client import ModalSegmenter

    return ModalSegmenter(settings)
