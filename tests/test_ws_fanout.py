"""Tests for the websocket event fan-out used by the live UI."""

import asyncio

import pytest

from cortexflow.api import routes
from cortexflow.events.bus import EventBus
from cortexflow.events.types import Event


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    routes._event_queues.clear()
    monkeypatch.setattr(routes, "_bus_subscribed", False)
    yield
    routes._event_queues.clear()


@pytest.mark.asyncio
async def test_on_event_delivers_one_copy_per_queue():
    first, second = asyncio.Queue(), asyncio.Queue()
    routes._event_queues.extend([first, second])

    await routes._on_event(Event(type="flow.message", payload={"content": "hi"}))

    assert first.qsize() == 1
    assert second.qsize() == 1
    assert (await first.get()).payload["content"] == "hi"


@pytest.mark.asyncio
async def test_on_event_skips_full_queues():
    full = asyncio.Queue(maxsize=1)
    full.put_nowait(Event(type="old"))
    routes._event_queues.append(full)

    await routes._on_event(Event(type="new"))

    assert full.qsize() == 1
    assert (await full.get()).type == "old"


@pytest.mark.asyncio
async def test_event_subscription_is_registered_once(monkeypatch):
    bus = EventBus()

    class FakeEngine:
        event_bus = bus

    monkeypatch.setattr(routes, "_get_engine", lambda: FakeEngine())

    await routes._ensure_event_subscription()
    await routes._ensure_event_subscription()

    assert len(bus._handlers["*"]) == 1
