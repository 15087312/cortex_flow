"""Node dispatcher."""

from __future__ import annotations

from typing import Any

from cortexflow.compiler.ir import NodeIR
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


class NodeDispatcher:
    """Dispatch nodes for execution."""

    async def dispatch(self, node_ir: NodeIR, context: ExecutionContext) -> Any:
        """Dispatch node."""
        node = NodeRegistry.create(node_ir.type, node_ir.id, node_ir.config)
        return await node.execute(context)
