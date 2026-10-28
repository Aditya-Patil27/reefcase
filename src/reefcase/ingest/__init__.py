"""Re-export ingest's public names (architecture §3)."""

from reefcase.ingest.frames import CandidateFrame, IngestError, extract_candidates

__all__ = ["CandidateFrame", "IngestError", "extract_candidates"]
