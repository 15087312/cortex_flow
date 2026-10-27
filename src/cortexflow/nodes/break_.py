"""Break node - Exit the enclosing loop immediately (Coze-style).

Must be placed inside a loop body chain. The loop keeps results collected
so far and resumes routing via ``on_complete`` / ``on_success``.
"""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import LoopBreak


@NodeRegistry.register("break")
class BreakNode(BaseNode):
    """Exit the enclosing loop."""

    async def execute(self, context: ExecutionContext) -> Any:
        raise LoopBreak(self.node_id)
