"""Story 3.5 — Segmentation stage (architecture § 4.3, § 5.1, § 6.1, § 6.4)."""

import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import reefcase.pipeline.stages as stages_module
from reefcase.core.config import Settings
from reefcase.core.errors import NotFoundError
from reefcase.core.events import Segmented
from reefcase.core.schemas import (
    Frame,
    GeoPoint,
    QualityScore,
    SegClass,
    Segmentation,
    Site,
    Survey,
    SurveyStatus,
)
from reefcase.pipeline.runner import JobRunner
from reefcase.pipeline.stages import segment_stage
from reefcase.store.db import Store
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.fake import FakeSegmenter

CLIP_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "clip_10s.mp4"
SURVEY_ID = "srv_test_segment_01"


def _now() -> datetime:
    return datetime.now(UTC)


async def _create_survey(store: Store, video_ref: str | None = None) -> Survey:
    site = Site(
        id="site_test_segment",
        name="Test Reef",
        location=GeoPoint(lat=-16.5, lon=145.5),
        created_at=_now(),
    )
    await store.sites.save(site)
    survey = Survey(
        id=SURVEY_ID,
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.QUEUED,
        source="upload",
        video_path=video_ref,
        created_at=_now(),
    )
    await store.surveys.save(survey)
    return survey


async def _save_frame(store: Store, frame_id: str, height: int, width: int, t_sec: float) -> Frame:
    image = np.full((height, width, 3), 90, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(image).save(buf, format="JPEG")
    frame = Frame(
        id=frame_id,
        survey_id=SURVEY_ID,
        t_sec=t_sec,
        image_path=store.blobs.save_frame(SURVEY_ID, frame_id, buf.getvalue()),
        quality=QualityScore(blur=150.0, color_cast=10.0, turbidity=0.5, passed=True),
    )
    await store.frames.save(frame)
    return frame


@pytest.mark.asyncio
async def test_segmentation_repo_round_trip(store: Store) -> None:
    segmentation = Segmentation(
        id="seg_repo_01",
        frame_id="frm_repo_01",
        backend="fake",
        mask_path="blobs/srv_repo_01/masks/frm_repo_01.png",
        cover={cls: 1 / 6 for cls in SegClass},
        latency_ms=12,
    )
    await store.segmentations.save(segmentation)

    assert await store.segmentations.get_by_frame("frm_repo_01") == segmentation
    with pytest.raises(NotFoundError, match="no segmentation for frame: frm_missing"):
        await store.segmentations.get_by_frame("frm_missing")


@pytest.mark.asyncio
async def test_segment_stage_stores_mask_row_and_event_per_frame(store: Store) -> None:
    await _create_survey(store)
    frames = [
        await _save_frame(store, "frm_seg_01", 64, 80, 0.5),
        await _save_frame(store, "frm_seg_02", 64, 80, 1.0),
    ]

    await segment_stage(store, SURVEY_ID, frames, segmenter=FakeSegmenter())

    events = [e for e in await store.events.list(SURVEY_ID) if isinstance(e, Segmented)]
    assert [e.frame_id for e in events] == [f.id for f in frames]

    expected_mask = FakeSegmenter().segment(np.zeros((64, 80, 3), dtype=np.uint8))
    for frame, event in zip(frames, events, strict=True):
        row = await store.segmentations.get_by_frame(frame.id)
        assert row.backend == "fake"
        assert row.latency_ms >= 0
        assert row.cover == cover_from_mask(expected_mask)
        assert row.mask_path == f"blobs/{SURVEY_ID}/masks/{frame.id}.png"

        # The PNG's pixel values are the class ids; its palette makes it viewable.
        with Image.open(store.blobs.resolve(row.mask_path)) as png:
            assert png.mode == "P"
            np.testing.assert_array_equal(np.asarray(png), expected_mask)

        assert event.backend == "fake"
        assert event.cover == row.cover
        assert event.mask_url == f"/media/{SURVEY_ID}/masks/{frame.id}.png"


@pytest.mark.asyncio
async def test_segment_stage_sets_pixel_weighted_survey_cover(store: Store) -> None:
    await _create_survey(store)
    small = await _save_frame(store, "frm_small", 8, 8, 0.5)
    large = await _save_frame(store, "frm_large", 40, 60, 1.0)

    cover = await segment_stage(store, SURVEY_ID, [small, large], segmenter=FakeSegmenter())

    fake = FakeSegmenter()
    small_cover = cover_from_mask(fake.segment(np.zeros((8, 8, 3), dtype=np.uint8)))
    large_cover = cover_from_mask(fake.segment(np.zeros((40, 60, 3), dtype=np.uint8)))
    expected = {cls: (small_cover[cls] * 64 + large_cover[cls] * 2400) / 2464 for cls in SegClass}
    survey = await store.surveys.get(SURVEY_ID)
    assert survey.cover is not None
    assert cover == survey.cover
    for cls in SegClass:
        assert survey.cover[cls] == pytest.approx(expected[cls])
    assert sum(survey.cover.values()) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_run_stages_segments_kept_frames_and_cover_survives_the_runner(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()  # segmenter="fake", no env, no .env
    monkeypatch.setattr(stages_module, "Settings", lambda: settings)
    await _create_survey(store, store.blobs.save_video(SURVEY_ID, CLIP_PATH.read_bytes()))

    runner = JobRunner(store, stages_module.run_stages)
    assert await runner.run_once() is True

    survey = await store.surveys.get(SURVEY_ID)
    assert survey.status is SurveyStatus.DONE, survey.failure_reason
    assert survey.cover is not None
    frames = await store.frames.list_by_survey(SURVEY_ID)
    assert frames
    for frame in frames:
        assert (await store.segmentations.get_by_frame(frame.id)).frame_id == frame.id
