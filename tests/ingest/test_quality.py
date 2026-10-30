"""Story 2.4 — Quality scoring and fail-fast (architecture § 4.2, § 6.1, FR2, FR3)."""

import inspect
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import reefcase.pipeline.stages as stages_module
from reefcase.core.config import Settings
from reefcase.core.errors import NotFoundError
from reefcase.core.events import FrameScored, FramesExtracted, SurveyFailed
from reefcase.core.schemas import (
    Frame,
    GeoPoint,
    QualityScore,
    Site,
    Survey,
    SurveyStatus,
)
from reefcase.ingest.frames import extract_candidates
from reefcase.ingest.quality import (
    BLUR_THRESHOLD,
    COLOR_CAST_THRESHOLD,
    TURBIDITY_THRESHOLD,
    QualityError,
    score,
)
from reefcase.pipeline.runner import JobRunner
from reefcase.pipeline.stages import ingest_stage
from reefcase.store.db import Store

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FRAME_01_PATH = FIXTURES_DIR / "frames" / "01.jpg"
CLIP_PATH = FIXTURES_DIR / "clip_10s.mp4"

IMAGE_HEIGHT, IMAGE_WIDTH = 120, 160


def _now() -> datetime:
    return datetime.now(UTC)


def _checkerboard(amplitude: float) -> np.ndarray:
    """A grey checkerboard whose 4-neighbour Laplacian is non-zero but flat overall."""
    base = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH), dtype=np.float64)
    base[::2, ::2] = amplitude
    base[1::2, 1::2] = amplitude
    gray = np.clip(127.0 + base, 0, 255).astype(np.uint8)
    return np.stack([gray, gray, gray], axis=-1)


def _soft_gradient() -> np.ndarray:
    """A smooth grey ramp: no high-frequency detail, so the Laplacian is ~zero."""
    ramp = np.tile(np.linspace(0, 255, IMAGE_WIDTH, dtype=np.float64), (IMAGE_HEIGHT, 1))
    gray = np.clip(ramp, 0, 255).astype(np.uint8)
    return np.stack([gray, gray, gray], axis=-1)


def _saturated_stripes() -> np.ndarray:
    """White and pure-blue stripes: sharp and contrasty, but heavily blue-cast."""
    image = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
    image[::2, :] = (255, 255, 255)
    image[1::2, :] = (0, 0, 255)
    return image


#: Reasons cycled by the scripted ``score`` in the plurality tests. "too blurry"
#: comes first (a naive ``rejected[0].reason`` would report it), "colour cast"
#: occurs twice per cycle (it must win as the plurality), and ``None`` is a pass.
_SCRIPTED_PATTERN: tuple[str | None, ...] = (
    "too blurry",
    "colour cast",
    "too murky",
    "colour cast",
    None,
)

_SCRIPTED_SCORES: dict[str | None, QualityScore] = {
    None: QualityScore(blur=600.0, color_cast=30.0, turbidity=0.7, passed=True, reason=None),
    "too blurry": QualityScore(
        blur=5.0, color_cast=30.0, turbidity=0.7, passed=False, reason="too blurry"
    ),
    "too murky": QualityScore(
        blur=600.0, color_cast=30.0, turbidity=0.99, passed=False, reason="too murky"
    ),
    "colour cast": QualityScore(
        blur=600.0, color_cast=95.0, turbidity=0.7, passed=False, reason="colour cast"
    ),
}


class _ScriptedScorer:
    """A deterministic stand-in for ``score`` that cycles ``_SCRIPTED_PATTERN``.

    ``reasons`` records one entry per call, so a test can assert on the exact
    sequence the stage actually saw rather than a hard-coded one.
    """

    def __init__(self) -> None:
        self.reasons: list[str | None] = []

    def __call__(self, _image: object) -> QualityScore:
        reason = _SCRIPTED_PATTERN[len(self.reasons) % len(_SCRIPTED_PATTERN)]
        self.reasons.append(reason)
        return _SCRIPTED_SCORES[reason]


def test_score_returns_quality_score_without_threshold_overrides() -> None:
    parameters = inspect.signature(score).parameters
    assert list(parameters) == ["image"]

    result = score(_soft_gradient())
    assert isinstance(result, QualityScore)


def test_score_sharp_real_frame_passes() -> None:
    image = np.array(Image.open(FRAME_01_PATH).convert("RGB"))
    result = score(image)
    assert result.passed is True
    assert result.reason is None
    assert result.blur >= BLUR_THRESHOLD
    assert result.turbidity <= TURBIDITY_THRESHOLD
    assert result.color_cast <= COLOR_CAST_THRESHOLD


