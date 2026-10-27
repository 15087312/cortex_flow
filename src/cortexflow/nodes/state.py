"""State node - Read/write state."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("state")
class StateNode(BaseNode):
    """Read/write state."""

    async def execute(self, context: ExecutionContext) -> Any:
        actions = self.config.get("actions", [])
        results = {}

        for action_def in actions:
            action = action_def.get("action", "set")
            if action == "set":
                target = action_def.get("target")
                value = action_def.get("value")
                resolved_value = self.resolve(value, context)
                context.set_variable(target, resolved_value)
                results[target] = resolved_value
            elif action == "read":
                source = action_def.get("source")
                output = action_def.get("output")
                value = context.get_variable(source)
                if output:
                    context.set_variable(output, value)
                    results[output] = value
            elif action == "append":
                target = action_def.get("target")
                value = action_def.get("value")
                resolved_value = self.resolve(value, context)
                current = context.get_variable(target) or []
                if not isinstance(current, list):
                    current = [current]
                current.append(resolved_value)
                context.set_variable(target, current)
                results[target] = current

        return results
