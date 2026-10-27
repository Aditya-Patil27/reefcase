"""SAM 3 Modal endpoint and an offline dry-run.

Human deployment command:
    modal deploy ml/modal/sam_endpoint.py
"""

from __future__ import annotations

import argparse
from io import BytesIO

import numpy as np
from PIL import Image

from reefcase.vision.fake import FakeSegmenter

try:
    import modal
except ImportError:  # pragma: no cover - Modal is a human deployment dependency.
    modal = None


def segment_jpeg(payload: bytes) -> bytes:
    image = np.asarray(Image.open(BytesIO(payload)).convert("RGB"), dtype=np.uint8)
    mask = FakeSegmenter().segment(image)
    output = BytesIO()
    Image.fromarray(mask, mode="L").save(output, format="PNG")
    return output.getvalue()


def dry_run() -> None:
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    encoded = BytesIO()
    Image.fromarray(image, mode="RGB").save(encoded, format="JPEG")
    decoded = np.asarray(Image.open(BytesIO(segment_jpeg(encoded.getvalue()))))
    print(f"dry-run: {decoded.shape[0]}x{decoded.shape[1]} uint8 PNG class map")


if modal is not None:  # pragma: no cover - requires Modal CLI and credentials.
    app = modal.App("reefcase-sam3")
    image = modal.Image.debian_slim().pip_install("numpy", "pillow")

    @app.function(image=image)
    def segment(payload: bytes) -> bytes:
        return segment_jpeg(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
    else:
        parser.error("use --dry-run locally; deployment is a human step")
