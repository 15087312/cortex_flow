"""Retrieval node - Knowledge base retrieval / RAG."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("retrieval")
class RetrievalNode(BaseNode):
    """Retrieve documents from knowledge base for RAG."""

    async def execute(self, context: ExecutionContext) -> Any:
        query = self.resolve(self.config.get("retrieval_query", ""), context)
        if not query:
            query = str(context.variables.get("input", ""))

        source = self.config.get("retrieval_source", "memory")
        top_k = self.config.get("retrieval_top_k", 5)
        collection = self.config.get("retrieval_collection")

        memory = context.get_adapter("memory")
        if not memory:
            raise RuntimeError("Memory adapter not available for retrieval")

        namespace = collection or source
        results = await memory.query(
            query=str(query),
            top_k=top_k,
            namespace=namespace,
        )

        documents = [r["content"] for r in results]
        return {
            "query": str(query),
            "documents": documents,
            "results": results,
            "count": len(results),
        }