def test_score_too_blurry() -> None:
    result = score(_soft_gradient())
    assert result.passed is False
    assert result.reason == "too blurry"
    assert result.blur < BLUR_THRESHOLD
    # The other metrics are fine, so blur is the only failure.
    assert result.turbidity <= TURBIDITY_THRESHOLD
    assert result.color_cast <= COLOR_CAST_THRESHOLD


def test_score_too_murky() -> None:
    result = score(_checkerboard(4.0))
    assert result.passed is False
    assert result.reason == "too murky"
    assert result.turbidity > TURBIDITY_THRESHOLD
    # Sharp enough and neutral, so turbidity is the only failure.
    assert result.blur >= BLUR_THRESHOLD
    assert result.color_cast <= COLOR_CAST_THRESHOLD


def test_score_colour_cast() -> None:
    result = score(_saturated_stripes())
    assert result.passed is False
    assert result.reason == "colour cast"
    assert result.color_cast > COLOR_CAST_THRESHOLD
    # Sharp and clear, so the cast is the only failure.
    assert result.blur >= BLUR_THRESHOLD
    assert result.turbidity <= TURBIDITY_THRESHOLD


def test_score_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="HxWx3"):
        score(np.zeros((10, 10), dtype=np.uint8))


async def _create_survey_with_video(store: Store, video_file: Path) -> Survey:
    site = Site(
        id="site_test_quality",
        name="Test Reef",
        location=GeoPoint(lat=-16.5, lon=145.5),
        created_at=_now(),
    )
    await store.sites.save(site)

    survey_id = "srv_test_quality_01"
    video_ref = store.blobs.save_video(survey_id, video_file.read_bytes())
    survey = Survey(
        id=survey_id,
        site_id=site.id,
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.QUEUED,
        source="upload",
        video_path=video_ref,
        created_at=_now(),
    )
    await store.surveys.save(survey)
    return survey


@pytest.mark.asyncio
async def test_frame_repo_round_trip(store: Store) -> None:
    quality = QualityScore(blur=150.0, color_cast=10.0, turbidity=0.5, passed=True, reason=None)
    frame = Frame(
        id="frm_repo_01",
        survey_id="srv_repo_01",
        t_sec=1.5,
        image_path="blobs/srv_repo_01/frames/frm_repo_01.jpg",
        quality=quality,
    )
    await store.frames.save(frame)

    loaded = await store.frames.get(frame.id)
    assert loaded == frame
    assert await store.frames.list_by_survey(frame.survey_id) == [frame]

    with pytest.raises(NotFoundError, match="unknown frame: frm_missing"):
        await store.frames.get("frm_missing")


@pytest.mark.asyncio
async def test_ingest_stage_saves_passing_frames_and_emits_events(
    store: Store, make_settings: Callable[..., Settings]
) -> None:
    settings = make_settings()
    survey = await _create_survey_with_video(store, CLIP_PATH)

    await ingest_stage(store, survey.id, settings=settings)

    frames = await store.frames.list_by_survey(survey.id)
    assert settings.min_frames <= len(frames) <= settings.keep_frames
    assert frames == sorted(frames, key=lambda frame: (frame.t_sec, frame.id))
    for frame in frames:
        assert frame.quality.passed is True
        assert frame.quality.reason is None
        disk_path = store.blobs.resolve(frame.image_path)
        assert disk_path.is_file()
        assert disk_path.stat().st_size > 0

    events = await store.events.list(survey.id)
    extracted_events = [event for event in events if isinstance(event, FramesExtracted)]
    assert len(extracted_events) == 1
    assert extracted_events[0].count >= len(frames)

    scored_events = [event for event in events if isinstance(event, FrameScored)]
    assert len(scored_events) == len(frames)
    thumbs = {event.frame_id: event.thumb_url for event in scored_events}
    for frame in frames:
        assert thumbs[frame.id] == f"/media/{survey.id}/thumbs/{frame.id}.jpg"


