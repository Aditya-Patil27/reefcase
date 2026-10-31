"""Story 5.5 — Teacher/student disagreement (architecture §5.6, FR11)."""

import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx
import numpy as np
import pytest
from PIL import Image

import reefcase.pipeline.stages as stages_module
from reefcase.agent.disagreement import IOU_THRESHOLD, coral_iou, disagrees, iou_per_class
from reefcase.core.config import Settings
from reefcase.core.events import Disagreement, Segmented
from reefcase.core.schemas import (
    MASK_INDEX,
    Cause,
    EvidenceRef,
    Finding,
    Frame,
    GeoPoint,
    Hypothesis,
    Investigation,
    QualityScore,
    SegBackend,
    SegClass,
    Site,
    Survey,
    SurveyStatus,
)
from reefcase.pipeline.stages import investigate_stage, segment_stage
from reefcase.store.db import Store
from reefcase.vision.modal_client import ModalSegmenter
from reefcase.vision.segmenter import build_checker

SURVEY_ID = "srv_test_disagree_01"
LIVE = MASK_INDEX[SegClass.LIVE_CORAL]
BLEACHED = MASK_INDEX[SegClass.BLEACHED_CORAL]
SAND = MASK_INDEX[SegClass.SAND]


class _FixedSegmenter:
    """Returns the same class for every pixel, under a chosen backend name."""

    def __init__(self, name: SegBackend, class_id: int) -> None:
        self.name: SegBackend = name
        self._class_id = class_id

    def segment(self, image: np.ndarray) -> np.ndarray:
        return np.full(image.shape[:2], self._class_id, dtype=np.uint8)


def _now() -> datetime:
    return datetime.now(UTC)


async def _create_survey(store: Store) -> None:
    site = Site(
        id="site_test_disagree",
        name="Test Reef",
        location=GeoPoint(lat=20.27, lon=-155.86),
        created_at=_now(),
    )
    await store.sites.save(site)
    await store.surveys.save(
        Survey(
            id=SURVEY_ID,
            site_id=site.id,
            dive_date=date(2024, 7, 6),
            status=SurveyStatus.QUEUED,
            source="upload",
            created_at=_now(),
        )
    )


async def _save_frame(store: Store, frame_id: str) -> Frame:
    buf = io.BytesIO()
    Image.fromarray(np.full((16, 20, 3), 90, dtype=np.uint8)).save(buf, format="JPEG")
    frame = Frame(
        id=frame_id,
        survey_id=SURVEY_ID,
        t_sec=0.5,
        image_path=store.blobs.save_frame(SURVEY_ID, frame_id, buf.getvalue()),
        quality=QualityScore(blur=150.0, color_cast=10.0, turbidity=0.5, passed=True),
    )
    await store.frames.save(frame)
    return frame


# ---------- iou_per_class and the threshold ----------


def test_iou_per_class_scores_each_class_present_in_either_mask() -> None:
    a = np.array([[LIVE, LIVE], [BLEACHED, SAND]], dtype=np.uint8)
    b = np.array([[LIVE, BLEACHED], [BLEACHED, SAND]], dtype=np.uint8)

    assert iou_per_class(a, b) == {
        SegClass.LIVE_CORAL: 0.5,
        SegClass.BLEACHED_CORAL: 0.5,
        SegClass.SAND: 1.0,
    }


def test_iou_per_class_rejects_masks_of_different_shapes() -> None:
    with pytest.raises(ValueError, match="shape"):
        iou_per_class(np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 3), dtype=np.uint8))


def test_coral_iou_averages_live_and_bleached_present_in_either_mask() -> None:
    a = np.array([[LIVE, LIVE], [BLEACHED, SAND]], dtype=np.uint8)
    b = np.array([[LIVE, SAND], [SAND, SAND]], dtype=np.uint8)

    # live 1/2, bleached 0/1; sand doesn't count.
    assert coral_iou(a, b) == pytest.approx(0.25)


def test_coral_iou_is_full_agreement_when_neither_mask_has_coral() -> None:
    sand = np.full((2, 2), SAND, dtype=np.uint8)

    assert coral_iou(sand, sand) == 1.0


def test_disagrees_below_the_half_iou_threshold_only() -> None:
    assert IOU_THRESHOLD == 0.5
    assert disagrees(0.49)
    assert not disagrees(0.5)


# ---------- segment stage, dual mode ----------


