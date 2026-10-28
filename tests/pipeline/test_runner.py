"""Story 2.2 — the runner's concurrency limit (architecture §6.1).

``run_forever`` must run surveys in parallel up to ``concurrency`` and never
claim past the limit. The stub stages block on per-survey gates, so overlap
(and the peak in-flight count) is observed offline — no HTTP, no live services.
"""

import asyncio
from datetime import UTC, date, datetime

import pytest

from reefcase.core.schemas import Survey, SurveyStatus
from reefcase.pipeline.runner import JobRunner
from reefcase.store.db import Store

POLL = 0.005  # status-poll tick while a stage gate is held


def make_survey(survey_id: str) -> Survey:
    """A queued survey row, ready to be claimed by the runner."""
    return Survey(
        id=survey_id,
        site_id="site_a",
        dive_date=date(2026, 10, 25),
        status=SurveyStatus.QUEUED,
        source="upload",
        created_at=datetime(2026, 10, 26, 9, 30, tzinfo=UTC),
    )


async def wait_for_status(
    store: Store, survey_id: str, status: SurveyStatus, *, timeout: float = 2.0
) -> None:
    """Poll the store until ``survey_id`` reaches ``status`` (or hang the test)."""

    async def poll() -> None:
        while True:
            survey = await store.surveys.get(survey_id)
            if survey.status is status:
                return
            await asyncio.sleep(POLL)

    await asyncio.wait_for(poll(), timeout)


@pytest.mark.asyncio
async def test_run_forever_never_exceeds_the_concurrency_limit(store: Store) -> None:
    in_flight = 0
    peak = 0
    started: list[str] = []
    gates: dict[str, asyncio.Event] = {}

    async def gated_stages(_store: Store, survey_id: str) -> None:
        """Block each survey mid-flight until its gate is released."""
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        started.append(survey_id)
        await gates[survey_id].wait()
        in_flight -= 1

    survey_ids = [f"srv_{i:04d}" for i in range(3)]
    for survey_id in survey_ids:
        gates[survey_id] = asyncio.Event()
        await store.surveys.save(make_survey(survey_id))

    runner = JobRunner(store, gated_stages, poll_interval=0.01, concurrency=2)
    loop_task = asyncio.create_task(runner.run_forever())
    try:
        # The two oldest surveys claim concurrently and overlap in flight.
        await wait_for_status(store, "srv_0000", SurveyStatus.RUNNING)
        await wait_for_status(store, "srv_0001", SurveyStatus.RUNNING)
        survey_0 = await store.surveys.get("srv_0000")
        assert survey_0.status is SurveyStatus.RUNNING  # still blocked, so overlapping
        assert peak == 2
        assert started == ["srv_0000", "srv_0001"]  # the third was never claimed

        # Releasing one survey frees a slot; only then does the third start.
        gates["srv_0000"].set()
        await wait_for_status(store, "srv_0002", SurveyStatus.RUNNING)
        assert started == ["srv_0000", "srv_0001", "srv_0002"]
    finally:
        gates["srv_0001"].set()
        gates["srv_0002"].set()
        runner.close()
        await asyncio.wait_for(loop_task, timeout=2)

    assert peak == 2  # never more than the limit of 2 in flight
    statuses = [(await store.surveys.get(survey_id)).status for survey_id in survey_ids]
    assert statuses == [SurveyStatus.DONE, SurveyStatus.DONE, SurveyStatus.DONE]
