"""Pipeline stage definitions (architecture § 4.3, § 6.1)."""

from __future__ import annotations

import asyncio
import io
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from reefcase.core.config import Settings
from reefcase.core.events import FrameScored, FramesExtracted, Segmented
from reefcase.core.ids import FRAME, SEGMENTATION, new_id
from reefcase.core.schemas import MASK_INDEX, Frame, SegClass, Segmentation
from reefcase.ingest.frames import IngestError, extract_candidates
from reefcase.ingest.quality import QualityError, score
from reefcase.pipeline.bus import EventBus
from reefcase.vision.cover import cover_from_mask
from reefcase.vision.segmenter import Segmenter, build_segmenter

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = ["ingest_stage", "run_stages", "segment_stage"]

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


async def run_stages(store: Store, survey_id: str) -> None:
    """Run all pipeline stages in sequence."""
    settings = Settings()
    frames = await ingest_stage(store, survey_id, settings=settings)
    await segment_stage(store, survey_id, frames, settings=settings)
