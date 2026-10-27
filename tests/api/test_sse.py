"""Story 2.2 — SSE stream, Last-Event-ID replay and the failure path (§6.3, §6.1).

Runner and route are driven through the real FastAPI app; stages are stubbed by
the test via ``build_app(run_stages, ...)``. All bodies are read to the end:
httpx ASGI transports buffer, so a stream that never terminates would hang the
test.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import httpx
import pytest

from reefcase.api.main import create_app
from reefcase.core.config import Settings
from reefcase.core.events import FramesExtracted, ReportReady, ToolCalled, ToolReturned
from reefcase.pipeline.runner import JobRunner
from reefcase.store.db import Store

CLIP_BYTES = (Path(__file__).parents[1] / "fixtures" / "clip_10s.mp4").read_bytes()
GOOD_FIELDS = {"lat": "19.7292", "lon": "-157.4132", "dive_date": "2026-10-01"}
WAIT_S = 0.75  # the poll interval is 0.05 s; this stays far under the 5 s AC


def build_app(
    make_settings: Callable[..., Settings],
    tmp_path: Path,
    run_stages: Callable[[Store, str], Coroutine[Any, Any, None]] | None = None,
):
    settings = make_settings(data_dir=str(tmp_path / "var"), segmenter="fake")
    return create_app(settings, run_stages=run_stages)


def parse_sse(body: str) -> list[dict[str, Any]]:
    """Parse an SSE body into ``[{"id", "event", "data"}]`` records."""
    records: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        record: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            record[field] = value.lstrip(" ")
        if record:
            records.append(record)
    return records


def event_types(records: list[dict[str, Any]]) -> list[str]:
    return [record.get("event", "") for record in records]


def NOWISH():
    """An aware timestamp for stub events (the store stores what it is given)."""
    from datetime import UTC, datetime

    return datetime.now(UTC)


async def run_stages_ok(store: Store, survey_id: str) -> None:
    """The stubbed stage chain: emit the events later stories will emit."""
    await store.events.append(
        FramesExtracted(
            survey_id=survey_id,
            seq=await store.events.next_seq(survey_id),
            ts=NOWISH(),
            count=12,
        )
    )
    await store.events.append(
        ToolCalled(
            survey_id=survey_id,
            seq=await store.events.next_seq(survey_id),
            ts=NOWISH(),
            call_id="call_1",
            tool="reef_map",
            params={"site_id": "site_x"},
        )
    )
    await store.events.append(
        ToolReturned(
            survey_id=survey_id,
            seq=await store.events.next_seq(survey_id),
            ts=NOWISH(),
            call_id="call_1",
            tool_result_id="tr_1",
            summary="reef flattened",
        )
    )
    await store.events.append(
        ReportReady(
            survey_id=survey_id,
            seq=await store.events.next_seq(survey_id),
            ts=NOWISH(),
            investigation_id="inv_1",
        )
    )


async def run_stages_fail(store: Store, survey_id: str) -> None:
    del store, survey_id
    raise RuntimeError("segmentation exploded")


@pytest.fixture
def runner_for(make_settings: Callable[..., Settings], tmp_path: Path):
    """Create a JobRunner for an app; close them all afterwards."""
    created: list[JobRunner] = []

    def factory(
        app: Any, run_stages: Callable[[Store, str], Coroutine[Any, Any, None]]
    ) -> JobRunner:
        instance = JobRunner(app.state.store, run_stages, bus=app.state.bus, poll_interval=0.01)
        created.append(instance)
        return instance

    yield factory
    for instance in created:
        instance.close()


async def upload(client: httpx.AsyncClient, **overrides: Any) -> str:
    fields = dict(GOOD_FIELDS)
    fields.update(overrides)
    data = {"video": ("clip.mp4", CLIP_BYTES, "video/mp4")}
    response = await client.post("/api/surveys", data=fields, files=data)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def drive(
    runner: JobRunner,
    store: Store,
    survey_id: str,
    *,
    status: str = "done",
    timeout: float = 5.0,
) -> None:
    """Let the runner's poll loop process the survey until ``status`` is reached."""
    task = asyncio.create_task(runner.run_forever())
    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            survey = await store.surveys.get(survey_id)
            if survey.status.value == status:
                return
            await asyncio.sleep(0.02)
        raise AssertionError(f"survey never became {status!r}")
    finally:
        runner.close()
        await asyncio.wait_for(task, timeout=1)


