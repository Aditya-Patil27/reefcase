import numpy as np
import pytest

from reefcase.core.config import Settings
from reefcase.core.schemas import MASK_INDEX, SegClass
from reefcase.vision.fake import FakeSegmenter
from reefcase.vision.segmenter import Segmenter, build_segmenter, cover_from_mask


def test_cover_from_mask_returns_fraction_for_each_class() -> None:
    mask = np.array(
        [
            [MASK_INDEX[SegClass.OTHER], MASK_INDEX[SegClass.LIVE_CORAL]],
            [MASK_INDEX[SegClass.BLEACHED_CORAL], MASK_INDEX[SegClass.ALGAE]],
            [MASK_INDEX[SegClass.RUBBLE], MASK_INDEX[SegClass.SAND]],
        ],
        dtype=np.uint8,
    )

    cover = cover_from_mask(mask)

    assert cover == {member: pytest.approx(1 / 6) for member in SegClass}
    assert sum(cover.values()) == pytest.approx(1.0, abs=1e-6)


def test_cover_from_mask_rejects_non_2d_mask() -> None:
    with pytest.raises(ValueError, match="2-D"):
        cover_from_mask(np.zeros((2, 2, 1), dtype=np.uint8))


def test_build_segmenter_selects_fake_backend(make_settings) -> None:
    settings: Settings = make_settings(segmenter="fake")

    segmenter = build_segmenter(settings)

    assert isinstance(segmenter, FakeSegmenter)
    assert isinstance(segmenter, Segmenter)
