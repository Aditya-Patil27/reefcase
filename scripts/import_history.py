"""Import past survey photos as historical surveys (Story 8.1, architecture §9.5, FR14).

Reads a manifest CSV with the columns ``image_path, site, lat, lon, date, source, licence``.
``image_path`` is relative to the manifest; ``source`` is where the photo was downloaded from,
and any missing photo is fetched from it first. Photos are grouped by site (a station within
500 m of an existing site joins it, FR12) and date. Each group becomes one ``historical``
survey: every photo is saved as a frame, segmented by the configured segmenter, and the survey
ends ``done`` with its cover. No assessment or agent run.

A site that already has a ``done`` historical survey on that date is skipped, so re-running is
safe.

Usage:
    uv run python scripts/import_history.py                         # the demo manifest
    uv run python scripts/import_history.py path/to/manifest.csv
    uv run python scripts/import_history.py --no-download           # local photos only

The demo manifest is NOAA PIFSC ESD NCRMP station HAW-41 (North Kohala, Hawaii) in 2013, 2016
and 2019; cite PIFSC ESD (see data/LICENSES.md). The photos land in the gitignored
``data/demo/history/``.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from reefcase.core.config import Settings
from reefcase.core.ids import FRAME, SITE, SURVEY, new_id
from reefcase.core.schemas import Frame, GeoPoint, Site, Survey, SurveyStatus
from reefcase.ingest.quality import score
from reefcase.pipeline.stages import segment_stage
from reefcase.store.db import Store
from reefcase.vision.segmenter import Segmenter, build_segmenter

logger = logging.getLogger("import_history")

DEFAULT_MANIFEST = Path(__file__).parents[1] / "data" / "demo" / "history_manifest.csv"
COLUMNS = ("image_path", "site", "lat", "lon", "date", "source", "licence")
# NCRMP photos are 4000x3000; frames from an upload are video-sized.
MAX_SIDE = 1920
DOWNLOAD_TIMEOUT_S = 180.0


@dataclass(frozen=True, slots=True)
class ManifestRow:
    image_path: Path
    site: str
    lat: float
    lon: float
    dive_date: date
    source: str
    licence: str


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_row(raw: dict[str, str], base: Path, line: int) -> ManifestRow:
    def bad(field: str, why: str) -> ValueError:
        return ValueError(f"row {line}: {field} {why}, got {raw.get(field)!r}")

    values = {key: (raw.get(key) or "").strip() for key in COLUMNS}
    for field in ("image_path", "site", "source", "licence"):
        if not values[field]:
            raise bad(field, "must not be empty")
    try:
        lat, lon = float(values["lat"]), float(values["lon"])
    except ValueError:
        raise bad("lat", "and lon must be numbers") from None
    if not -90.0 <= lat <= 90.0:
        raise bad("lat", "must be between -90 and 90")
    if not -180.0 <= lon <= 180.0:
        raise bad("lon", "must be between -180 and 180")
    try:
        dive_date = date.fromisoformat(values["date"])
    except ValueError:
        raise bad("date", "must be YYYY-MM-DD") from None
    return ManifestRow(
        image_path=base / values["image_path"],
        site=values["site"],
        lat=lat,
        lon=lon,
        dive_date=dive_date,
        source=values["source"],
        licence=values["licence"],
    )


def read_manifest(path: Path) -> list[ManifestRow]:
    """Parse and validate the manifest; errors name the CSV row (the header is row 1)."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(missing)}")
        return [_parse_row(raw, path.parent, line) for line, raw in enumerate(reader, start=2)]


def fetch_missing(rows: Sequence[ManifestRow], client: httpx.Client) -> int:
    """Download every photo that is not on disk yet from its https ``source``; return the count."""
    fetched = 0
    for row in rows:
        if row.image_path.is_file():
            continue
        if not row.source.startswith("https://"):
            raise ValueError(
                f"{row.image_path} is missing and its source is not https: {row.source}"
            )
        row.image_path.parent.mkdir(parents=True, exist_ok=True)
        part = row.image_path.with_name(row.image_path.name + ".part")
        with client.stream("GET", row.source) as response:
            response.raise_for_status()
            with part.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        part.replace(row.image_path)
        fetched += 1
        logger.info("downloaded %s", row.image_path.name)
    return fetched


