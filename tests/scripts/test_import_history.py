"""Story 8.1: import past NCRMP survey photos as historical surveys.

AC: a manifest of (image path, lat, lon, date, source, licence) becomes ``historical`` surveys
grouped by site and date, segmented by the configured segmenter, with no agent run.
"""

import importlib.util
import shutil
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import httpx
import numpy as np
import pytest
from PIL import Image

from reefcase.core.schemas import SurveyStatus
from reefcase.store.db import Store
from reefcase.vision.fake import FakeSegmenter

REPO_ROOT = Path(__file__).parents[2]
FRAMES_DIR = REPO_ROOT / "tests" / "fixtures" / "frames"
HEADER = "image_path,site,lat,lon,date,source,licence"
LICENCE = "US Gov; cite NOAA PIFSC ESD"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "import_history", REPO_ROOT / "scripts" / "import_history.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up while it executes
    spec.loader.exec_module(module)
    return module


ih = _load_script()


def _manifest(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "manifest.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


def _photo(tmp_path: Path, name: str, fixture: str = "01.jpg") -> str:
    (tmp_path / "history").mkdir(exist_ok=True)
    shutil.copy(FRAMES_DIR / fixture, tmp_path / "history" / name)
    return f"history/{name}"


def _row(image: str, lat: float, lon: float, day: str, site: str = "HAW-41") -> str:
    return f"{image},{site},{lat},{lon},{day},https://example.org/{image},{LICENCE}"


def test_read_manifest_resolves_paths_against_the_manifest(tmp_path: Path) -> None:
    image = _photo(tmp_path, "a.jpg")
    rows = ih.read_manifest(_manifest(tmp_path, [_row(image, 20.26828, -155.8604, "2013-08-03")]))

    assert len(rows) == 1
    row = rows[0]
    assert row.image_path == tmp_path / "history" / "a.jpg"
    assert (row.site, row.lat, row.lon) == ("HAW-41", 20.26828, -155.8604)
    assert row.dive_date == date(2013, 8, 3)
    assert row.source == "https://example.org/history/a.jpg"
    assert row.licence == LICENCE


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("a.jpg,HAW-41,95,-155.8,2013-08-03,https://x/a.jpg,US Gov", "lat"),
        ("a.jpg,HAW-41,20.2,-190,2013-08-03,https://x/a.jpg,US Gov", "lon"),
        ("a.jpg,HAW-41,20.2,-155.8,03-AUG-13,https://x/a.jpg,US Gov", "date"),
        ("a.jpg,HAW-41,20.2,-155.8,2013-08-03,https://x/a.jpg,", "licence"),
        ("a.jpg,,20.2,-155.8,2013-08-03,https://x/a.jpg,US Gov", "site"),
    ],
)
def test_read_manifest_names_the_bad_row_and_field(tmp_path: Path, row: str, message: str) -> None:
    with pytest.raises(ValueError, match=rf"row 2: .*{message}"):
        ih.read_manifest(_manifest(tmp_path, [row]))


def test_read_manifest_rejects_a_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "manifest.csv"
    path.write_text("image_path,lat,lon,date\n", encoding="utf-8")

    with pytest.raises(ValueError, match="licence"):
        ih.read_manifest(path)


@pytest.mark.asyncio
async def test_import_groups_photos_into_done_historical_surveys(
    tmp_path: Path, store: Store
) -> None:
    rows = ih.read_manifest(
        _manifest(
            tmp_path,
            [
                # Each year's station fix differs by a few metres: one site.
                _row(_photo(tmp_path, "13_1.jpg"), 20.26828, -155.8604, "2013-08-03"),
                _row(_photo(tmp_path, "13_2.jpg", "02.jpg"), 20.26828, -155.8604, "2013-08-03"),
                _row(_photo(tmp_path, "16_1.jpg"), 20.26824, -155.86038, "2016-08-15"),
                _row(_photo(tmp_path, "19_1.jpg"), 20.268215, -155.860413, "2019-07-15"),
            ],
        )
    )

    surveys = await ih.import_history(store, rows, segmenter=FakeSegmenter())

    sites = await store.sites.list()
    assert [site.name for site in sites] == ["HAW-41"]
    stored = await store.surveys.by_site(sites[0].id)
    assert [s.id for s in stored] == [s.id for s in surveys]
    assert [s.dive_date for s in stored] == [date(2013, 8, 3), date(2016, 8, 15), date(2019, 7, 15)]
    for survey in stored:
        assert survey.source == "historical"
        assert survey.status == SurveyStatus.DONE
        assert survey.video_path is None
        assert survey.cover is not None
        assert sum(survey.cover.values()) == pytest.approx(1.0)  # pyright: ignore[reportUnknownMemberType]

    frames = await store.frames.list_by_survey(stored[0].id)
    assert [frame.t_sec for frame in frames] == [0.0, 1.0]
    for frame in frames:
        seg = await store.segmentations.get_by_frame(frame.id)
        assert seg.backend == "fake"
        assert store.blobs.resolve(frame.image_path).is_file()

    # Segmented only: no assessment, no agent tool call.
    events = await store.events.list(stored[0].id)
    assert {event.type for event in events} == {"segmented"}


