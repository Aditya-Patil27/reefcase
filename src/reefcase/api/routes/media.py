"""GET /media/{survey_id}/thumbs/{frame_id}.jpg — a small copy of a stored frame (§6.3).

A frame is stored at full size (often 1920 px, about 1 MB); the frame grid shows it at a
few hundred pixels, so it asks for this instead. The first request makes the thumbnail
and writes it beside the frame; later requests serve that file.
"""

import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image

__all__ = ["CACHE_CONTROL", "THUMB_WIDTH", "router"]

router = APIRouter()

# A blob is never rewritten under the same id, so a day in the browser cache is safe.
CACHE_CONTROL = "public, max-age=86400"
THUMB_WIDTH = 640
_ID = re.compile(r"[A-Za-z0-9_-]+")


@router.get("/media/{survey_id}/thumbs/{frame_id}.jpg", include_in_schema=False)
def get_thumb(survey_id: str, frame_id: str, request: Request) -> FileResponse:
    """Serve the frame's thumbnail, making it first if needed; 404 when the frame is unknown."""
    if not (_ID.fullmatch(survey_id) and _ID.fullmatch(frame_id)):
        raise HTTPException(status_code=404)
    blobs = request.app.state.store.blobs
    thumb = blobs.thumb_path(survey_id, frame_id)
    if not thumb.is_file():
        frame = blobs.frame_path(survey_id, frame_id)
        if not frame.is_file():
            raise HTTPException(status_code=404)
        _make_thumb(frame, thumb)
    return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": CACHE_CONTROL})


def _make_thumb(frame: Path, thumb: Path) -> None:
    """Write a ``THUMB_WIDTH``-wide JPEG of ``frame`` to ``thumb``, atomically."""
    thumb.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(frame) as image:
        image.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 4))
        fd, tmp = tempfile.mkstemp(dir=thumb.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as out:
                image.convert("RGB").save(out, format="JPEG", quality=80)
            os.replace(tmp, thumb)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
