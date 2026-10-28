from io import BytesIO

import httpx
import numpy as np
import pytest
from PIL import Image

from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError
from reefcase.vision.modal_client import ModalSegmenter


def test_modal_segmenter_posts_jpeg_and_decodes_png(make_settings) -> None:
    expected = np.array([[0, 1], [4, 5]], dtype=np.uint8)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer wk-id.ws-secret"
        image = Image.open(BytesIO(request.content))
        assert image.format == "JPEG"
        assert image.size == (2, 2)
        output = BytesIO()
        Image.fromarray(expected, mode="L").save(output, format="PNG")
        return httpx.Response(200, content=output.getvalue())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings: Settings = make_settings(
        sam_modal_url="https://modal.test/segment", sam_modal_token="wk-id.ws-secret"
    )
    segmenter = ModalSegmenter(settings, client=client)

    result = segmenter.segment(np.zeros((2, 2, 3), dtype=np.uint8))

    np.testing.assert_array_equal(result, expected)


def test_modal_segmenter_refuses_to_run_without_a_token(make_settings) -> None:
    settings: Settings = make_settings(sam_modal_url="https://modal.test/segment")

    with pytest.raises(ConfigError, match="REEFCASE_SAM_MODAL_TOKEN"):
        ModalSegmenter(settings)
