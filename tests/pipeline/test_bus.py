"""Story 2.2 — the event bus: persist-then-fanout, replay, stream end (§6.2)."""

import asyncio
from datetime import UTC, datetime

import pytest

from reefcase.core.errors import StoreError
from reefcase.core.events import Event, SurveyFailed, SurveyStarted
from reefcase.pipeline.bus import STREAM_END, EventBus
from reefcase.store.db import Store

NOW = datetime(2026, 10, 27, 18, 30, tzinfo=UTC)
SETTLE = 0.15  # > one poll timeout: the subscriber has replayed and gone live


def started(seq: int = 1, site_id: str = "site_a") -> SurveyStarted:
    return SurveyStarted(survey_id="srv_x", seq=seq, ts=NOW, site_id=site_id)


def failed(seq: int, reason: str = "boom") -> SurveyFailed:
    return SurveyFailed(survey_id="srv_x", seq=seq, ts=NOW, reason=reason)


async def collect(bus: EventBus, survey_id: str, after_seq: int = 0) -> list[Event]:
    """Consume one subscription until the stream-end sentinel (or hang the test)."""
    got: list[Event] = []

    async def run() -> list[Event]:
        async for event in bus.subscribe(survey_id, after_seq=after_seq):
            got.append(event)
        return got

    return await asyncio.wait_for(run(), timeout=5)


async def settle() -> None:
    await asyncio.sleep(SETTLE)


def types(events: list[Event]) -> list[str]:
    return [event.type for event in events]


@pytest.mark.asyncio
async def test_publish_persists_then_fans_out(store: Store) -> None:
    bus = EventBus(store)
    task = asyncio.create_task(collect(bus, "srv_x"))
    await settle()

    event = started()
    await bus.publish(event)
    await settle()
    await bus.end_stream("srv_x")
    received = await task

    stored = await store.events.list("srv_x")
    assert [e.seq for e in stored] == [1]
    assert stored[0] == event
    assert received == [event]


def test_stream_end_sentinel_is_a_string() -> None:
    assert STREAM_END == "stream_end"


@pytest.mark.asyncio
async def test_subscribe_replays_stored_events_then_goes_live(store: Store) -> None:
    bus = EventBus(store)
    first = started(seq=1, site_id="site_r")
    await bus.publish(first)

    task = asyncio.create_task(collect(bus, "srv_x"))
    await settle()

    second = failed(seq=2)
    await bus.publish(second)
    await bus.end_stream("srv_x")
    received = await task

    assert types(received) == ["survey_started", "survey_failed"]


@pytest.mark.asyncio
async def test_subscribe_after_seq_skips_older_events(store: Store) -> None:
    bus = EventBus(store)
    await bus.publish(started(seq=1, site_id="site_r"))
    await bus.publish(failed(seq=2, reason="old"))

    task = asyncio.create_task(collect(bus, "srv_x", after_seq=2))
    await settle()

    third = failed(seq=3, reason="new")
    await bus.publish(third)
    await bus.end_stream("srv_x")
    received = await task

    assert received == [third]


@pytest.mark.asyncio
async def test_stream_end_stops_a_live_subscription(store: Store) -> None:
    bus = EventBus(store)
    event = started()
    await bus.publish(event)

    task = asyncio.create_task(collect(bus, "srv_x"))
    await settle()
    await bus.end_stream("srv_x")

    assert types(await task) == ["survey_started"]


@pytest.mark.asyncio
async def test_fanout_is_scoped_to_the_survey_subscribers(store: Store) -> None:
    bus = EventBus(store)
    task = asyncio.create_task(collect(bus, "srv_x"))
    await settle()

    other = SurveyStarted(survey_id="srv_y", seq=1, ts=NOW, site_id="site_b")
    await bus.publish(other)
    await settle()
    await bus.end_stream("srv_x")

    assert await task == []


@pytest.mark.asyncio
async def test_end_stream_without_subscribers_is_a_noop(store: Store) -> None:
    bus = EventBus(store)
    await bus.end_stream("srv_nobody")


@pytest.mark.asyncio
async def test_duplicate_seq_still_raises_through_the_bus(store: Store) -> None:
    bus = EventBus(store)
    event = started()
    await bus.publish(event)
    with pytest.raises(StoreError):
        await bus.publish(event)


@pytest.mark.asyncio
async def test_replay_is_contiguous_across_publishes(store: Store) -> None:
    bus = EventBus(store)
    for seq in (1, 2, 3):
        await bus.publish(failed(seq, f"r{seq}"))

    events = await store.events.list("srv_x")
    assert [e.seq for e in events] == [1, 2, 3]
