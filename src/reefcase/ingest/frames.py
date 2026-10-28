# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalMemberAccess=false
"""Candidate frame sampling from video clips (Story 2.3; architecture Section 4.2, Section 6.4)."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple, cast

import av
import av.error
import numpy as np

from reefcase.core.errors import ReefCaseError

__all__ = ["CandidateFrame", "IngestError", "extract_candidates"]


class IngestError(ReefCaseError):
    """Raised when video ingest fails or video is unreadable."""


class CandidateFrame(NamedTuple):
    """A sampled video frame decoded as RGB uint8 with its timestamp."""

    image: np.ndarray[Any, np.dtype[np.uint8]]
    t_sec: float


def extract_candidates(path: str | Path, every_sec: float = 0.5) -> Iterator[CandidateFrame]:
    """Sample candidate frames from a video at roughly ``every_sec`` intervals.

    Yields:
        CandidateFrame: RGB image (HxWx3, uint8) and timestamp in seconds.

    Raises:
        ValueError: If ``every_sec`` is not positive.
        IngestError: If the video cannot be opened, has no video stream, or is corrupt.
    """
    if every_sec <= 0:
        raise ValueError(f"every_sec must be positive, got {every_sec}")

    target = Path(path)
    if not target.is_file():
        raise IngestError(f"unreadable video: file not found {path}")

    container: Any = None
    try:
        try:
            container = av.open(str(target))
        except (av.error.FFmpegError, OSError, ValueError) as exc:
            raise IngestError(f"unreadable video: {exc}") from exc

        if not container.streams.video:
            raise IngestError("unreadable video: no video stream found")

        stream = container.streams.video[0]
        next_target = 0.0

        try:
            for frame in container.decode(video=0):
                if frame.time is not None:
                    t_sec = float(frame.time)
                elif frame.pts is not None and stream.time_base is not None:
                    t_sec = float(frame.pts * stream.time_base)
                else:
                    t_sec = 0.0

                if t_sec >= next_target - 1e-5:
                    rgb = cast(
                        np.ndarray[Any, np.dtype[np.uint8]], frame.to_ndarray(format="rgb24")
                    )
                    yield CandidateFrame(image=rgb, t_sec=round(t_sec, 4))
                    next_target += every_sec
        except (av.error.FFmpegError, OSError, ValueError) as exc:
            raise IngestError(f"unreadable video: decode failed: {exc}") from exc
    finally:
        if container is not None:
            with contextlib.suppress(Exception):
                container.close()
