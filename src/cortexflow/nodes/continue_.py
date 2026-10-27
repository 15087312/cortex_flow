"""Continue node - Skip to the next loop iteration (Coze-style).

Must be placed inside a loop body chain. Nodes after it in the same body
chain are skipped for the current iteration.
"""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import LoopContinue


@NodeRegistry.register("continue")
class ContinueNode(BaseNode):
    """Skip to the next loop iteration."""

    async def execute(self, context: ExecutionContext) -> Any:
        raise LoopContinue(self.node_id)
