"""Build the demo dive clip from the 2024 NCRMP photos of station HAW-41 (Story 8.3 AC 1).

NCRMP 2024 fixed-site photos of OCC-HAW-002 (the same North Kohala station as the historical
surveys, 8.1) are downloaded from NCEI into the gitignored ``data/demo/clip/`` and stitched into
an H.264 clip. Each photo is held for ``HOLD_SEC``, the ingest sampling interval, so every photo
becomes exactly one candidate frame. Cite NOAA PIFSC ESD (see data/LICENSES.md).

Upload the clip with lat 20.268249, lon -155.860434 and dive date 2024-07-06.

Usage:
    uv run python scripts/build_demo_clip.py                    # data/demo/haw41_2024.mp4
    uv run python scripts/build_demo_clip.py --out clip.mp4
"""

# pyright: reportUnknownMemberType=false
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
import httpx
from PIL import Image

logger = logging.getLogger("build_demo_clip")

SOURCE_DIR = (
    "https://www.ncei.noaa.gov/data/oceans/archive/arc0247/0317534/1.1/data/0-data/"
    "NCRMP_FIXED_IMAGES_HAWAII_2024"
)
STATION = "OCC-HAW-002_2024"
PHOTO_COUNT = 30
PHOTO_DIR = Path("data/demo/clip")
DEFAULT_OUT = Path("data/demo/haw41_2024.mp4")
HOLD_SEC = 0.5  # the default ingest sampling interval (reefcase.ingest.frames)
MAX_SIDE = 1920
DOWNLOAD_TIMEOUT_S = 180.0


def photo_urls(count: int = PHOTO_COUNT) -> list[str]:
    """The NCEI URLs of the station's numbered photos, 1 to ``count``."""
    return [f"{SOURCE_DIR}/{STATION}_{n:02d}.JPG" for n in range(1, count + 1)]


def fetch_missing(urls: Sequence[str], folder: Path, client: httpx.Client) -> list[Path]:
    """Download every photo not yet in ``folder``; return the local paths in ``urls`` order."""
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for url in urls:
        path = folder / url.rsplit("/", 1)[1]
        if not path.is_file():
            part = path.with_name(path.name + ".part")
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
            part.replace(path)
            logger.info("downloaded %s", path.name)
        paths.append(path)
    return paths


def _even_size(path: Path) -> tuple[int, int]:
    """The photo's size shrunk to ``MAX_SIDE``, rounded down to even sides for yuv420p."""
    with Image.open(path) as img:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        width, height = img.size
    return width - width % 2, height - height % 2


def stitch(photos: Sequence[Path], out: Path) -> None:
    """Encode ``photos`` as an H.264 clip, each held for ``HOLD_SEC``, all at the first one's size."""
    if not photos:
        raise ValueError("no photos to stitch")
    width, height = _even_size(photos[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(out), mode="w") as container:
        stream: Any = container.add_stream("libx264", rate=Fraction(1) / Fraction(HOLD_SEC))
        stream.width, stream.height = width, height
        stream.pix_fmt = "yuv420p"
        for index, path in enumerate(photos):
            with Image.open(path) as img:
                rgb = img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
            frame = av.VideoFrame.from_image(rgb)
            frame.pts = index
            container.mux(stream.encode(frame))
        container.mux(stream.encode())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with httpx.Client(timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True) as client:
        photos = fetch_missing(photo_urls(), PHOTO_DIR, client)
    stitch(photos, args.out)
    size_mb = args.out.stat().st_size / 1e6
    logger.info("%s: %d photos, %.1f s, %.1f MB", args.out, len(photos), len(photos) * HOLD_SEC, size_mb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
