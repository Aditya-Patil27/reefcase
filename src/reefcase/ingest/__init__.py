"""Re-export ingest's public names (architecture §3)."""

from reefcase.ingest.frames import CandidateFrame, IngestError, extract_candidates
from reefcase.ingest.quality import (
    BLUR_THRESHOLD,
    COLOR_CAST_THRESHOLD,
    TURBIDITY_THRESHOLD,
    QualityError,
    score,
)

__all__ = [
    "BLUR_THRESHOLD",
    "COLOR_CAST_THRESHOLD",
    "TURBIDITY_THRESHOLD",
    "CandidateFrame",
    "IngestError",
    "QualityError",
    "extract_candidates",
    "score",
]
