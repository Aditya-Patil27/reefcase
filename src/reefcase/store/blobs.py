"""Blob paths and bytes under ``<data_dir>/blobs`` (architecture §6.4).

Schemas store data-dir-relative POSIX refs (``blobs/<survey_id>/frames/<frame_id>.jpg``),
never absolute paths, so a seeded ``data/demo/`` tree can move between hosts.
``Blobs`` builds the absolute ``Path`` for I/O and converts with ``ref()`` /
``resolve()``.
"""

import shutil
from pathlib import Path
from typing import BinaryIO

from reefcase.core.errors import StoreError

__all__ = ["BLOBS_DIRNAME", "Blobs"]

BLOBS_DIRNAME = "blobs"


def _normalise_suffix(suffix: str) -> str:
    """Return ``suffix`` as a lower-cased, dot-prefixed extension."""
    cleaned = suffix.strip().lower()
    if not cleaned:
        return ""
    return cleaned if cleaned.startswith(".") else f".{cleaned}"


class Blobs:
    """Paths and bytes under ``<data_dir>/blobs`` (architecture §6.4)."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)

    @property
    def root(self) -> Path:
        """``<data_dir>/blobs``."""
        return self._data_dir / BLOBS_DIRNAME

    def survey_dir(self, survey_id: str) -> Path:
        """``<root>/<survey_id>``."""
        return self.root / survey_id

    def frame_path(self, survey_id: str, frame_id: str) -> Path:
        """``<root>/<survey_id>/frames/<frame_id>.jpg``."""
        return self.survey_dir(survey_id) / "frames" / f"{frame_id}.jpg"

    def mask_path(self, survey_id: str, frame_id: str) -> Path:
        """``<root>/<survey_id>/masks/<frame_id>.png``."""
        return self.survey_dir(survey_id) / "masks" / f"{frame_id}.png"

    def video_path(self, survey_id: str, suffix: str = ".mp4") -> Path:
        """``<root>/<survey_id>/video<ext>``."""
        return self.survey_dir(survey_id) / f"video{_normalise_suffix(suffix)}"

    def ref(self, path: Path) -> str:
        """Return ``path`` as a data-dir-relative POSIX string."""
        try:
            return Path(path).relative_to(self._data_dir).as_posix()
        except ValueError as exc:
            raise StoreError(f"blob path is outside the data dir: {path}") from exc

    def resolve(self, ref: str) -> Path:
        """Return the absolute path for ``ref``; reject anything escaping the data dir."""
        data_dir = self._data_dir.resolve()
        path = (data_dir / ref).resolve()
        if not path.is_relative_to(data_dir):
            raise StoreError(f"blob path escapes the data dir: {ref}")
        return path

    def save_frame(self, survey_id: str, frame_id: str, data: bytes) -> str:
        """Write ``data`` as the frame image and return its ref."""
        return self._write(self.frame_path(survey_id, frame_id), data)

    def save_mask(self, survey_id: str, frame_id: str, data: bytes) -> str:
        """Write ``data`` as the frame mask and return its ref."""
        return self._write(self.mask_path(survey_id, frame_id), data)

    def save_video(self, survey_id: str, data: bytes, suffix: str = ".mp4") -> str:
        """Write ``data`` as the survey video and return its ref."""
        return self._write(self.video_path(survey_id, suffix), data)

    def save_video_stream(self, survey_id: str, source: BinaryIO, suffix: str = ".mp4") -> str:
        """Copy ``source`` to the survey video without loading it into memory; return its ref."""
        path = self.video_path(survey_id, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as target:
            shutil.copyfileobj(source, target)
        return self.ref(path)

    def read(self, ref: str) -> bytes:
        """Read the bytes behind ``ref``."""
        return self.resolve(ref).read_bytes()

    def _write(self, path: Path, data: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.ref(path)
