"""Tool node - Call tools."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import WaitEvent


@NodeRegistry.register("tool")
class ToolNode(BaseNode):
    """Call a tool via adapter."""

    async def execute(self, context: ExecutionContext) -> Any:
        tool_name = self.config.get("tool")
        if not tool_name:
            raise ValueError("Tool node missing 'tool' field")

        args = self.config.get("args", {})
        require_approval = self.config.get("require_approval", False)
        resolved_args = self.resolve(args, context)

        if require_approval:
            approval_id = f"approval_{self.node_id}_{id(self)}"
            context.set_variable("approval_request_id", approval_id)

            if not context.get_variable(f"_approval_{approval_id}"):
                raise WaitEvent(
                    event_type="user_approval",
                    filter={"request_id": approval_id},
                )

        tool_adapter = context.get_adapter("tool")
        if tool_adapter:
            result = await tool_adapter.invoke(tool_name, resolved_args)
        else:
            result = {
                "tool": tool_name,
                "args": resolved_args,
                "output": f"Mock result from tool {tool_name}",
            }

        return result
