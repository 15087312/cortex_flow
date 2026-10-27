"""Wait node - Wait for external events."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import WaitEvent


@NodeRegistry.register("wait")
class WaitNode(BaseNode):
    """Wait for external event."""

    async def execute(self, context: ExecutionContext) -> Any:
        event_type = self.config.get("event")
        if not event_type:
            raise ValueError("Wait node missing 'event' field")

        event_filter = self.config.get("filter", {})
        resolved_filter = self.resolve(event_filter, context)

        raise WaitEvent(event_type, resolved_filter)
