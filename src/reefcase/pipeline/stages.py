"""Pipeline stage definitions (architecture § 4.3, § 6.1)."""

from __future__ import annotations

import asyncio
import io
import logging
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import numpy as np
from PIL import Image
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior
from pydantic_ai.models import Model

from reefcase.agent.investigator import investigate
from reefcase.core.config import Settings
from reefcase.core.errors import ConfigError
from reefcase.core.events import (
    Assessed,
    FindingEvent,
    FrameScored,
    FramesExtracted,
    ReportReady,
    Segmented,
)
from reefcase.core.ids import FRAME, SEGMENTATION, new_id
from reefcase.core.schemas import (
    MASK_INDEX,
    Frame,
    FrameAssessment,
    Investigation,
    SegClass,
    Segmentation,
)
from reefcase.ingest.frames import IngestError, extract_candidates
from reefcase.ingest.quality import QualityError, score
from reefcase.llm.assess import assess_frame
from reefcase.llm.providers import build_model
from reefcase.pipeline.bus import EventBus
from reefcase.tools.http import ToolContext, build_client
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.segmenter import Segmenter, build_segmenter

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = [
    "ASSESS_CONCURRENCY",
    "assess_stage",
    "ingest_stage",
    "investigate_stage",
    "run_stages",
    "segment_stage",
]

logger = logging.getLogger(__name__)

#: Frames assessed at once (Story 5.1); bounds load on the LLM endpoint.
ASSESS_CONCURRENCY = 4

# Mask PNG palette: the reef colours from docs/agents/ui.md, by §4.2 class id, so
# the web can overlay the mask as-is while its pixel values stay class ids.
_MASK_COLOURS: dict[SegClass, tuple[int, int, int]] = {
    SegClass.OTHER: (68, 79, 87),
    SegClass.LIVE_CORAL: (75, 195, 159),
    SegClass.BLEACHED_CORAL: (236, 232, 217),
    SegClass.ALGAE: (141, 129, 61),
    SegClass.RUBBLE: (125, 110, 99),
    SegClass.SAND: (182, 169, 143),
}
_MASK_PALETTE = [
    channel
    for _, colour in sorted((MASK_INDEX[cls], colour) for cls, colour in _MASK_COLOURS.items())
    for channel in colour
]


def _now() -> datetime:
    return datetime.now(UTC)


async def ingest_stage(
    store: Store,
    survey_id: str,
    *,
    bus: EventBus | None = None,
    settings: Settings | None = None,
) -> list[Frame]:
    """Sample candidate frames, score quality, save passing frames as JPEG blobs.

    Emits ``frames_extracted`` once candidates are sampled, and ``frame_scored``
    for each saved frame.

    Raises:
        IngestError: If the survey has no video or video decode fails.
        QualityError: If fewer than ``min_frames`` pass quality checks, with
            the most common rejection reason ("too blurry", "too murky", "colour cast").
    """
    cfg = settings or Settings()
    event_bus = bus or EventBus(store)

    survey = await store.surveys.get(survey_id)
    if not survey.video_path:
        raise IngestError(f"unreadable video: survey {survey_id} has no video")

    video_file = store.blobs.resolve(survey.video_path)
    if not video_file.is_file():
        raise IngestError(f"unreadable video: file not found {video_file}")

    # Decode video frames in background thread
    candidates = await asyncio.to_thread(
        lambda: list(extract_candidates(video_file, every_sec=0.5))
    )

    await event_bus.publish(
        FramesExtracted(
            survey_id=survey_id,
            seq=await store.events.next_seq(survey_id),
            ts=_now(),
            count=len(candidates),
        )
    )

    scored = [(cand, score(cand.image)) for cand in candidates]
    passing = [(cand, q) for cand, q in scored if q.passed]
    rejected = [(cand, q) for cand, q in scored if not q.passed]

    if len(passing) < cfg.min_frames:
        counts = Counter(q.reason for _, q in rejected if q.reason is not None)
        reason = counts.most_common(1)[0][0] if counts else "too blurry"
        raise QualityError(reason)

    # Sharpest first, then keep the top ``keep_frames``, then chronological order
    top_passing = sorted(passing, key=lambda item: item[1].blur, reverse=True)[: cfg.keep_frames]
    kept = sorted(top_passing, key=lambda item: item[0].t_sec)

    saved_frames: list[Frame] = []
    for cand, q in kept:
        frame_id = new_id(FRAME)

        # Encode frame as JPEG
        buf = io.BytesIO()
        Image.fromarray(cand.image).save(buf, format="JPEG", quality=90)
        jpeg_bytes = buf.getvalue()

        image_ref = store.blobs.save_frame(survey_id, frame_id, jpeg_bytes)
        frame = Frame(
            id=frame_id,
            survey_id=survey_id,
            t_sec=cand.t_sec,
            image_path=image_ref,
            quality=q,
        )
        await store.frames.save(frame)
        saved_frames.append(frame)

        thumb_url = f"/media/{survey_id}/frames/{frame_id}.jpg"
        await event_bus.publish(
            FrameScored(
                survey_id=survey_id,
                seq=await store.events.next_seq(survey_id),
                ts=_now(),
                frame_id=frame_id,
                quality=q,
                thumb_url=thumb_url,
            )
        )

    return saved_frames


