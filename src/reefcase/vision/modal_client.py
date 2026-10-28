from __future__ import annotations

from io import BytesIO
from typing import Literal

import httpx
import numpy as np
from PIL import Image

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError

__all__ = ["ModalSegmenter"]


class ModalSegmenter:
    """HTTP client for the deployed SAM 3 Modal endpoint."""

    name: Literal["sam3"] = "sam3"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if settings.sam_modal_url is None:
            raise ConfigError("REEFCASE_SAM_MODAL_URL is required for ModalSegmenter")
        if settings.sam_modal_token is None:
            raise ConfigError("REEFCASE_SAM_MODAL_TOKEN is required for ModalSegmenter")
        self._url = settings.sam_modal_url
        # Modal proxy auth: the endpoint rejects anyone without this workspace token.
        self._auth = f"Bearer {settings.sam_modal_token.get_secret_value()}"
        self._client = client or httpx.Client(timeout=60.0)

    def segment(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError("image must be an HxWx3 uint8 RGB array")
        encoded = BytesIO()
        Image.fromarray(image, mode="RGB").save(encoded, format="JPEG", quality=90)
        response = self._client.post(
            self._url,
            content=encoded.getvalue(),
            headers={"content-type": "image/jpeg", "authorization": self._auth},
        )
        response.raise_for_status()
        mask = np.asarray(Image.open(BytesIO(response.content)).convert("L"), dtype=np.uint8)
        if mask.ndim != 2 or mask.shape != image.shape[:2]:
            raise ValueError("Modal endpoint returned a class map with the wrong shape")
        return mask
