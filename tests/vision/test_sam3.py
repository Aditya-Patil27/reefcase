from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from reefcase.core.schemas import MASK_INDEX, SegClass
from reefcase.vision.sam3 import Sam3Segmenter, _result_mask  # pyright: ignore[reportPrivateUsage]


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


def test_sam3_no_instances_gives_an_empty_mask_at_frame_size() -> None:
    # Real SAM 3 returns (0, 288, 288) when nothing matches, not (0, H, W).
    empty = np.zeros((0, 288, 288), dtype=bool)

    mask = _result_mask([{"masks": empty}], (2, 4))

    assert mask.shape == (2, 4)
    assert not mask.any()


@pytest.mark.gpu
def test_sam3_real_weights_segment_a_fixture_frame() -> None:
    """Real `facebook/sam3` on CUDA. Needs `uv sync --group gpu` and HF_TOKEN with gated access."""
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("no CUDA device")
    frame = Path(__file__).parents[1] / "fixtures" / "frames" / "01.jpg"
    image = np.asarray(Image.open(frame).convert("RGB"))

    result = Sam3Segmenter().segment(image)

    assert result.dtype == np.uint8
    assert result.shape == image.shape[:2]
    # Fixture frames are synthetic shapes SAM 3 may not recognise: check the contract only.
    assert set(np.unique(result).tolist()) <= set(MASK_INDEX.values())
