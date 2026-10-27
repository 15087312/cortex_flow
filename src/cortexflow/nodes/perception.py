"""Perception node - Collect perception data."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("perception")
class PerceptionNode(BaseNode):
    """Collect perception data via adapter."""

    async def execute(self, context: ExecutionContext) -> Any:
        source = self.config.get("source")
        if not source:
            raise ValueError("Perception node missing 'source' field")

        perception_config = self.config.get("config", {})
        write_to_blackboard = self.config.get("write_to_blackboard", False)

        perception_adapter = context.get_adapter("perception")
        if perception_adapter:
            result = await perception_adapter.collect(source, perception_config)
        else:
            result = {
                "source": source,
                "config": perception_config,
                "data": f"Mock perception data from {source}",
            }

        if write_to_blackboard:
            context.blackboard.add_observation(
                tier=self.config.get("tier", "default"),
                content=str(result),
            )

        return result
