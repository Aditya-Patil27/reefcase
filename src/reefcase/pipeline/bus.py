"""The event bus: persist, then fan out; replay without gaps (architecture §6.2).

``publish`` writes the event to the ``events`` table *first* (so a replay after
a crash still contains it), then hands the in-memory event to every live
subscriber of that survey. ``subscribe`` yields the stored events after
``after_seq`` and then the live ones, so an SSE reconnect (``Last-Event-ID``)
sees a gapless, duplicate-free stream. The seq is allocated by the publisher
via ``EventRepo.next_seq`` before calling ``publish`` — the table stays the
single source of truth, which makes the replay/live overlap trivial to dedup.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Final

from reefcase.core.events import Event
from reefcase.store.db import Store

__all__ = ["STREAM_END", "EventBus"]

#: Sentinel queued to every subscriber of a survey when its stream should end.
#: A queue item is either an ``Event`` or this string.
STREAM_END: Final[str] = "stream_end"

_QueueItem = Event | str


class EventBus:
    """Persists events, then fans them out to per-survey subscribers."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._queues: dict[str, list[asyncio.Queue[_QueueItem]]] = {}

    async def publish(self, event: Event) -> None:
        """Persist ``event``, then hand it to this survey's live subscribers."""
        await self._store.events.append(event)
        for queue in self._queues.get(event.survey_id, []):
            queue.put_nowait(event)

    async def end_stream(self, survey_id: str) -> None:
        """Tell every live subscriber of ``survey_id`` that the stream is over."""
        for queue in self._queues.get(survey_id, []):
            queue.put_nowait(STREAM_END)

    async def subscribe(
        self, survey_id: str, after_seq: int = 0, *, timeout: float = 0.05
    ) -> AsyncGenerator[Event]:
        """Yield stored events after ``after_seq``, then live ones, without gaps.

        The queue is registered before the replay, so an event published during
        the replay is buffered, not lost. Every idle wait ends with a catch-up
        read from the table (a publisher outside this process never touches the
        queues), and the sentinel triggers one final catch-up before the
        generator returns. ``timeout`` is the catch-up cadence while idle.
        """
        queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._queues.setdefault(survey_id, []).append(queue)
        try:
            last = after_seq
            for event in await self._store.events.list(survey_id, after_seq):
                yield event
                last = event.seq
            while True:
                item: _QueueItem | None
                try:
                    item = await asyncio.wait_for(queue.get(), timeout)
                except TimeoutError:
                    item = None
                if item is None:
                    # Idle: re-read the table for anything published off-process.
                    async for event in self._catch_up(survey_id, last):
                        yield event
                        last = event.seq
                    continue
                if isinstance(item, str):  # the stream-end sentinel
                    async for event in self._catch_up(survey_id, last):
                        yield event
                    return
                if item.seq <= last:  # already delivered by a catch-up read
                    continue
                yield item
                last = item.seq
        finally:
            subscribers = self._queues.get(survey_id)
            if subscribers is not None and queue in subscribers:
                subscribers.remove(queue)
                if not subscribers:
                    self._queues.pop(survey_id, None)

    async def _catch_up(self, survey_id: str, after_seq: int) -> AsyncGenerator[Event]:
        """Yield stored events newer than ``after_seq`` (the gapless tail)."""
        for event in await self._store.events.list(survey_id, after_seq):
            yield event