@pytest.mark.asyncio
async def test_import_shrinks_large_photos(tmp_path: Path, store: Store) -> None:
    (tmp_path / "history").mkdir()
    Image.new("RGB", (4000, 3000), (40, 120, 160)).save(tmp_path / "history" / "big.jpg")
    rows = ih.read_manifest(
        _manifest(tmp_path, [_row("history/big.jpg", 20.26828, -155.8604, "2013-08-03")])
    )

    [survey] = await ih.import_history(store, rows, segmenter=FakeSegmenter())

    [frame] = await store.frames.list_by_survey(survey.id)
    with Image.open(store.blobs.resolve(frame.image_path)) as img:
        assert img.size == (1920, 1440)


@pytest.mark.asyncio
async def test_stations_farther_apart_than_500_m_get_their_own_sites(
    tmp_path: Path, store: Store
) -> None:
    image = _photo(tmp_path, "a.jpg")
    rows = ih.read_manifest(
        _manifest(
            tmp_path,
            [
                _row(image, 20.26828, -155.8604, "2013-08-03", site="HAW-41"),
                _row(image, 19.93087, -155.89211, "2013-08-08", site="HAW-49"),
            ],
        )
    )

    await ih.import_history(store, rows, segmenter=FakeSegmenter())

    assert sorted(site.name for site in await store.sites.list()) == ["HAW-41", "HAW-49"]


@pytest.mark.asyncio
async def test_a_photo_joins_an_existing_site_nearby(tmp_path: Path, store: Store) -> None:
    rows = ih.read_manifest(
        _manifest(tmp_path, [_row(_photo(tmp_path, "a.jpg"), 20.26828, -155.8604, "2013-08-03")])
    )
    await ih.import_history(store, rows, segmenter=FakeSegmenter())
    [site] = await store.sites.list()
    later = ih.read_manifest(
        _manifest(tmp_path, [_row(_photo(tmp_path, "b.jpg"), 20.2683, -155.8605, "2016-08-15")])
    )

    await ih.import_history(store, later, segmenter=FakeSegmenter())

    assert [s.id for s in await store.sites.list()] == [site.id]
    assert len(await store.surveys.by_site(site.id)) == 2


@pytest.mark.asyncio
async def test_rerunning_skips_dates_already_imported(tmp_path: Path, store: Store) -> None:
    rows = ih.read_manifest(
        _manifest(tmp_path, [_row(_photo(tmp_path, "a.jpg"), 20.26828, -155.8604, "2013-08-03")])
    )
    await ih.import_history(store, rows, segmenter=FakeSegmenter())

    again = await ih.import_history(store, rows, segmenter=FakeSegmenter())

    assert again == []
    assert len(await store.surveys.list()) == 1


@pytest.mark.asyncio
async def test_a_failed_segmentation_marks_the_survey_failed(tmp_path: Path, store: Store) -> None:
    class Broken(FakeSegmenter):
        def segment(self, image: np.ndarray) -> np.ndarray:
            raise RuntimeError("segmenter down")

    rows = ih.read_manifest(
        _manifest(tmp_path, [_row(_photo(tmp_path, "a.jpg"), 20.26828, -155.8604, "2013-08-03")])
    )

    with pytest.raises(RuntimeError, match="segmenter down"):
        await ih.import_history(store, rows, segmenter=Broken())

    [survey] = await store.surveys.list()
    assert survey.status == SurveyStatus.FAILED
    assert survey.failure_reason == "segmenter down"


def test_fetch_missing_downloads_only_absent_photos(tmp_path: Path) -> None:
    present = _photo(tmp_path, "here.jpg")
    jpeg = (FRAMES_DIR / "02.jpg").read_bytes()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=jpeg)

    rows = ih.read_manifest(
        _manifest(
            tmp_path,
            [
                _row(present, 20.26828, -155.8604, "2013-08-03"),
                _row("history/gone.jpg", 20.26828, -155.8604, "2013-08-03"),
            ],
        )
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetched = ih.fetch_missing(rows, client)

    assert fetched == 1
    assert requested == ["https://example.org/history/gone.jpg"]
    assert (tmp_path / "history" / "gone.jpg").read_bytes() == jpeg
    assert not list((tmp_path / "history").glob("*.part"))


def test_fetch_missing_refuses_a_non_https_source(tmp_path: Path) -> None:
    rows = ih.read_manifest(
        _manifest(tmp_path, ["history/gone.jpg,HAW-41,20.2,-155.8,2013-08-03,ftp://x/g.jpg,US Gov"])
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request {request.url}")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="https"),
    ):
        ih.fetch_missing(rows, client)


def test_the_demo_manifest_has_one_station_over_three_years() -> None:
    rows = ih.read_manifest(REPO_ROOT / "data" / "demo" / "history_manifest.csv")

    assert {row.site for row in rows} == {"HAW-41"}
    assert sorted({row.dive_date for row in rows}) == [
        date(2013, 8, 3),
        date(2016, 8, 15),
        date(2019, 7, 15),
    ]
    assert all(row.source.startswith("https://www.ncei.noaa.gov/") for row in rows)
    assert all("PIFSC ESD" in row.licence for row in rows)