def _encode_mask(mask: np.ndarray) -> bytes:
    png = Image.fromarray(mask, mode="P")
    png.putpalette(_MASK_PALETTE)
    buf = io.BytesIO()
    png.save(buf, format="PNG")
    return buf.getvalue()


def _segment_frame(
    segmenter: Segmenter, image_file: Path
) -> tuple[np.ndarray, dict[SegClass, float], int]:
    """Decode, segment and score one frame; the blocking part of the stage."""
    with Image.open(image_file) as img:
        image = np.asarray(img.convert("RGB"))
    started = time.perf_counter()
    mask = segmenter.segment(image)
    latency_ms = round((time.perf_counter() - started) * 1000)
    return mask, cover_from_mask(mask), latency_ms


async def segment_stage(
    store: Store,
    survey_id: str,
    frames: list[Frame],
    *,
    bus: EventBus | None = None,
    settings: Settings | None = None,
    segmenter: Segmenter | None = None,
) -> dict[SegClass, float] | None:
    """Segment each kept frame, store its mask PNG and row, set the survey cover.

    Emits ``segmented`` per frame. The survey cover is the pixel-weighted mean
    of the frame covers; it is returned, or ``None`` when there are no frames.
    """
    event_bus = bus or EventBus(store)
    seg = segmenter or build_segmenter(settings or Settings())

    weighted = dict.fromkeys(SegClass, 0.0)
    total_pixels = 0
    for frame in frames:
        mask, cover, latency_ms = await asyncio.to_thread(
            _segment_frame, seg, store.blobs.resolve(frame.image_path)
        )
        mask_ref = store.blobs.save_mask(survey_id, frame.id, _encode_mask(mask))
        segmentation = Segmentation(
            id=new_id(SEGMENTATION),
            frame_id=frame.id,
            backend=seg.name,
            mask_path=mask_ref,
            cover=cover,
            latency_ms=latency_ms,
        )
        await store.segmentations.save(segmentation)
        await event_bus.publish(
            Segmented(
                survey_id=survey_id,
                seq=await store.events.next_seq(survey_id),
                ts=_now(),
                frame_id=frame.id,
                backend=seg.name,
                cover=cover,
                mask_url=f"/media/{survey_id}/masks/{frame.id}.png",
            )
        )
        for cls, fraction in cover.items():
            weighted[cls] += fraction * mask.size
        total_pixels += mask.size

    if total_pixels == 0:
        return None
    survey_cover = {cls: value / total_pixels for cls, value in weighted.items()}
    survey = await store.surveys.get(survey_id)
    await store.surveys.save(survey.model_copy(update={"cover": survey_cover}))
    return survey_cover


