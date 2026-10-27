from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from importlib import import_module
from types import ModuleType
from typing import Any, Literal

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


class Sam3Segmenter:
    """Local SAM 3 backend with one vision-feature extraction per frame."""

    name: Literal["sam3"] = "sam3"

    def __init__(
        self,
        model_id: str = DEFAULT_SAM_MODEL_ID,
        *,
        model: Any = None,
        processor: Any = None,
    ) -> None:
        # Injected test doubles take numpy inputs as-is; real weights need torch.
        self._torch: ModuleType | None = None
        if model is None or processor is None:
            self._torch = import_module("torch")
            transformers = import_module("transformers")
            model = transformers.Sam3Model.from_pretrained(
                model_id, torch_dtype=self._torch.float16
            )
            model = model.to("cuda").eval()
            processor = transformers.Sam3Processor.from_pretrained(model_id)
        self._model = model
        self._processor = processor

    def segment(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("image must have shape HxWx3")
        height, width = image.shape[:2]
        class_map = np.zeros((height, width), dtype=np.uint8)
        coral_mask = np.zeros((height, width), dtype=bool)

        with self._no_grad():
            image_inputs = self._inputs(images=image)
            vision_embeds = self._model.get_vision_features(
                pixel_values=image_inputs["pixel_values"]
            )
            for prompt in _PROMPTS:
                outputs = self._model(**self._inputs(text=prompt), vision_embeds=vision_embeds)
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

        coral_classes = classify_coral_pixels(image, coral_mask)
        class_map[coral_mask] = coral_classes[coral_mask]
        return class_map

    def _inputs(self, **kwargs: object) -> Any:
        """Processor outputs, moved onto the GPU in the model's fp16 when torch is loaded."""
        inputs = self._processor(**kwargs, return_tensors="pt")
        if self._torch is None:
            return inputs
        return inputs.to("cuda", self._torch.float16)

    def _no_grad(self) -> AbstractContextManager[object]:
        if self._torch is None:
            return nullcontext()
        return self._torch.inference_mode()


def _result_mask(results: Sequence[Mapping[str, Any]], shape: tuple[int, int]) -> np.ndarray:
    if not results:
        return np.zeros(shape, dtype=bool)
    segmentation = results[0].get("masks")
    if segmentation is None:
        return np.zeros(shape, dtype=bool)
    if hasattr(segmentation, "detach"):
        segmentation = segmentation.detach().cpu().numpy()
    mask = np.asarray(segmentation, dtype=bool)
    if mask.ndim == 3:
        mask = np.any(mask, axis=0)
    if mask.shape != shape:
        raise ValueError("SAM 3 returned a mask with the wrong shape")
    return mask
