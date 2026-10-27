"""Event bus - Async event dispatch."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from cortexflow.events.types import Event

logger = logging.getLogger(__name__)


class EventBus:
    """Async event bus."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._waiters: dict[str, list[asyncio.Future]] = defaultdict(list)

    async def publish(self, event: Event) -> None:
        """Publish event to type-specific and wildcard (``"*"``) handlers."""
        # Call handlers
        handlers = list(self._handlers.get(event.type, []))
        if event.type != "*":
            handlers.extend(self._handlers.get("*", []))
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                logger.exception("Event handler failed for %s", event.type)

        # Wake up waiters
        for future in self._waiters.get(event.type, []):
            if not future.done():
                future.set_result(event)
        self._waiters[event.type].clear()

    async def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to event type."""
        self._handlers[event_type].append(handler)

    async def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe from event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def wait_for(
        self, event_type: str, filter: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Event:
        """Wait for event."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._waiters[event_type].append(future)

        event = await asyncio.wait_for(future, timeout)
        if filter:
            for key, value in filter.items():
                if event.payload.get(key) != value:
                    return await self.wait_for(event_type, filter, timeout)
        return event