@pytest.mark.asyncio
async def test_ingest_stage_keeps_only_the_sharpest_keep_frames(
    store: Store, make_settings: Callable[..., Settings]
) -> None:
    keep_frames = 5
    settings = make_settings(keep_frames=keep_frames)
    survey = await _create_survey_with_video(store, CLIP_PATH)

    # Independent ground truth: decode and score the same candidates here, then
    # derive the expected survivors from the real blur values (no hard-coded list).
    candidates = list(extract_candidates(CLIP_PATH))
    passing = [
        (candidate.t_sec, quality)
        for candidate in candidates
        if (quality := score(candidate.image)).passed
    ]
    assert len(passing) > keep_frames, "the [: keep_frames] slice must actually bind"
    sharpest = sorted(passing, key=lambda item: item[1].blur, reverse=True)[:keep_frames]
    expected_t_secs = {t_sec for t_sec, _ in sharpest}

    await ingest_stage(store, survey.id, settings=settings)

    frames = await store.frames.list_by_survey(survey.id)
    assert len(frames) == keep_frames
    assert {frame.t_sec for frame in frames} == expected_t_secs
    assert frames == sorted(frames, key=lambda frame: (frame.t_sec, frame.id))
    assert all(frame.quality.passed for frame in frames)

    # Every dropped candidate is blurrier than every kept one: not "the blurriest".
    dropped = [(t_sec, quality) for t_sec, quality in passing if t_sec not in expected_t_secs]
    assert min(frame.quality.blur for frame in frames) >= max(q.blur for _, q in dropped)

    events = await store.events.list(survey.id)
    extracted_events = [event for event in events if isinstance(event, FramesExtracted)]
    assert len(extracted_events) == 1
    assert extracted_events[0].count == len(candidates)

    scored_events = [event for event in events if isinstance(event, FrameScored)]
    assert len(scored_events) == keep_frames
    assert {event.frame_id for event in scored_events} == {frame.id for frame in frames}


@pytest.mark.asyncio
async def test_ingest_stage_fails_fast_when_under_min_frames_direct(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    survey = await _create_survey_with_video(store, CLIP_PATH)

    # Every candidate is now below the blur floor, so every rejection says "too blurry".
    import reefcase.ingest.quality as quality_module

    monkeypatch.setattr(quality_module, "BLUR_THRESHOLD", 1_000_000.0)

    with pytest.raises(QualityError, match="too blurry"):
        await ingest_stage(store, survey.id, settings=settings)

    assert await store.frames.list_by_survey(survey.id) == []


@pytest.mark.asyncio
async def test_ingest_stage_fails_fast_via_job_runner(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    survey = await _create_survey_with_video(store, CLIP_PATH)

    # Every candidate is now above the cast ceiling, so every rejection says "colour cast".
    import reefcase.ingest.quality as quality_module

    monkeypatch.setattr(quality_module, "COLOR_CAST_THRESHOLD", 0.0)

    async def _run_ingest(job_store: Store, survey_id: str) -> None:
        await ingest_stage(job_store, survey_id, settings=settings)

    runner = JobRunner(store, _run_ingest)
    assert await runner.run_once() is True

    updated_survey = await store.surveys.get(survey.id)
    assert updated_survey.status is SurveyStatus.FAILED
    assert updated_survey.failure_reason == "colour cast"

    events = await store.events.list(survey.id)
    failed_events = [event for event in events if isinstance(event, SurveyFailed)]
    assert len(failed_events) == 1
    assert failed_events[0].reason == "colour cast"


@pytest.mark.asyncio
async def test_ingest_stage_reports_the_most_common_rejection_reason(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    survey = await _create_survey_with_video(store, CLIP_PATH)

    scripted = _ScriptedScorer()
    monkeypatch.setattr(stages_module, "score", scripted)

    with pytest.raises(QualityError, match="colour cast"):
        await ingest_stage(store, survey.id, settings=settings)

    rejections = [reason for reason in scripted.reasons if reason is not None]
    # The plurality is *not* the first-seen reason, so a naive rejected[0] fails.
    assert rejections[0] == "too blurry"
    counts = Counter(rejections)
    assert counts["colour cast"] > max(counts["too blurry"], counts["too murky"])
    assert counts.most_common(1)[0][0] == "colour cast"
    # Fewer passes than the floor, so the failure is "too few", not "all rejected".
    assert sum(1 for reason in scripted.reasons if reason is None) < settings.min_frames

    assert await store.frames.list_by_survey(survey.id) == []


@pytest.mark.asyncio
async def test_ingest_stage_plurality_reason_via_job_runner(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings()
    survey = await _create_survey_with_video(store, CLIP_PATH)

    scripted = _ScriptedScorer()
    monkeypatch.setattr(stages_module, "score", scripted)

    async def _run_ingest(job_store: Store, survey_id: str) -> None:
        await ingest_stage(job_store, survey_id, settings=settings)

    runner = JobRunner(store, _run_ingest)
    assert await runner.run_once() is True

    updated_survey = await store.surveys.get(survey.id)
    assert updated_survey.status is SurveyStatus.FAILED
    assert updated_survey.failure_reason == "colour cast"
    assert await store.frames.list_by_survey(survey.id) == []

    events = await store.events.list(survey.id)
    extracted_events = [event for event in events if isinstance(event, FramesExtracted)]
    assert len(extracted_events) == 1
    assert extracted_events[0].count == len(scripted.reasons)

    failed_events = [event for event in events if isinstance(event, SurveyFailed)]
    assert len(failed_events) == 1
    assert failed_events[0].reason == "colour cast"
