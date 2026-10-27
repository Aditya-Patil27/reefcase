from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Literal, Protocol, cast

import numpy as np

from reefcase.core.config import DEFAULT_SAM_MODEL_ID
from reefcase.core.schemas import MASK_INDEX, SegClass
from reefcase.vision.bleaching import classify_coral_pixels

__all__ = ["Sam3Segmenter"]

_PROMPTS = ("sand", "rubble", "algae", "coral")
_PROMPT_CLASS = {
    "sand": SegClass.SAND,
    "rubble": SegClass.RUBBLE,
    "algae": SegClass.ALGAE,
}


class _Processor(Protocol):
    def __call__(self, **kwargs: object) -> Mapping[str, object]: ...

    def post_process_instance_segmentation(
        self,
        outputs: object,
        *,
        threshold: float,
        mask_threshold: float,
        target_sizes: list[tuple[int, int]],
    ) -> Sequence[Mapping[str, object]]: ...


class _Model(Protocol):
    def get_vision_features(self, **kwargs: object) -> object: ...

    def __call__(self, **kwargs: object) -> object: ...


class _TensorLike(Protocol):
    def detach(self) -> _TensorLike: ...

    def cpu(self) -> _TensorLike: ...

    def numpy(self) -> np.ndarray: ...


class Sam3Segmenter:
    """Local SAM 3 backend with one vision-feature extraction per frame."""

    name: Literal["sam3"] = "sam3"

    def __init__(
        self,
        model_id: str = DEFAULT_SAM_MODEL_ID,
        *,
        model: _Model | None = None,
        processor: _Processor | None = None,
    ) -> None:
        if model is None or processor is None:
            model, processor = self._load(model_id)
        self._model = model
        self._processor = processor

    def segment(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("image must have shape HxWx3")
        height, width = image.shape[:2]
        base_inputs = self._processor(images=image, return_tensors="pt")
        vision_features = self._model.get_vision_features(**base_inputs)
        class_map = np.zeros((height, width), dtype=np.uint8)
        coral_mask = np.zeros((height, width), dtype=bool)

        for prompt in _PROMPTS:
            prompt_inputs = self._processor(
                images=image,
                text=prompt,
                return_tensors="pt",
            )
            outputs = self._model(
                **prompt_inputs,
                vision_features=vision_features,
            )
            results = self._processor.post_process_instance_segmentation(
                outputs,
                threshold=0.5,
                mask_threshold=0.5,
                target_sizes=[(height, width)],
            )
            prompt_mask = _result_mask(results, (height, width))
            if prompt == "coral":
                coral_mask |= prompt_mask
            else:
                class_map[prompt_mask] = MASK_INDEX[_PROMPT_CLASS[prompt]]

        class_map[coral_mask] = MASK_INDEX[SegClass.LIVE_CORAL]
        coral_classes = classify_coral_pixels(image, coral_mask)
        class_map[coral_mask] = coral_classes[coral_mask]
        return class_map

    @staticmethod
    def _load(model_id: str) -> tuple[_Model, _Processor]:
        transformers = import_module("transformers")
        torch = import_module("torch")
        model_type = getattr(transformers, "Sam3Model")  # noqa: B009
        processor_type = getattr(transformers, "Sam3Processor")  # noqa: B009
        model = model_type.from_pretrained(model_id, torch_dtype=torch.float16)
        model = model.to("cuda").eval()
        processor = processor_type.from_pretrained(model_id)
        return cast(_Model, model), cast(_Processor, processor)


def _result_mask(results: Sequence[Mapping[str, object]], shape: tuple[int, int]) -> np.ndarray:
    if not results:
        return np.zeros(shape, dtype=bool)
    segmentation: object = results[0].get("segmentation")
    if segmentation is None:
        return np.zeros(shape, dtype=bool)
    if hasattr(segmentation, "detach"):
        tensor = cast(_TensorLike, segmentation)
        segmentation = tensor.detach().cpu().numpy()
    mask = np.asarray(segmentation, dtype=bool)
    if mask.ndim == 3:
        mask = np.any(mask, axis=0)
    if mask.shape != shape:
        raise ValueError("SAM 3 returned a mask with the wrong shape")
    return mask
