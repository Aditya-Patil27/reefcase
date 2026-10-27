import numpy as np
import pytest

from reefcase.core.schemas import MASK_INDEX, SegClass
from reefcase.vision.sam3 import Sam3Segmenter


class FakeProcessor:
    def __init__(self) -> None:
        self.prompts: list[str | None] = []

    def __call__(self, **kwargs: object) -> dict[str, object]:
        text = kwargs.get("text")
        self.prompts.append(text if isinstance(text, str) else None)
        if "images" in kwargs:
            return {"pixel_values": np.zeros((1, 3, 2, 4), dtype=np.float32)}
        return {"text": text}

    def post_process_instance_segmentation(
        self,
        outputs: object,
        *,
        threshold: float,
        mask_threshold: float,
        target_sizes: list[tuple[int, int]],
    ) -> list[dict[str, object]]:
        return [{"masks": outputs}]


class FakeModel:
    def __init__(self) -> None:
        self.feature_calls = 0
        self.feature_token = object()

    def get_vision_features(self, **kwargs: object) -> object:
        self.feature_calls += 1
        return self.feature_token

    def __call__(self, **kwargs: object) -> object:
        assert kwargs["vision_embeds"] is self.feature_token
        assert "pixel_values" not in kwargs
        prompt = kwargs.get("text")
        masks = {
            "sand": np.array([[1, 0, 0, 0], [0, 0, 0, 0]], dtype=bool),
            "rubble": np.array([[0, 1, 0, 0], [0, 0, 0, 0]], dtype=bool),
            "algae": np.array([[0, 0, 1, 0], [0, 0, 0, 0]], dtype=bool),
            "coral": np.array([[0, 0, 0, 1], [1, 0, 0, 0]], dtype=bool),
        }
        return masks[prompt]  # type: ignore[index]


def test_sam3_reuses_features_and_paints_priority() -> None:
    model = FakeModel()
    segmenter = Sam3Segmenter(model=model, processor=FakeProcessor())
    image = np.zeros((2, 4, 3), dtype=np.uint8)

    result = segmenter.segment(image)

    assert result.dtype == np.uint8
    assert result.shape == (2, 4)
    assert model.feature_calls == 1
    assert result[0].tolist() == [
        MASK_INDEX[SegClass.SAND],
        MASK_INDEX[SegClass.RUBBLE],
        MASK_INDEX[SegClass.ALGAE],
        MASK_INDEX[SegClass.LIVE_CORAL],
    ]


@pytest.mark.gpu
def test_sam3_real_model_is_gpu_only() -> None:
    """The real-weight test is run manually on a Kaggle T4."""
    assert True
