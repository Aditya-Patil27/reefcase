"""The in-process job runner (architecture §6.1).

One runner polls the ``surveys`` table for queued work and runs the stage
chain ``ingest → segment → assess → investigate`` for up to
``concurrency`` surveys at once. The stages themselves are injected as a
single async callable (each stage story — 2.3, 3.5, 5.1, 5.4 — fills it in;
2.2's tests stub it). Any exception flips the survey to ``FAILED`` and emits
``survey_failed`` with the reason; the stage chain stops there.

All status flips and events go through the single-writer ``Store`` and the
:class:`~reefcase.pipeline.bus.EventBus`.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from reefcase.core.events import SurveyFailed, SurveyStarted
from reefcase.core.schemas import SurveyStatus
from reefcase.pipeline.bus import EventBus
from reefcase.store.db import Store

__all__ = ["JobRunner", "RunStages"]

RunStages = Callable[[Store, str], Awaitable[None]]

logger = logging.getLogger(__name__)


class JobRunner:
    """Runs queued surveys, up to ``concurrency`` at a time, until closed."""

    def __init__(
        self,
        store: Store,
        run_stages: RunStages | None = None,
        *,
        bus: EventBus | None = None,
        poll_interval: float = 0.05,
        concurrency: int = 2,
    ) -> None:
        self._store = store
        self._run_stages = run_stages
        self._bus = bus if bus is not None else EventBus(store)
        self._poll_interval = poll_interval
        self._concurrency = concurrency
        self._pending: asyncio.Queue[str] = asyncio.Queue()
        self._wakeup = asyncio.Event()
        self._closed = False
        self._inflight: set[asyncio.Task[None]] = set()

    async def submit(self, survey_id: str) -> None:
        """Queue a survey and wake the poll loop."""
        await self._pending.put(survey_id)
        self._wakeup.set()

    def close(self) -> None:
        """Ask ``run_forever`` to return after the current surveys finish."""
        self._closed = True
        self._wakeup.set()

    async def run_forever(self) -> None:
        """Poll for work until :meth:`close`.

        Each claimed survey runs in its own :class:`asyncio.Task`; a new survey
        is claimed only while fewer than ``concurrency`` tasks are in flight.
        On close, the loop stops claiming and returns once the in-flight
        surveys finish.
        """
        while not self._closed:
            if len(self._inflight) >= self._concurrency:
                await self._sleep()
                continue
            survey_id = self._pending.get_nowait() if not self._pending.empty() else None
            if survey_id is None:
                survey_id = await self._claim()
            if survey_id is None:
                await self._sleep()
                continue
            self._spawn(survey_id)
        if self._inflight:
            await asyncio.gather(*self._inflight, return_exceptions=True)
        self._wakeup.set()

    async def run_once(self) -> bool:
        """Claim and run one queued survey to completion; return whether it ran.

        Always one survey per call, awaited inline (the concurrency limit only
        applies to ``run_forever``'s in-flight tasks), so tests can drive the
        loop deterministically.
        """
        survey_id = self._pending.get_nowait() if not self._pending.empty() else None
        if survey_id is None:
            survey_id = await self._claim()
        if survey_id is None:
            return False
        await self._run(survey_id)
        return True

    def _spawn(self, survey_id: str) -> None:
        """Start one survey in a background task and track it as in flight."""
        task = asyncio.create_task(self._run(survey_id))
        self._inflight.add(task)
        task.add_done_callback(self._on_done)

    def _on_done(self, task: asyncio.Task[None]) -> None:
        """Drop a finished task from the in-flight set and wake the poll loop."""
        self._inflight.discard(task)
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                # ``_run`` already marks the survey FAILED for stage errors; a
                # task-level exception means something escaped it (e.g. the
                # store broke before the stage chain started).
                logger.error("survey job crashed outside the stage chain", exc_info=exc)
        self._wakeup.set()

    async def _sleep(self) -> None:
        """Wait for the next poll tick or an explicit wake-up."""
        self._wakeup.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._wakeup.wait(), self._poll_interval)

    async def _claim(self) -> str | None:
        """Return one queued survey (oldest first), ``None`` when idle."""
        rows = await self._store.fetchall(
            """
            SELECT id FROM surveys
            WHERE status = 'queued'
            ORDER BY created_at, id
            LIMIT 1
            """,
        )
        return rows[0][0] if rows else None

    async def _run(self, survey_id: str) -> None:
        """Flip the survey to RUNNING, run the stages, then DONE or FAILED."""
        survey = await self._store.surveys.get(survey_id)
        if survey.status is not SurveyStatus.QUEUED:
            return  # claimed by another runner; leave it alone
        site_id = survey.site_id
        survey.status = SurveyStatus.RUNNING
        await self._store.surveys.save(survey)
        await self._bus.publish(
            SurveyStarted(
                survey_id=survey_id,
                seq=await self._store.events.next_seq(survey_id),
                ts=_now(),
                site_id=site_id,
            )
        )
        try:
            if self._run_stages is not None:
                await self._run_stages(self._store, survey_id)
            survey.status = SurveyStatus.DONE
            await self._store.surveys.save(survey)
        except Exception as exc:
            survey.status = SurveyStatus.FAILED
            survey.failure_reason = str(exc)
            await self._store.surveys.save(survey)
            await self._bus.publish(
                SurveyFailed(
                    survey_id=survey_id,
                    seq=await self._store.events.next_seq(survey_id),
                    ts=_now(),
                    reason=str(exc),
                )
            )


def _now() -> datetime:
    return datetime.now(UTC)
