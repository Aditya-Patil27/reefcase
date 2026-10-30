"""Story 8.3 AC 1: the demo clip stitches the 2024 photos so ingest samples each one once."""

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from reefcase.ingest.frames import extract_candidates

REPO_ROOT = Path(__file__).parents[2]
FRAMES_DIR = REPO_ROOT / "tests" / "fixtures" / "frames"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_demo_clip", REPO_ROOT / "scripts" / "build_demo_clip.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bdc = _load_script()


def _photos(tmp_path: Path, count: int) -> list[Path]:
    photos: list[Path] = []
    for index in range(count):
        path = tmp_path / "clip" / f"photo_{index + 1:02d}.jpg"
        path.parent.mkdir(exist_ok=True)
        shutil.copy(FRAMES_DIR / f"0{index % 6 + 1}.jpg", path)
        photos.append(path)
    return photos


def test_photo_urls_number_the_station_photos() -> None:
    urls = bdc.photo_urls(3)

    assert [url.rsplit("/", 1)[1] for url in urls] == [
        "OCC-HAW-002_2024_01.JPG",
        "OCC-HAW-002_2024_02.JPG",
        "OCC-HAW-002_2024_03.JPG",
    ]
    assert all(url.startswith("https://www.ncei.noaa.gov/") for url in urls)


def test_fetch_missing_downloads_only_absent_photos(tmp_path: Path) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=b"jpeg bytes")

    present = tmp_path / "OCC-HAW-002_2024_01.JPG"
    present.write_bytes(b"already here")
    urls = ["https://example.org/OCC-HAW-002_2024_01.JPG", "https://example.org/OCC-HAW-002_2024_02.JPG"]

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        paths = bdc.fetch_missing(urls, tmp_path, client)

    assert paths == [present, tmp_path / "OCC-HAW-002_2024_02.JPG"]
    assert requested == ["https://example.org/OCC-HAW-002_2024_02.JPG"]
    assert present.read_bytes() == b"already here"
    assert paths[1].read_bytes() == b"jpeg bytes"
    assert not list(tmp_path.glob("*.part"))


def test_stitch_holds_each_photo_for_one_sampling_interval(tmp_path: Path) -> None:
    photos = _photos(tmp_path, 8)
    clip = tmp_path / "clip.mp4"

    bdc.stitch(photos, clip)

    candidates = list(extract_candidates(clip, every_sec=bdc.HOLD_SEC))
    assert [c.t_sec for c in candidates] == [i * bdc.HOLD_SEC for i in range(len(photos))]
    assert candidates[0].image.shape == (256, 256, 3)


def test_stitch_shrinks_large_photos_to_even_sides(tmp_path: Path) -> None:
    from PIL import Image

    photo = tmp_path / "big.jpg"
    Image.new("RGB", (4001, 3001), (20, 90, 120)).save(photo)
    clip = tmp_path / "clip.mp4"

    bdc.stitch([photo], clip)

    (candidate,) = extract_candidates(clip, every_sec=bdc.HOLD_SEC)
    height, width, _ = candidate.image.shape
    assert max(width, height) <= bdc.MAX_SIDE
    assert width % 2 == 0 and height % 2 == 0


def test_stitch_needs_a_photo(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no photos"):
        bdc.stitch([], tmp_path / "clip.mp4")
