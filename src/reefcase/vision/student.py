from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Literal, Protocol, cast

import numpy as np

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError

__all__ = ["StudentSegmenter"]


class _TorchModel(Protocol):
    def to(self, device: str): ...

    def eval(self): ...

    def __call__(self, tensor: object) -> object: ...


class _TensorLike(Protocol):
    def detach(self) -> _TensorLike: ...

    def cpu(self) -> _TensorLike: ...

    def numpy(self) -> np.ndarray: ...


class StudentSegmenter:
    """ReefStudent segmenter with CUDA preferred and CPU fallback."""

    name: Literal["student"] = "student"

    def __init__(self, settings: Settings) -> None:
        if settings.student_weights is None:
            raise ConfigError("REEFCASE_STUDENT_WEIGHTS is required for student segmenter")
        self._weights = settings.student_weights
        self._device = self._pick_device()
        self._model = self._load_model(self._weights, self._device)

    @property
    def device(self) -> str:
        return self._device

    def segment(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError("image must be an HxWx3 uint8 RGB array")
        logits = self._predict(image)
        class_map = np.argmax(logits, axis=0).astype(np.uint8, copy=False)
        if class_map.shape != image.shape[:2]:
            raise ValueError("student model returned an invalid class-map shape")
        return class_map

    def _predict(self, image: np.ndarray) -> np.ndarray:
        torch = import_module("torch")
        tensor = torch.from_numpy(image.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
        tensor = tensor.to(self._device)
        outputs: object = self._model(tensor)
        if hasattr(outputs, "detach"):
            tensor_like = cast(_TensorLike, outputs)
            outputs = tensor_like.detach().cpu().numpy()
        logits = np.asarray(outputs, dtype=np.float32)
        if logits.ndim != 4 or logits.shape[0] != 1:
            raise ValueError("student model output must have shape [1, classes, H, W]")
        return logits[0]

    @staticmethod
    def _pick_device() -> str:
        try:
            torch = import_module("torch")
        except ModuleNotFoundError:
            return "cpu"
        cuda = getattr(torch, "cuda", None)
        has_is_available = callable(getattr(cuda, "is_available", None))
        if cuda is not None and has_is_available and cuda.is_available():
            return "cuda"
        return "cpu"

    @staticmethod
    def _load_model(weights: Path, device: str) -> _TorchModel:
        try:
            torch = import_module("torch")
            smp = import_module("segmentation_models_pytorch")
        except ModuleNotFoundError as exc:
            raise ConfigError(
                "student backend requires torch and segmentation_models_pytorch"
            ) from exc
        model = smp.Unet("efficientnet-b0", classes=6, in_channels=3)
        state = torch.load(weights, map_location=device)
        model.load_state_dict(state)
        model = model.to(device).eval()
        return cast(_TorchModel, model)
