"""Knowledge node - Write side of the knowledge base (chunk + store)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.rag.loader import FileLoader
from cortexflow.rag.splitter import RecursiveTextSplitter
from cortexflow.runtime.context import ExecutionContext

ACTIONS = {"ingest_text", "ingest_file", "ingest_directory", "list", "delete", "clear"}


@NodeRegistry.register("knowledge")
class KnowledgeNode(BaseNode):
    """Ingest documents into the memory namespace used by ``retrieval``.

    Retrieval reads chunks from the memory adapter, so ingestion chunks the
    input and stores each chunk with source metadata in the same namespace.
    """

    async def execute(self, context: ExecutionContext) -> Any:
        action = self.config.get("knowledge_action", "ingest_text")
        if action not in ACTIONS:
            raise ValueError(f"Knowledge node '{self.node_id}' has unknown action '{action}'")

        namespace = self.resolve(self.config.get("knowledge_namespace"), context)
        namespace = str(namespace) if namespace else "default"

        memory = context.get_adapter("memory")
        if not memory:
            raise RuntimeError("Memory adapter not available for knowledge node")

        if action == "list":
            entries = await memory.list_all(namespace=namespace)
            return {
                "action": "list",
                "namespace": namespace,
                "count": len(entries),
                "entries": entries,
            }

        if action == "clear":
            await memory.clear(namespace=namespace)
            return {"action": "clear", "namespace": namespace}

        if action == "delete":
            entry_id = self.resolve(self.config.get("knowledge_entry_id"), context)
            if not entry_id:
                raise ValueError(f"Knowledge node '{self.node_id}' delete needs 'knowledge_entry_id'")
            deleted = await memory.delete(str(entry_id), namespace=namespace)
            return {
                "action": "delete",
                "namespace": namespace,
                "entry_id": str(entry_id),
                "deleted": bool(deleted),
            }

        documents = self._load_documents(action, context)
        splitter = RecursiveTextSplitter(
            chunk_size=self.config.get("knowledge_chunk_size", 500),
            chunk_overlap=self.config.get("knowledge_overlap", 50),
        )
        metadata = self.resolve(self.config.get("knowledge_metadata") or {}, context)
        if not isinstance(metadata, dict):
            metadata = {}

        chunk_total = 0
        for source, text in documents:
            chunks = splitter.split_text(text)
            for index, chunk in enumerate(chunks):
                await memory.store(
                    content=chunk,
                    namespace=namespace,
                    metadata={
                        **metadata,
                        "source": source,
                        "chunk_index": index,
                        "total_chunks": len(chunks),
                    },
                )
            chunk_total += len(chunks)

        return {
            "action": action,
            "namespace": namespace,
            "documents": len(documents),
            "chunks": chunk_total,
            "sources": [source for source, _ in documents],
        }

    def _load_documents(self, action: str, context: ExecutionContext) -> list[tuple[str, str]]:
        source = self.resolve(self.config.get("knowledge_source"), context)
        if not source:
            raise ValueError(f"Knowledge node '{self.node_id}' needs 'knowledge_source'")
        source = str(source)

        if action == "ingest_text":
            return [("text", source)]

        path = Path(source).expanduser()
        loader = FileLoader()
        loaded = loader.load(path)
        if not loaded:
            raise ValueError(f"Knowledge node '{self.node_id}' found no documents at '{path}'")
        return [(doc.metadata.get("source", str(path)), doc.content) for doc in loaded]
