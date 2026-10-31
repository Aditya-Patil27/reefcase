"""Tests for Telegram bot interface (Story 8.2).

Offline tests using respx to mock the ReefCase API. Zero calls to Telegram.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from reefcase.bot.main import (
    MAX_TELEGRAM_FILE_BYTES,
    ChatSession,
    LocationPayload,
    VideoPayload,
    follow_survey_events,
    handle_location,
    handle_video,
)
from reefcase.core.events import ReportReady, SurveyFailed

API_URL = "http://test-api"
FAKE_CLIP = b"fake video bytes"


def _make_video(size: int = 1024, dive_date: date = date(2026, 10, 20)) -> VideoPayload:
    return VideoPayload(
        content=FAKE_CLIP,
        filename="clip.mp4",
        dive_date=dive_date,
        size=size,
    )


def _make_location() -> LocationPayload:
    return LocationPayload(lat=19.7292, lon=-157.4132)


class MockSender:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def __call__(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


@pytest.mark.asyncio
@respx.mock
async def test_video_then_location_success() -> None:
    sender = MockSender()
    session = ChatSession()

    respx.post(f"{API_URL}/api/surveys").respond(
        status_code=201,
        json={"id": "srv_123", "status": "queued", "source": "bot"},
    )

    report_ready_event = ReportReady(
        survey_id="srv_123",
        seq=1,
        ts=datetime.now(UTC),
        investigation_id="inv_123",
    )
    sse_body = f"event: report_ready\ndata: {report_ready_event.model_dump_json()}\n\n"
    respx.get(f"{API_URL}/api/surveys/srv_123/events").respond(
        status_code=200,
        content=sse_body,
        headers={"content-type": "text/event-stream"},
    )

    respx.get(f"{API_URL}/api/surveys/srv_123/investigation").respond(
        status_code=200,
        json={
            "id": "inv_123",
            "survey_id": "srv_123",
            "verdict": "Thermal stress caused extensive bleaching.",
            "findings": [
                {"statement": "Severe coral bleaching on 60% of colonies.", "evidence": []},
                {"statement": "Water temperature exceeded 31C for 3 weeks.", "evidence": []},
                {"statement": "No signs of crown-of-thorns starfish predation.", "evidence": []},
                {"statement": "Low algal turf overgrowth observed.", "evidence": []},
            ],
            "hypotheses": [],
            "recommendations": [],
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    async with httpx.AsyncClient() as client:
        # Step 1: Send video first
        await handle_video(session, _make_video(), 101, sender, client, API_URL)
        assert len(sender.messages) == 1
        assert "location" in sender.messages[0][1].lower()

        # Step 2: Send location
        await handle_location(session, _make_location(), 101, sender, client, API_URL)

    # Assertions
    assert len(sender.messages) == 3
    assert sender.messages[1][1] == "Investigating…"
    final_msg = sender.messages[2][1]
    assert "Thermal stress caused extensive bleaching." in final_msg
    assert "Severe coral bleaching on 60% of colonies." in final_msg
    assert "Water temperature exceeded 31C for 3 weeks." in final_msg
    assert "No signs of crown-of-thorns starfish predation." in final_msg
    assert "Low algal turf" not in final_msg  # Only top 3
    assert f"{API_URL}/surveys/srv_123" in final_msg


@pytest.mark.asyncio
@respx.mock
async def test_location_then_video_success() -> None:
    sender = MockSender()
    session = ChatSession()

    respx.post(f"{API_URL}/api/surveys").respond(
        status_code=201,
        json={"id": "srv_456", "status": "queued", "source": "bot"},
    )

    report_ready_event = ReportReady(
        survey_id="srv_456",
        seq=1,
        ts=datetime.now(UTC),
        investigation_id="inv_456",
    )
    sse_body = f"event: report_ready\ndata: {report_ready_event.model_dump_json()}\n\n"
    respx.get(f"{API_URL}/api/surveys/srv_456/events").respond(
        status_code=200,
        content=sse_body,
        headers={"content-type": "text/event-stream"},
    )

    respx.get(f"{API_URL}/api/surveys/srv_456/investigation").respond(
        status_code=200,
        json={
            "id": "inv_456",
            "survey_id": "srv_456",
            "verdict": "Mechanical anchor damage detected.",
            "findings": [
                {"statement": "Linear scar across reef crest.", "evidence": []},
            ],
            "hypotheses": [],
            "recommendations": [],
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    async with httpx.AsyncClient() as client:
        # Step 1: Send location first
        await handle_location(session, _make_location(), 202, sender, client, API_URL)
        assert len(sender.messages) == 1
        assert "clip" in sender.messages[0][1].lower()

        # Step 2: Send video
        await handle_video(session, _make_video(), 202, sender, client, API_URL)

    assert len(sender.messages) == 3
    assert sender.messages[1][1] == "Investigating…"
    final_msg = sender.messages[2][1]
    assert "Mechanical anchor damage detected." in final_msg
    assert "Linear scar across reef crest." in final_msg
    assert f"{API_URL}/surveys/srv_456" in final_msg


@pytest.mark.asyncio
async def test_clip_over_20mb_rejected() -> None:
    sender = MockSender()
    session = ChatSession()

    large_video = _make_video(size=MAX_TELEGRAM_FILE_BYTES + 1)
    async with httpx.AsyncClient() as client:
        await handle_video(session, large_video, 303, sender, client, API_URL)

    assert len(sender.messages) == 1
    assert sender.messages[0][1] == "clip is over 20 MB, trim it or upload it on the website"
    assert session.video is None


@pytest.mark.asyncio
@respx.mock
async def test_api_422_rejection() -> None:
    sender = MockSender()
    session = ChatSession()

    respx.post(f"{API_URL}/api/surveys").respond(
        status_code=422,
        json={"detail": "lat: must be between -90 and 90, got 99.0"},
    )

    async with httpx.AsyncClient() as client:
        await handle_location(
            session, LocationPayload(lat=99.0, lon=0.0), 404, sender, client, API_URL
        )
        await handle_video(session, _make_video(), 404, sender, client, API_URL)

    assert len(sender.messages) == 2
    assert "Location received" in sender.messages[0][1]
    err_msg = sender.messages[1][1]
    assert "lat: must be between -90 and 90, got 99.0" in err_msg


@pytest.mark.asyncio
@respx.mock
async def test_survey_failed_event() -> None:
    sender = MockSender()
    session = ChatSession()

    respx.post(f"{API_URL}/api/surveys").respond(
        status_code=201,
        json={"id": "srv_fail", "status": "queued", "source": "bot"},
    )

    failed_event = SurveyFailed(
        survey_id="srv_fail",
        seq=1,
        ts=datetime.now(UTC),
        reason="Water turbidity too high: 0 frames passed quality scoring",
    )
    sse_body = f"event: survey_failed\ndata: {failed_event.model_dump_json()}\n\n"
    respx.get(f"{API_URL}/api/surveys/srv_fail/events").respond(
        status_code=200,
        content=sse_body,
        headers={"content-type": "text/event-stream"},
    )

    async with httpx.AsyncClient() as client:
        await handle_video(session, _make_video(), 505, sender, client, API_URL)
        await handle_location(session, _make_location(), 505, sender, client, API_URL)

    assert len(sender.messages) == 3
    assert sender.messages[1][1] == "Investigating…"
    fail_msg = sender.messages[2][1]
    assert "Investigation failed" in fail_msg
    assert "Water turbidity too high" in fail_msg


@pytest.mark.asyncio
@respx.mock
async def test_stream_that_ends_early_is_resumed_after_the_last_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The API ends the stream while a survey is queued; the bot must reconnect, not go silent.
    monkeypatch.setattr("reefcase.bot.main.RECONNECT_S", 0.0)
    sender = MockSender()
    failed = SurveyFailed(survey_id="srv_q", seq=8, ts=datetime.now(UTC), reason="no frames")
    route = respx.get(f"{API_URL}/api/surveys/srv_q/events")
    route.side_effect = [
        httpx.Response(200, content=": stream_end\n\n"),
        httpx.Response(200, content="id: 7\nevent: frame_scored\ndata: {}\n\n: stream_end\n\n"),
        httpx.Response(
            200, content=f"id: 8\nevent: survey_failed\ndata: {failed.model_dump_json()}\n\n"
        ),
    ]

    async with httpx.AsyncClient() as client:
        await follow_survey_events("srv_q", 606, sender, client, API_URL)

    assert [m for _, m in sender.messages] == ["Investigation failed: no frames"]
    headers = [call.request.headers.get("last-event-id") for call in route.calls]
    assert headers == [None, None, "7"]
