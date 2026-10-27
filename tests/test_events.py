"""Tests for event bus."""

import asyncio

import pytest

from cortexflow.events.bus import EventBus
from cortexflow.events.types import Event, EventType


@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    received = []
    await bus.subscribe("test.event", lambda e: received.append(e))
    await bus.publish(Event(type="test.event", payload={"key": "value"}))
    assert len(received) == 1
    assert received[0].payload["key"] == "value"


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    results = []
    await bus.subscribe("test", lambda e: results.append("a"))
    await bus.subscribe("test", lambda e: results.append("b"))
    await bus.publish(Event(type="test"))
    assert results == ["a", "b"]


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    results = []
    handler = lambda e: results.append(e)
    await bus.subscribe("test", handler)
    await bus.publish(Event(type="test"))
    assert len(results) == 1
    await bus.unsubscribe("test", handler)
    await bus.publish(Event(type="test"))
    assert len(results) == 1


@pytest.mark.asyncio
async def test_wait_for():
    bus = EventBus()

    async def delayed_publish():
        await asyncio.sleep(0.05)
        await bus.publish(Event(type="my_event", payload={"data": 42}))

    asyncio.create_task(delayed_publish())
    event = await bus.wait_for("my_event", timeout=2.0)
    assert event.payload["data"] == 42


@pytest.mark.asyncio
async def test_wait_for_timeout():
    bus = EventBus()
    with pytest.raises(asyncio.TimeoutError):
        await bus.wait_for("never_happens", timeout=0.05)


@pytest.mark.asyncio
async def test_wait_for_with_filter():
    bus = EventBus()

    async def delayed_publish():
        await asyncio.sleep(0.02)
        await bus.publish(Event(type="evt", payload={"id": "wrong"}))
        await asyncio.sleep(0.02)
        await bus.publish(Event(type="evt", payload={"id": "right"}))

    asyncio.create_task(delayed_publish())
    event = await bus.wait_for("evt", filter={"id": "right"}, timeout=2.0)
    assert event.payload["id"] == "right"


@pytest.mark.asyncio
async def test_async_handler():
    bus = EventBus()
    results = []

    async def handler(e):
        await asyncio.sleep(0.01)
        results.append(e.payload.get("v"))

    await bus.subscribe("test", handler)
    await bus.publish(Event(type="test", payload={"v": 99}))
    assert results == [99]


def test_event_type_constants():
    assert EventType.NODE_STARTED == "node.started"
    assert EventType.FLOW_COMPLETED == "flow.completed"
    assert EventType.FLOW_SUSPENDED == "flow.suspended"


@pytest.mark.asyncio
async def test_wildcard_subscriber_receives_every_event():
    bus = EventBus()
    seen = []
    await bus.subscribe("*", lambda e: seen.append(e.type))
    await bus.publish(Event(type="one"))
    await bus.publish(Event(type="two"))
    assert seen == ["one", "two"]


@pytest.mark.asyncio
async def test_specific_and_wildcard_handlers_both_fire_once():
    bus = EventBus()
    calls = []
    await bus.subscribe("thing", lambda e: calls.append("specific"))
    await bus.subscribe("*", lambda e: calls.append("wildcard"))
    await bus.publish(Event(type="thing"))
    assert calls == ["specific", "wildcard"]
