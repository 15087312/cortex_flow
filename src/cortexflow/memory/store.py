"""Memory stores for different memory types."""

from __future__ import annotations

import math
import hashlib
import time
from typing import Any

from cortexflow.memory.types import MemoryEntry, MemoryType, MemoryImportance


class BaseMemoryStore:
    """Base class for memory stores."""

    def __init__(self) -> None:
        self._memories: dict[str, MemoryEntry] = {}

    def store(self, entry: MemoryEntry) -> str:
        self._memories[entry.memory_id] = entry
        return entry.memory_id

    def get(self, memory_id: str) -> MemoryEntry | None:
        entry = self._memories.get(memory_id)
        if entry:
            entry.access()
        return entry

    def delete(self, memory_id: str) -> bool:
        return self._memories.pop(memory_id, None) is not None

    def list_all(self, namespace: str | None = None) -> list[MemoryEntry]:
        entries = list(self._memories.values())
        if namespace:
            entries = [e for e in entries if e.namespace == namespace]
        return entries

    def clear(self, namespace: str | None = None) -> int:
        if namespace:
            to_remove = [mid for mid, e in self._memories.items() if e.namespace == namespace]
            for mid in to_remove:
                del self._memories[mid]
            return len(to_remove)
        count = len(self._memories)
        self._memories.clear()
        return count

    @property
    def count(self) -> int:
        return len(self._memories)


class VectorMemoryStore(BaseMemoryStore):
    """Memory store with vector-based similarity search."""

    def __init__(self, dim: int = 128) -> None:
        super().__init__()
        self._dim = dim
        self._embeddings: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = text.lower().split()
        for i, token in enumerate(tokens):
            h = hashlib.md5(token.encode()).hexdigest()
            for j in range(0, min(len(h), self._dim * 2), 2):
                idx = int(h[j:j + 2], 16) % self._dim
                weight = 1.0 / (1.0 + 0.1 * i)
                vec[idx] += weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def store(self, entry: MemoryEntry) -> str:
        mid = super().store(entry)
        self._embeddings[mid] = self._embed(entry.content)
        return mid

    def delete(self, memory_id: str) -> bool:
        self._embeddings.pop(memory_id, None)
        return super().delete(memory_id)

    def clear(self, namespace: str | None = None) -> int:
        if namespace:
            to_remove = [mid for mid, e in self._memories.items() if e.namespace == namespace]
            for mid in to_remove:
                del self._memories[mid]
                self._embeddings.pop(mid, None)
            return len(to_remove)
        count = len(self._memories)
        self._memories.clear()
        self._embeddings.clear()
        return count

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        namespace: str | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[dict[str, Any]]:
        query_vec = self._embed(query)
        scored = []

        for mid, emb_vec in self._embeddings.items():
            entry = self._memories.get(mid)
            if not entry:
                continue
            if namespace and entry.namespace != namespace:
                continue
            if memory_type and entry.memory_type != memory_type:
                continue

            score = sum(a * b for a, b in zip(query_vec, emb_vec))
            score *= entry.strength
            if score >= min_score:
                scored.append((mid, score, entry))

        scored.sort(key=lambda x: -x[1])

        results = []
        for mid, score, entry in scored[:top_k]:
            entry.access()
            results.append({
                "memory_id": mid,
                "content": entry.content,
                "score": score,
                "memory_type": entry.memory_type.value,
                "importance": entry.importance.value,
                "metadata": entry.metadata,
                "strength": entry.strength,
                "tags": entry.tags,
            })
        return results


class ShortTermMemoryStore(VectorMemoryStore):
    """Short-term memory with fast decay."""

    def __init__(self) -> None:
        super().__init__()
        self._max_capacity = 100

    def store(self, entry: MemoryEntry) -> str:
        entry.memory_type = MemoryType.SHORT_TERM
        entry.decay_rate = 0.5
        mid = super().store(entry)
        self._enforce_capacity()
        return mid

    def _enforce_capacity(self) -> None:
        while len(self._memories) > self._max_capacity:
            oldest_id = min(
                self._memories,
                key=lambda mid: self._memories[mid].last_accessed,
            )
            self.delete(oldest_id)


class LongTermMemoryStore(VectorMemoryStore):
    """Long-term memory with slow decay."""

    def store(self, entry: MemoryEntry) -> str:
        entry.memory_type = MemoryType.LONG_TERM
        entry.decay_rate = 0.01
        return super().store(entry)


class EpisodicMemoryStore(VectorMemoryStore):
    """Episodic memory — event-based with temporal context."""

    def store(self, entry: MemoryEntry) -> str:
        entry.memory_type = MemoryType.EPISODIC
        entry.decay_rate = 0.05
        return super().store(entry)

    def recall_sequence(
        self,
        namespace: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> list[dict[str, Any]]:
        entries = self.list_all(namespace=namespace)
        if start_time:
            entries = [e for e in entries if e.created_at >= start_time]
        if end_time:
            entries = [e for e in entries if e.created_at <= end_time]
        entries.sort(key=lambda e: e.created_at)
        return [e.to_dict() for e in entries]


class SemanticMemoryStore(VectorMemoryStore):
    """Semantic memory — facts and concepts."""

    def store(self, entry: MemoryEntry) -> str:
        entry.memory_type = MemoryType.SEMANTIC
        entry.decay_rate = 0.02
        return super().store(entry)

    def search_facts(
        self,
        query: str,
        namespace: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        return self.search(query, top_k=top_k, namespace=namespace, memory_type=MemoryType.SEMANTIC)
