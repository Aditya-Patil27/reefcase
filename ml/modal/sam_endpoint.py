"""SAM 3 Modal endpoint and an offline dry-run.

Human deployment command (needs a Modal secret named ``huggingface`` holding
``HF_TOKEN``, because ``facebook/sam3`` is gated):
    modal deploy ml/modal/sam_endpoint.py

The printed ``...segment.modal.run`` URL goes in ``REEFCASE_SAM_MODAL_URL``, and a
proxy-auth token (``modal workspace proxy-tokens``) goes in ``REEFCASE_SAM_MODAL_TOKEN``
as ``<id>.<secret>``.

Credit guards: one T4 at most, scale to zero after 30 s idle, 60 s per request, and
no warm containers. Do not add ``min_containers``: that bills around the clock.
"""

from __future__ import annotations

import argparse
from io import BytesIO

import numpy as np
from PIL import Image

from reefcase.vision.fake import FakeSegmenter
from reefcase.vision.segmenter import Segmenter

try:
    import modal
except ImportError:  # pragma: no cover - Modal is a human deployment dependency.
    modal = None


def segment_jpeg(payload: bytes, segmenter: Segmenter) -> bytes:
    image = np.asarray(Image.open(BytesIO(payload)).convert("RGB"), dtype=np.uint8)
    mask = segmenter.segment(image)
    output = BytesIO()
    Image.fromarray(mask, mode="L").save(output, format="PNG")
    return output.getvalue()


def dry_run() -> None:
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    encoded = BytesIO()
    Image.fromarray(image, mode="RGB").save(encoded, format="JPEG")
    png = segment_jpeg(encoded.getvalue(), FakeSegmenter())
    decoded = np.asarray(Image.open(BytesIO(png)))
    print(f"dry-run: {decoded.shape[0]}x{decoded.shape[1]} uint8 PNG class map")


if modal is not None:  # pragma: no cover - requires Modal CLI and credentials.
    from fastapi import Request, Response

    app = modal.App("reefcase-sam3")
    image = (
        modal.Image.debian_slim(python_version="3.14")
        .pip_install(
            # Same versions as the `gpu` group in pyproject.toml.
            "torch==2.14.1",
            "torchvision==0.29.1",
            "transformers==5.20.2",
            "numpy",
            "pillow",
            "pydantic",
            "pydantic-settings",
            "fastapi[standard]",
        )
        .add_local_python_source("reefcase")
    )

    # Keeps the 3.3 GB of weights between cold starts instead of re-downloading them.
    hf_cache = modal.Volume.from_name("reefcase-hf-cache", create_if_missing=True)

    @app.cls(
        gpu="T4",
        # The 0.125-core default starves kernel launches: 0.8 s inference took 25-60 s.
        cpu=2.0,
        image=image,
        secrets=[modal.Secret.from_name("huggingface")],
        volumes={"/root/.cache/huggingface": hf_cache},
        max_containers=1,
        scaledown_window=30,
        timeout=60,
        # The first cold start downloads the weights; startup otherwise inherits 60 s.
        startup_timeout=600,
    )
    class Sam3Endpoint:
        @modal.enter()
        def load(self) -> None:
            from reefcase.vision.sam3 import Sam3Segmenter

            self.segmenter = Sam3Segmenter()

        @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
        async def segment(self, request: Request) -> Response:
            png = segment_jpeg(await request.body(), self.segmenter)
            return Response(content=png, media_type="image/png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
    else:
        parser.error("use --dry-run locally; deployment is a human step")
