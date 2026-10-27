"""Memory manager with consolidation, decay, and persistence."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cortexflow.memory.types import MemoryEntry, MemoryType, MemoryImportance
from cortexflow.memory.store import (
    ShortTermMemoryStore,
    LongTermMemoryStore,
    EpisodicMemoryStore,
    SemanticMemoryStore,
)


class MemoryManager:
    """Manages multiple memory stores with consolidation and decay."""

    def __init__(self, persistence_path: str | Path | None = None) -> None:
        self.short_term = ShortTermMemoryStore()
        self.long_term = LongTermMemoryStore()
        self.episodic = EpisodicMemoryStore()
        self.semantic = SemanticMemoryStore()

        self._stores = {
            MemoryType.SHORT_TERM: self.short_term,
            MemoryType.LONG_TERM: self.long_term,
            MemoryType.EPISODIC: self.episodic,
            MemoryType.SEMANTIC: self.semantic,
        }

        self._persistence_path = Path(persistence_path) if persistence_path else None
        if self._persistence_path and self._persistence_path.exists():
            self._load_from_disk()

    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        namespace: str = "default",
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Store a memory entry."""
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            importance=importance,
            namespace=namespace,
            metadata=metadata or {},
            tags=tags or [],
        )
        store = self._stores.get(memory_type, self.short_term)
        return store.store(entry)

    def get(self, memory_id: str) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        for store in self._stores.values():
            entry = store.get(memory_id)
            if entry:
                return entry
        return None

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        namespace: str | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[dict[str, Any]]:
        """Search across memory stores."""
        if memory_type:
            store = self._stores.get(memory_type)
            if store:
                return store.search(query, top_k, min_score, namespace)
            return []

        all_results = []
        for store in self._stores.values():
            results = store.search(query, top_k=top_k * 2, min_score=min_score, namespace=namespace)
            all_results.extend(results)

        all_results.sort(key=lambda x: -x["score"])
        return all_results[:top_k]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        for store in self._stores.values():
            if store.delete(memory_id):
                return True
        return False

    def clear(self, namespace: str | None = None, memory_type: MemoryType | None = None) -> int:
        """Clear memories."""
        if memory_type:
            store = self._stores.get(memory_type)
            return store.clear(namespace) if store else 0

        total = 0
        for store in self._stores.values():
            total += store.clear(namespace)
        return total

    def consolidate(self, threshold: float = 0.6) -> int:
        """Consolidate short-term memories to long-term."""
        consolidated = 0
        to_promote = []

        for entry in self.short_term.list_all():
            if entry.should_consolidate(threshold):
                to_promote.append(entry)

        for entry in to_promote:
            new_entry = MemoryEntry(
                content=entry.content,
                memory_type=MemoryType.LONG_TERM,
                importance=entry.importance,
                namespace=entry.namespace,
                metadata={**entry.metadata, "consolidated_from": entry.memory_id},
                tags=entry.tags,
                strength=entry.strength,
            )
            self.long_term.store(new_entry)
            self.short_term.delete(entry.memory_id)
            consolidated += 1

        return consolidated

    def apply_decay(self) -> int:
        """Apply decay to all memories and forget weak ones."""
        forgotten = 0
        current_time = time.time()

        for store in self._stores.values():
            to_forget = []
            for entry in store.list_all():
                entry.apply_decay(current_time)
                if entry.should_forget():
                    to_forget.append(entry.memory_id)

            for mid in to_forget:
                store.delete(mid)
                forgotten += 1

        return forgotten

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "short_term": self.short_term.count,
            "long_term": self.long_term.count,
            "episodic": self.episodic.count,
            "semantic": self.semantic.count,
            "total": sum(s.count for s in self._stores.values()),
        }

    def save_to_disk(self) -> None:
        """Persist memories to disk."""
        if not self._persistence_path:
            return

        data = {
            "short_term": [e.to_dict() for e in self.short_term.list_all()],
            "long_term": [e.to_dict() for e in self.long_term.list_all()],
            "episodic": [e.to_dict() for e in self.episodic.list_all()],
            "semantic": [e.to_dict() for e in self.semantic.list_all()],
        }

        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        self._persistence_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _load_from_disk(self) -> None:
        """Load memories from disk."""
        if not self._persistence_path or not self._persistence_path.exists():
            return

        data = json.loads(self._persistence_path.read_text())

        for mem_type, entries in data.items():
            store = self._stores.get(MemoryType(mem_type))
            if store:
                for entry_data in entries:
                    entry = MemoryEntry.from_dict(entry_data)
                    store.store(entry)

    def list_all(self, namespace: str | None = None, memory_type: MemoryType | None = None) -> list[dict[str, Any]]:
        """List all memories."""
        if memory_type:
            store = self._stores.get(memory_type)
            return [e.to_dict() for e in store.list_all(namespace)] if store else []

        all_entries = []
        for store in self._stores.values():
            all_entries.extend([e.to_dict() for e in store.list_all(namespace)])
        return all_entries
