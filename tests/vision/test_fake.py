"""Story 1.5 AC 2 — FakeSegmenter: deterministic, shape-faithful class maps."""

from typing import Literal

import numpy as np
import pytest

from reefcase.core.schemas import MASK_INDEX
from reefcase.vision.fake import FakeSegmenter


def _image(height: int, width: int, seed: int) -> np.ndarray:
    """An HxWx3 uint8 RGB image whose content varies with ``seed``."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def test_segmenter_name_is_fake() -> None:
    segmenter: FakeSegmenter = FakeSegmenter()
    name: Literal["sam3", "student", "fake"] = segmenter.name
    assert name == "fake"


def test_segment_returns_same_shape_uint8_class_map() -> None:
    image = _image(48, 64, seed=0)
    mask = FakeSegmenter().segment(image)
    assert mask.shape == (48, 64)
    assert mask.dtype == np.uint8
    assert int(mask.min()) >= 0
    assert int(mask.max()) <= 5


@pytest.mark.parametrize(
    ("height", "width"),
    [(1, 1), (7, 3), (64, 64), (256, 256), (240, 320)],
)
def test_segment_matches_any_shape(height: int, width: int) -> None:
    mask = FakeSegmenter().segment(_image(height, width, seed=1))
    assert mask.shape == (height, width)


def test_segment_is_deterministic_and_content_independent() -> None:
    segmenter = FakeSegmenter()
    image_a = _image(32, 32, seed=2)
    image_b = _image(32, 32, seed=3)
    assert np.array_equal(segmenter.segment(image_a), segmenter.segment(image_a))
    assert np.array_equal(segmenter.segment(image_a), segmenter.segment(image_b))


def test_segment_pattern_covers_all_six_classes() -> None:
    mask = FakeSegmenter().segment(_image(256, 256, seed=4))
    present = set(np.unique(mask).tolist())
    assert present == set(MASK_INDEX.values())