def _frame_jpeg(path: Path) -> tuple[bytes, np.ndarray]:
    """Load a photo, shrink it to ``MAX_SIDE``, return its JPEG bytes and RGB pixels."""
    with Image.open(path) as img:
        rgb = img.convert("RGB")
    rgb.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=90)
    return buf.getvalue(), np.asarray(rgb)


async def _site_for(store: Store, row: ManifestRow) -> Site:
    location = GeoPoint(lat=row.lat, lon=row.lon)
    site = await store.sites.find_site_near(location)
    if site is None:
        site = Site(id=new_id(SITE), name=row.site, location=location, created_at=_now())
        await store.sites.save(site)
    return site


async def _import_survey(
    store: Store, site: Site, dive_date: date, rows: list[ManifestRow], segmenter: Segmenter
) -> Survey:
    survey = Survey(
        id=new_id(SURVEY),
        site_id=site.id,
        dive_date=dive_date,
        status=SurveyStatus.RUNNING,
        source="historical",
        created_at=_now(),
    )
    await store.surveys.save(survey)
    try:
        frames: list[Frame] = []
        for index, row in enumerate(rows):
            jpeg, pixels = await asyncio.to_thread(_frame_jpeg, row.image_path)
            frame_id = new_id(FRAME)
            frame = Frame(
                id=frame_id,
                survey_id=survey.id,
                t_sec=float(index),
                image_path=store.blobs.save_frame(survey.id, frame_id, jpeg),
                # Recorded, never used to drop a photo: these are curated survey photos.
                quality=score(pixels),
            )
            await store.frames.save(frame)
            frames.append(frame)
        await segment_stage(store, survey.id, frames, segmenter=segmenter)
    except Exception as exc:
        failed = await store.surveys.get(survey.id)
        await store.surveys.save(
            failed.model_copy(
                update={
                    "status": SurveyStatus.FAILED,
                    "failure_reason": str(exc) or type(exc).__name__,
                }
            )
        )
        raise
    done = await store.surveys.get(survey.id)  # segment_stage set the cover
    done = done.model_copy(update={"status": SurveyStatus.DONE})
    await store.surveys.save(done)
    return done


async def import_history(
    store: Store, rows: Sequence[ManifestRow], *, segmenter: Segmenter
) -> list[Survey]:
    """Create one ``done`` historical survey per (site, date); return the new ones."""
    groups: dict[tuple[str, date], tuple[Site, list[ManifestRow]]] = {}
    for row in rows:
        site = await _site_for(store, row)
        groups.setdefault((site.id, row.dive_date), (site, []))[1].append(row)

    imported: list[Survey] = []
    for (site_id, dive_date), (site, group) in sorted(groups.items(), key=lambda item: item[0]):
        existing = await store.surveys.by_site(site_id)
        if any(
            s.source == "historical" and s.dive_date == dive_date and s.status == SurveyStatus.DONE
            for s in existing
        ):
            logger.info("skipping %s %s: already imported", site.name, dive_date)
            continue
        survey = await _import_survey(store, site, dive_date, group, segmenter)
        logger.info("imported %s %s: %d photos as %s", site.name, dive_date, len(group), survey.id)
        imported.append(survey)
    return imported


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--no-download", action="store_true", help="fail on a missing photo instead of fetching it"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one "downloaded" line per photo is enough

    rows = read_manifest(args.manifest)
    if args.no_download:
        missing = [str(row.image_path) for row in rows if not row.image_path.is_file()]
        if missing:
            print(f"missing photos: {', '.join(missing)}", file=sys.stderr)
            return 1
    else:
        with httpx.Client(timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True) as client:
            fetch_missing(rows, client)

    settings = Settings()
    segmenter = build_segmenter(settings)
    logger.info("segmenter: %s, data dir: %s", segmenter.name, settings.data_dir)
    with Store.open(settings.data_dir) as store:
        imported = asyncio.run(import_history(store, rows, segmenter=segmenter))
    logger.info("%d new historical surveys", len(imported))
    return 0


if __name__ == "__main__":
    sys.exit(main())
