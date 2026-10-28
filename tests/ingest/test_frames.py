"""Tests for candidate frame extraction (Story 2.3; architecture §6.4)."""

import itertools
from pathlib import Path

import numpy as np
import pytest

from reefcase.ingest.frames import CandidateFrame, IngestError, extract_candidates

CLIP_10S = Path("tests/fixtures/clip_10s.mp4")


def test_extract_candidates_yields_expected_frames() -> None:
    assert CLIP_10S.is_file()
    candidates = list(extract_candidates(CLIP_10S, every_sec=0.5))

    # Acceptance criterion: ~20 RGB frames with their t_sec
    assert 19 <= len(candidates) <= 21
    assert len(candidates) == 20

    # Verify frame type, shape and properties
    first = candidates[0]
    assert isinstance(first, CandidateFrame)
    assert isinstance(first.image, np.ndarray)
    assert first.image.ndim == 3
    assert first.image.shape[2] == 3
    assert first.image.dtype == np.uint8
    assert first.t_sec == pytest.approx(0.0, abs=1e-3)

    # Verify tuple unpacking
    img, t = first
    assert np.array_equal(img, first.image)
    assert t == first.t_sec

    # Verify timestamps are monotonically increasing up to ~10.0s
    timestamps = [c.t_sec for c in candidates]
    for prev, curr in itertools.pairwise(timestamps):
        assert curr > prev
        assert curr - prev == pytest.approx(0.5, abs=0.05)
    assert timestamps[-1] < 10.0


def test_extract_candidates_different_stride() -> None:
    candidates_1s = list(extract_candidates(CLIP_10S, every_sec=1.0))
    assert 9 <= len(candidates_1s) <= 11
    assert len(candidates_1s) == 10

    candidates_2s = list(extract_candidates(CLIP_10S, every_sec=2.0))
    assert len(candidates_2s) == 5


def test_extract_candidates_invalid_stride() -> None:
    with pytest.raises(ValueError, match="positive"):
        list(extract_candidates(CLIP_10S, every_sec=0.0))
    with pytest.raises(ValueError, match="positive"):
        list(extract_candidates(CLIP_10S, every_sec=-1.0))


def test_extract_candidates_nonexistent_file() -> None:
    with pytest.raises(IngestError, match="unreadable video"):
        list(extract_candidates("tests/fixtures/does_not_exist.mp4"))


def test_extract_candidates_corrupt_file(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not a valid mp4 header or video stream data")
    with pytest.raises(IngestError, match="unreadable video"):
        list(extract_candidates(corrupt))


def test_extract_candidates_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(IngestError, match="unreadable video"):
        list(extract_candidates(empty))