@pytest.mark.asyncio
async def test_segment_stage_uses_sam3_and_emits_disagreement_when_masks_disagree(
    store: Store,
) -> None:
    await _create_survey(store)
    frame = await _save_frame(store, "frm_disagree_01")
    student = _FixedSegmenter("student", LIVE)
    sam3 = _FixedSegmenter("sam3", BLEACHED)

    cover = await segment_stage(store, SURVEY_ID, [frame], segmenter=student, checker=sam3)

    row = await store.segmentations.get_by_frame(frame.id)
    assert row.backend == "sam3"
    assert row.cover[SegClass.BLEACHED_CORAL] == 1.0
    assert cover is not None and cover[SegClass.BLEACHED_CORAL] == 1.0
    with Image.open(store.blobs.resolve(row.mask_path)) as png:
        assert np.all(np.asarray(png) == BLEACHED)

    events = await store.events.list(SURVEY_ID)
    disagreements = [e for e in events if isinstance(e, Disagreement)]
    assert [(e.frame_id, e.iou, e.chosen) for e in disagreements] == [(frame.id, 0.0, "sam3")]
    segmented = [e for e in events if isinstance(e, Segmented)]
    assert [e.backend for e in segmented] == ["sam3"]


@pytest.mark.asyncio
async def test_segment_stage_keeps_the_student_mask_when_masks_agree(store: Store) -> None:
    await _create_survey(store)
    frame = await _save_frame(store, "frm_agree_01")

    await segment_stage(
        store,
        SURVEY_ID,
        [frame],
        segmenter=_FixedSegmenter("student", LIVE),
        checker=_FixedSegmenter("sam3", LIVE),
    )

    assert (await store.segmentations.get_by_frame(frame.id)).backend == "student"
    events = await store.events.list(SURVEY_ID)
    assert not [e for e in events if isinstance(e, Disagreement)]


# ---------- uncertain_frames ----------


def _investigation(uncertain_frames: list[str]) -> Investigation:
    evidence = EvidenceRef(kind="frame", id="frm_disagree_01")
    return Investigation(
        id="inv_disagree_01",
        survey_id=SURVEY_ID,
        findings=[Finding(statement="Live coral is pale.", evidence=[evidence])],
        hypotheses=[
            Hypothesis(
                cause=Cause.HEAT_STRESS,
                confidence=0.6,
                supporting=[evidence],
                rationale="Pale colonies.",
            )
        ],
        verdict="Heat stress.",
        actions=["Resurvey."],
        uncertain_frames=uncertain_frames,
        model="muse-spark-open",
    )


@pytest.mark.asyncio
async def test_investigate_stage_adds_disagreement_frames_to_uncertain_frames(
    store: Store,
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_survey(store)
    for frame_id in ("frm_disagree_01", "frm_disagree_02"):
        await store.events.append(
            Disagreement(
                survey_id=SURVEY_ID,
                seq=await store.events.next_seq(SURVEY_ID),
                ts=_now(),
                frame_id=frame_id,
                iou=0.1,
                chosen="sam3",
            )
        )

    async def fake_investigate(*_args: Any, **_kwargs: Any) -> Investigation:
        return _investigation(["frm_agent_says", "frm_disagree_02"])

    monkeypatch.setattr(stages_module, "investigate", fake_investigate)
    async with httpx.AsyncClient() as client:
        result = await investigate_stage(
            store,
            SURVEY_ID,
            frames=[],
            segs=[],
            assessments=[],
            settings=make_settings(),
            model=object(),  # pyright: ignore[reportArgumentType]
            http_client=client,
        )

    expected = ["frm_agent_says", "frm_disagree_02", "frm_disagree_01"]
    assert result.uncertain_frames == expected
    assert (await store.investigations.get_by_survey(SURVEY_ID)).uncertain_frames == expected


# ---------- build_checker: opt-in, student only, SAM 3 available ----------


def test_build_checker_is_none_unless_the_check_is_switched_on(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(
        segmenter="student", sam_modal_url="https://sam.test", sam_modal_token="tok"
    )

    assert build_checker(settings) is None


def test_build_checker_returns_sam3_on_modal_for_the_student(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(
        segmenter="student",
        sam_modal_url="https://sam.test",
        sam_modal_token="tok",
        disagreement_check=True,
    )

    checker = build_checker(settings)

    assert isinstance(checker, ModalSegmenter)
    assert checker.name == "sam3"


@pytest.mark.parametrize(
    "overrides",
    [
        {"segmenter": "sam3_modal", "sam_modal_url": "https://sam.test", "sam_modal_token": "t"},
        {"segmenter": "student"},
    ],
    ids=["segmenter-is-already-sam3", "sam3-not-configured"],
)
def test_build_checker_is_none_without_a_student_and_sam3(
    make_settings: Callable[..., Settings], overrides: dict[str, Any]
) -> None:
    assert build_checker(make_settings(disagreement_check=True, **overrides)) is None