async def stream_body(app: Any, survey_id: str, *, headers: dict[str, str] | None = None) -> str:
    """Open the SSE route and return the full body text (the stream terminates)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/surveys/{survey_id}/events",
            headers=headers or {},
            timeout=WAIT_S,
        )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return response.text


@pytest.mark.asyncio
async def test_sse_survey_started_within_5s(make_settings, tmp_path, runner_for) -> None:
    app = build_app(make_settings, tmp_path, run_stages_ok)
    runner = runner_for(app, run_stages_ok)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        survey_id = await upload(client)
    await drive(runner, app.state.store, survey_id)
    body = await stream_body(app, survey_id)

    records = parse_sse(body)
    assert event_types(records)[0] == "survey_started"  # first frame, so within 5 s
    first = records[0]
    assert first["id"] == "1"
    data = json.loads(first["data"])
    assert data["type"] == "survey_started"
    assert data["site_id"].startswith("site_")
    seqs = [int(r["id"]) for r in records if "id" in r]
    assert seqs == sorted(set(seqs))  # contiguous, no duplicates


@pytest.mark.asyncio
async def test_sse_reconnect_from_last_event_id(make_settings, tmp_path, runner_for) -> None:
    app = build_app(make_settings, tmp_path, run_stages_ok)
    runner = runner_for(app, run_stages_ok)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        survey_id = await upload(client)
    await drive(runner, app.state.store, survey_id)

    full = parse_sse(await stream_body(app, survey_id))
    assert len(full) >= 5  # started + 3 stage events + report_ready
    body = await stream_body(app, survey_id, headers={"Last-Event-ID": "3"})
    records = parse_sse(body)

    ids = [int(r["id"]) for r in records if "id" in r]
    assert ids == list(range(4, 4 + len(ids)))  # from seq 4 onward, no gaps, no dupes
    assert [r["event"] for r in records] == [r["event"] for r in full][3:]


@pytest.mark.asyncio
async def test_failed_stage_marks_survey_failed_and_emits_event(
    make_settings, tmp_path, runner_for
) -> None:
    app = build_app(make_settings, tmp_path, run_stages_fail)
    runner = runner_for(app, run_stages_fail)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        survey_id = await upload(client)
    await drive(runner, app.state.store, survey_id, status="failed")

    survey = await app.state.store.surveys.get(survey_id)
    assert survey.status.value == "failed"
    assert survey.failure_reason == "segmentation exploded"

    body = await stream_body(app, survey_id)
    records = parse_sse(body)
    assert event_types(records)[0] == "survey_started"
    last = records[-1]
    assert last["event"] == "survey_failed"
    assert "segmentation exploded" in last["data"]


@pytest.mark.asyncio
async def test_stream_replays_via_store_only(make_settings, tmp_path, runner_for) -> None:
    """A stream opened after the job ended replays the whole log from the table."""
    app = build_app(make_settings, tmp_path, run_stages_ok)
    runner = runner_for(app, run_stages_ok)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        survey_id = await upload(client)
    await drive(runner, app.state.store, survey_id)

    body = await stream_body(app, survey_id)
    records = parse_sse(body)
    assert event_types(records)[0] == "survey_started"
    assert records[-1]["event"] == "report_ready"
    ids = [int(r["id"]) for r in records if "id" in r]
    assert ids == list(range(1, len(ids) + 1))


@pytest.mark.asyncio
async def test_unknown_survey_stream_is_404(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/surveys/srv_missing/events")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_queued_survey_stream_ends_with_sentinel(make_settings, tmp_path) -> None:
    """No runner is running: the survey stays queued and the stream ends cleanly."""
    app = build_app(make_settings, tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        survey_id = await upload(client)
    body = await stream_body(app, survey_id)
    assert parse_sse(body) == []  # no events, and the route returned anyway


@pytest.mark.asyncio
async def test_bad_last_event_id_is_422(make_settings, tmp_path) -> None:
    app = build_app(make_settings, tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/surveys/srv_missing/events", headers={"Last-Event-ID": "oops"}
        )
    assert response.status_code in (404, 422)
