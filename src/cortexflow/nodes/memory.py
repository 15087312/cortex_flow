"""Memory node - Store and query long-term memory."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("memory")
class MemoryNode(BaseNode):
    """Store or query memories via the memory adapter."""

    async def execute(self, context: ExecutionContext) -> Any:
        action = self.config.get("memory_action", "query")
        content = self.resolve(self.config.get("memory_content", ""), context)
        namespace = self.resolve(self.config.get("memory_namespace"), context)
        top_k = self.config.get("memory_top_k", 5)
        min_score = self.config.get("memory_min_score", 0.0)

        memory = context.get_adapter("memory")
        if not memory:
            raise RuntimeError("Memory adapter not available")

        if action == "store":
            metadata = {}
            if namespace:
                metadata["namespace"] = namespace
            await memory.store(
                content=str(content),
                namespace=namespace,
                metadata=metadata,
            )
            return {"action": "stored", "content": str(content)}

        query_text = str(content) if content else self.resolve(
            self.config.get("retrieval_query", ""), context
        )
        if not query_text:
            query_text = str(context.variables.get("input", ""))

        results = await memory.query(
            query=query_text,
            top_k=top_k,
            namespace=namespace,
            min_score=min_score or 0.0,
        )
        return {"results": results, "query": query_text, "count": len(results)}
