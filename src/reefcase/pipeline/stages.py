"""Pipeline stage definitions (architecture § 4.3, § 6.1)."""

from __future__ import annotations

import asyncio
import io
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PIL import Image

from reefcase.core.config import Settings
from reefcase.core.events import FrameScored, FramesExtracted
from reefcase.core.ids import FRAME, new_id
from reefcase.core.schemas import Frame
from reefcase.ingest.frames import IngestError, extract_candidates
from reefcase.ingest.quality import QualityError, score
from reefcase.pipeline.bus import EventBus

if TYPE_CHECKING:
    from reefcase.store.db import Store

__all__ = ["ingest_stage", "run_stages"]


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


async def run_stages(store: Store, survey_id: str) -> None:
    """Run all pipeline stages in sequence."""
    await ingest_stage(store, survey_id)
