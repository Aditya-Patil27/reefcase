"""POST /api/surveys — turn an uploaded clip into a queued survey (Story 2.1, §6.3).

Validation happens before anything is stored: a non-video suffix is a 422 naming
``video``, lat/lon outside §4.2 bounds are 422s naming the field, and a body
larger than ``MAX_VIDEO_BYTES`` is a 413. The video is streamed to
``blobs/{survey_id}/video<ext>`` (the upload's own suffix) through ``Store.blobs``
and the ``Site`` and ``Survey`` rows persist through the store's single writer, so the survey is
readable after the app shuts down (the store is the only database).
"""

import asyncio
import contextlib
from datetime import UTC, date, datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from reefcase.agent.ask import Answer, AskRequest, ask
from reefcase.core.errors import NotFoundError
from reefcase.core.events import ToolReturned
from reefcase.core.ids import SITE, SURVEY, new_id
from reefcase.core.schemas import (
    Frame,
    FrameAssessment,
    GeoPoint,
    Investigation,
    Segmentation,
    Site,
    Survey,
    SurveyStatus,
    ToolResult,
)
from reefcase.llm.providers import build_model

__all__ = ["MAX_VIDEO_BYTES", "VIDEO_SUFFIXES", "FrameDetail", "router"]

router = APIRouter()

MAX_VIDEO_BYTES = 500 * 1024 * 1024

VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".avi", ".webm", ".mkv"})


def _video_suffix(filename: str | None) -> str:
    """Return the lower-cased suffix of ``filename`` (empty when there is none)."""
    return PurePosixPath(filename or "").suffix.lower()


def _now() -> datetime:
    """The creation timestamp for new rows (UTC, tz-aware)."""
    return datetime.now(UTC)


def _site_name(lat: float, lon: float, site_name: str | None) -> str:
    """The site's display name: the given one, or ``Reef @ lat,lon`` (§2.1/2.5 rule)."""
    if site_name:
        return site_name
    return f"Reef @ {lat:.5f}, {lon:.5f}"


@router.post("/surveys", response_model=Survey, status_code=201)
async def create_survey(
    request: Request,
    video: UploadFile,
    lat: Annotated[float, Form()],
    lon: Annotated[float, Form()],
    dive_date: Annotated[date, Form()],
    site_name: Annotated[str | None, Form()] = None,
    source: Annotated[Literal["upload", "bot"], Form()] = "upload",
) -> Survey:
    """Store an uploaded clip as a queued survey at the nearest site (or a new one)."""
    suffix = _video_suffix(video.filename)
    if suffix not in VIDEO_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"video: unsupported file type {suffix or '(no extension)'}; "
            f"expected one of {', '.join(sorted(VIDEO_SUFFIXES))}",
        )

    if not -90.0 <= lat <= 90.0:
        raise HTTPException(
            status_code=422,
            detail=f"lat: must be between -90 and 90, got {lat}",
        )
    if not -180.0 <= lon <= 180.0:
        raise HTTPException(
            status_code=422,
            detail=f"lon: must be between -180 and 180, got {lon}",
        )

    # Starlette has already spooled the upload to a temp file and counted its bytes.
    if video.size is not None and video.size > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"video: larger than {MAX_VIDEO_BYTES} bytes",
        )

    survey_id = new_id(SURVEY)
    store = request.app.state.store
    video_ref = await asyncio.to_thread(
        store.blobs.save_video_stream, survey_id, video.file, suffix
    )
    await video.close()

    # A survey within 500 m of an existing site joins it (2.5, FR12).
    location = GeoPoint(lat=lat, lon=lon)
    site = await store.sites.find_site_near(location)
    if site is None:
        site = Site(
            id=new_id(SITE),
            name=_site_name(lat, lon, site_name),
            location=location,
            created_at=_now(),
        )
        await store.sites.save(site)
    survey = Survey(
        id=survey_id,
        site_id=site.id,
        dive_date=dive_date,
        status=SurveyStatus.QUEUED,
        source=source,
        video_path=video_ref,
        created_at=_now(),
    )
    await store.surveys.save(survey)
    return survey


@router.get("/surveys/{survey_id}", response_model=Survey)
async def get_survey(survey_id: str, request: Request) -> Survey:
    """Return one survey, or 404 when the id is unknown."""
    try:
        return await request.app.state.store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class FrameDetail(BaseModel):
    """A frame alongside its segmentation and assessment (Story 5.4, §6.3)."""

    frame: Frame
    segmentation: Segmentation | None = None
    assessment: FrameAssessment | None = None


@router.get(
    "/surveys/{survey_id}/investigation",
    response_model=Investigation,
    operation_id="getInvestigation",
    summary="The investigation, once the report is ready",
    responses={404: {"description": "Not ready yet."}},
)
async def get_investigation(survey_id: str, request: Request) -> Investigation:
    """Return the survey's investigation, or 404 until ready."""
    store = request.app.state.store
    try:
        await store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return await store.investigations.get_by_survey(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not ready yet.") from exc


@router.get(
    "/surveys/{survey_id}/frames",
    response_model=list[FrameDetail],
    operation_id="getSurveyFrames",
    summary="Frames with quality, segmentation and assessment",
)
async def get_survey_frames(survey_id: str, request: Request) -> list[FrameDetail]:
    """Return the survey's frames with quality, segmentation and assessment."""
    store = request.app.state.store
    try:
        await store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    frames = await store.frames.list_by_survey(survey_id)
    segs = await store.segmentations.list_by_survey(survey_id)
    assessments = await store.assessments.list_by_survey(survey_id)

    seg_by_frame = {s.frame_id: s for s in segs}
    assessment_by_frame = {a.frame_id: a for a in assessments}

    return [
        FrameDetail(
            frame=frame,
            segmentation=seg_by_frame.get(frame.id),
            assessment=assessment_by_frame.get(frame.id),
        )
        for frame in frames
    ]


@router.post(
    "/surveys/{survey_id}/ask",
    response_model=Answer,
    operation_id="askSurvey",
    summary="Ask a question about the survey's investigation",
    responses={
        404: {"description": "Survey not found."},
        409: {"description": "Investigation not ready yet."},
        422: {"description": "Invalid question."},
        504: {"description": "The model took too long to answer."},
    },
)
async def ask_survey(
    survey_id: str,
    payload: AskRequest,
    request: Request,
) -> Answer:
    """Answer a follow-up question about the survey's investigation."""
    store = request.app.state.store
    try:
        await store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found.") from exc

    try:
        investigation = await store.investigations.get_by_survey(survey_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=409, detail=f"Survey {survey_id} has no investigation yet."
        ) from exc

    frames = await store.frames.list_by_survey(survey_id)
    segs = await store.segmentations.list_by_survey(survey_id)
    assessments = await store.assessments.list_by_survey(survey_id)

    events = await store.events.list(survey_id)
    tool_results: list[ToolResult] = []
    seen_ids: set[str] = set()
    for ev in events:
        if isinstance(ev, ToolReturned) and ev.tool_result_id not in seen_ids:
            seen_ids.add(ev.tool_result_id)
            with contextlib.suppress(NotFoundError):
                tool_results.append(await store.tool_results.get(ev.tool_result_id))

    model = build_model("agent", request.app.state.settings)
    if model is None:
        raise HTTPException(status_code=500, detail="agent model not configured")

    try:
        return await ask(
            payload.question,
            investigation,
            frames,
            segs,
            assessments,
            tool_results,
            model=model,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="The model took too long to answer.") from exc
