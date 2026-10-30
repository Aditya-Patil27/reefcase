import numpy as np
import pytest

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError
from reefcase.vision.student import StudentSegmenter, model_input_size


class DummyStudentSegmenter(StudentSegmenter):
    def __init__(self, device: str) -> None:
        self._device = device
        self._weights = None
        self._model = object()

    def _predict(self, image: np.ndarray) -> np.ndarray:
        logits = np.zeros((6, image.shape[0], image.shape[1]), dtype=np.float32)
        logits[5, :, :] = 1.0
        return logits


def test_student_segmenter_returns_class_map_contract() -> None:
    segmenter = DummyStudentSegmenter(device="cpu")

    result = segmenter.segment(np.zeros((4, 6, 3), dtype=np.uint8))

    assert result.shape == (4, 6)
    assert result.dtype == np.uint8
    assert set(np.unique(result)) == {5}


def test_student_segmenter_requires_weights_path(make_settings) -> None:
    settings: Settings = make_settings(segmenter="student", student_weights=None)

    with pytest.raises(ConfigError, match="REEFCASE_STUDENT_WEIGHTS"):
        StudentSegmenter(settings)


def test_student_segmenter_prefers_cuda_when_available(monkeypatch) -> None:
    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return True

    class _Torch:
        cuda = _Cuda()

    monkeypatch.setattr("reefcase.vision.student.import_module", lambda _: _Torch())
    assert StudentSegmenter._pick_device() == "cuda"


def test_model_input_size_keeps_aspect_on_a_32_pixel_grid() -> None:
    assert model_input_size(1024, 2048) == (512, 1024)
    assert model_input_size(1080, 1920) == (576, 1024)
    assert model_input_size(540, 960) == (576, 1024)
