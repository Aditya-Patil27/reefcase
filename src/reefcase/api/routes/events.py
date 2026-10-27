"""``GET /api/surveys/{id}/events`` — the live event stream (architecture §6.3).

SSE framing: ``id:`` = ``seq``, ``event:`` = ``type``, ``data:`` = the event's
JSON (``type`` included, which is what the web reducer parses). The stream
replays the stored log after ``Last-Event-ID`` and then follows live events.
It ends once the survey is no longer ``running`` — the client's
``EventSource`` reconnects and the replay makes that gapless — and signs off
with an SSE comment so the termination is visible when debugging.
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from reefcase.core.errors import NotFoundError
from reefcase.core.schemas import SurveyStatus
from reefcase.pipeline.bus import EventBus
from reefcase.store.db import Store

__all__ = ["router"]

router = APIRouter()

_WATCH_INTERVAL = 0.05


def _frame(seq: int, event_type: str, data: str) -> str:
    """One SSE frame: ``id``/``event``/``data`` and the blank-line terminator."""
    return f"id: {seq}\nevent: {event_type}\ndata: {data}\n\n"


@router.get("/surveys/{survey_id}/events")
async def survey_events(
    request: Request,
    survey_id: str,
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    """Stream the survey's events, replaying everything after ``Last-Event-ID``."""
    store: Store = request.app.state.store
    try:
        await store.surveys.get(survey_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    after_seq = 0
    if last_event_id is not None:
        try:
            after_seq = int(last_event_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Last-Event-ID must be an integer") from exc

    bus: EventBus = request.app.state.bus

    async def body() -> AsyncGenerator[str]:
        watcher = asyncio.create_task(_end_when_not_running(store, survey_id, bus))
        try:
            async for event in bus.subscribe(survey_id, after_seq=after_seq):
                yield _frame(event.seq, event.type, event.model_dump_json())
            yield ": stream_end\n\n"
        finally:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )


async def _end_when_not_running(store: Store, survey_id: str, bus: EventBus) -> None:
    """End the stream once the survey leaves ``running`` (or disappears)."""
    while True:
        try:
            survey = await store.surveys.get(survey_id)
        except NotFoundError:
            await bus.end_stream(survey_id)
            return
        if survey.status is not SurveyStatus.RUNNING:
            await bus.end_stream(survey_id)
            return
        await asyncio.sleep(_WATCH_INTERVAL)
