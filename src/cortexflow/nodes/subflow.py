"""Subflow node - Call sub-workflows."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("subflow")
class SubflowNode(BaseNode):
    """Call a sub-workflow via executor."""

    async def execute(self, context: ExecutionContext) -> Any:
        flow_id = self.config.get("flow")
        if not flow_id:
            raise ValueError("Subflow node missing 'flow' field")

        input_data = self.config.get("input", {})
        share_blackboard = self.config.get("share_blackboard", False)
        resolved_input = self.resolve(input_data, context)

        if context.executor:
            result = await context.executor.execute_subflow(
                flow_id=flow_id,
                input_variables=resolved_input,
                parent_context=context,
                share_blackboard=share_blackboard,
            )
        else:
            result = {
                "flow_id": flow_id,
                "input": resolved_input,
                "output": f"Mock result from subflow {flow_id}",
            }

        return result
