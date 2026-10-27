import numpy as np

from reefcase.core.schemas import MASK_INDEX, SegClass
from reefcase.vision.bleaching import classify_coral_pixels


def test_classify_coral_pixels_applies_lightness_and_chroma_thresholds() -> None:
    image = np.array(
        [
            [[255, 255, 255], [175, 70, 35]],
            [[180, 180, 180], [255, 255, 255]],
        ],
        dtype=np.uint8,
    )
    coral_mask = np.array([[True, True], [False, True]])

    classes = classify_coral_pixels(image, coral_mask)

    assert classes.tolist() == [
        [MASK_INDEX[SegClass.BLEACHED_CORAL], MASK_INDEX[SegClass.LIVE_CORAL]],
        [0, MASK_INDEX[SegClass.BLEACHED_CORAL]],
    ]


def test_pure_white_and_saturated_brown_are_bleached_and_live() -> None:
    image = np.array([[[255, 255, 255], [120, 55, 20]]], dtype=np.uint8)
    coral_mask = np.ones((1, 2), dtype=bool)

    classes = classify_coral_pixels(image, coral_mask)

    assert classes[0, 0] == MASK_INDEX[SegClass.BLEACHED_CORAL]
    assert classes[0, 1] == MASK_INDEX[SegClass.LIVE_CORAL]