async def assess_stage(
    store: Store,
    survey_id: str,
    frames: list[Frame],
    *,
    bus: EventBus | None = None,
    settings: Settings | None = None,
    model: Model | None = None,
) -> list[FrameAssessment]:
    """Assess each segmented frame with the teacher model, ``ASSESS_CONCURRENCY`` at a time.

    Stores each ``FrameAssessment`` and emits ``assessed``. A frame whose model
    output is invalid twice is skipped with a warning; the rest carry on. Returns
    the assessments in frame order.
    """
    event_bus = bus or EventBus(store)
    llm = model or build_model("teacher", settings or Settings())
    if llm is None:  # build_model only returns None for "student"
        raise ConfigError("REEFCASE_LLM_TEACHER_* is not configured")

    limit = asyncio.Semaphore(ASSESS_CONCURRENCY)
    # next_seq + publish is not atomic, so results are stored one at a time.
    publish_lock = asyncio.Lock()

    async def assess_one(frame: Frame) -> FrameAssessment | None:
        seg = await store.segmentations.get_by_frame(frame.id)
        image_bytes = store.blobs.read(frame.image_path)
        async with limit:
            try:
                assessment = await assess_frame(llm, frame, image_bytes, seg)
            except UnexpectedModelBehavior as exc:
                logger.warning("skipping frame %s: invalid assessment output (%s)", frame.id, exc)
                return None
            except ModelAPIError as exc:  # HTTP error, timeout, refused connection
                logger.warning("skipping frame %s: model API error (%s)", frame.id, exc)
                return None
        async with publish_lock:
            await store.assessments.save(assessment)
            await event_bus.publish(
                Assessed(
                    survey_id=survey_id,
                    seq=await store.events.next_seq(survey_id),
                    ts=_now(),
                    assessment=assessment,
                )
            )
        return assessment

    results = await asyncio.gather(*(assess_one(frame) for frame in frames))
    return [assessment for assessment in results if assessment is not None]


async def investigate_stage(
    store: Store,
    survey_id: str,
    *,
    frames: list[Frame] | None = None,
    segs: list[Segmentation] | None = None,
    assessments: list[FrameAssessment] | None = None,
    bus: EventBus | None = None,
    settings: Settings | None = None,
    model: Model | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> Investigation:
    """Investigate the survey: runs the agent over frames, segs, assessments.

    Persists the resulting ``Investigation``, emits ``finding`` for each finding,
    and emits ``report_ready``.
    """
    event_bus = bus or EventBus(store)
    cfg = settings or Settings()
    llm = model or build_model("agent", cfg)
    if llm is None:
        raise ConfigError("REEFCASE_LLM_AGENT_* is not configured")

    survey = await store.surveys.get(survey_id)
    if frames is None:
        frames = await store.frames.list_by_survey(survey_id)
    if segs is None:
        segs = await store.segmentations.list_by_survey(survey_id)
    if assessments is None:
        assessments = await store.assessments.list_by_survey(survey_id)

    client = http_client or build_client()
    close_client = http_client is None
    try:
        ctx = ToolContext(http=client, store=store, settings=cfg)
        investigation = await investigate(
            survey,
            frames,
            segs,
            assessments,
            ctx,
            event_bus.publish,
            model=llm,
        )
    finally:
        if close_client:
            await client.aclose()

    await store.investigations.save(investigation)

    for finding in investigation.findings:
        await event_bus.publish(
            FindingEvent(
                survey_id=survey_id,
                seq=await store.events.next_seq(survey_id),
                ts=_now(),
                finding=finding,
            )
        )

    await event_bus.publish(
        ReportReady(
            survey_id=survey_id,
            seq=await store.events.next_seq(survey_id),
            ts=_now(),
            investigation_id=investigation.id,
        )
    )

    return investigation


async def run_stages(
    store: Store,
    survey_id: str,
    *,
    settings: Settings | None = None,
    teacher_model: Model | None = None,
    agent_model: Model | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    """Run all pipeline stages in sequence."""
    cfg = settings or Settings()
    frames = await ingest_stage(store, survey_id, settings=cfg)
    await segment_stage(store, survey_id, frames, settings=cfg)
    if teacher_model is None and cfg.llm_role("teacher") is None:
        logger.warning("REEFCASE_LLM_TEACHER_* is not configured; skipping frame assessment")
        assessments: list[FrameAssessment] = []
    else:
        assessments = await assess_stage(
            store, survey_id, frames, settings=cfg, model=teacher_model
        )

    if agent_model is None and cfg.llm_role("agent") is None:
        logger.warning("REEFCASE_LLM_AGENT_* is not configured; skipping investigation")
    else:
        await investigate_stage(
            store,
            survey_id,
            frames=frames,
            assessments=assessments,
            settings=cfg,
            model=agent_model,
            http_client=http_client,
        )
