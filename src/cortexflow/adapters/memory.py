"""Memory adapter - Vector-based memory with embedding similarity."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import numpy as np

from cortexflow.adapters.base import MemoryAdapter

logger = logging.getLogger(__name__)


def _simple_embed(text: str, dim: int = 128) -> list[float]:
    """Simple hash-based embedding for local use without external API."""
    tokens = re.findall(r'\w+', text.lower())
    vec = np.zeros(dim, dtype=np.float32)
    for i, token in enumerate(tokens):
        h = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign * (1.0 / (1.0 + 0.1 * i))
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


class MemoryEntry:
    """A single memory entry with vector embedding."""

    def __init__(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.content = content
        self.metadata = metadata or {}
        self.embedding = _simple_embed(content)
        self.id = hashlib.sha256(content.encode()).hexdigest()[:16]


class VectorMemoryAdapter(MemoryAdapter):
    """In-memory vector store for long-term memory."""

    def __init__(self, dim: int = 128, top_k: int = 5) -> None:
        self._dim = dim
        self._top_k = top_k
        self._entries: list[MemoryEntry] = []
        self._namespaces: dict[str, list[MemoryEntry]] = {}

    async def query(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        top_k = kwargs.get("top_k", self._top_k)
        namespace = kwargs.get("namespace")
        min_score = kwargs.get("min_score", 0.0)

        entries = self._namespaces.get(namespace, self._entries) if namespace else self._entries
        if not entries:
            return []

        q_vec = np.array(_simple_embed(query, self._dim), dtype=np.float32)
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in entries:
            e_vec = np.array(entry.embedding, dtype=np.float32)
            score = float(np.dot(q_vec, e_vec))
            if score >= min_score:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": entry.content,
                "score": score,
                "metadata": entry.metadata,
                "id": entry.id,
            }
            for score, entry in scored[:top_k]
        ]

    async def store(self, content: str, **kwargs: Any) -> None:
        metadata = kwargs.get("metadata", {})
        namespace = kwargs.get("namespace")
        entry = MemoryEntry(content, metadata)

        if namespace:
            if namespace not in self._namespaces:
                self._namespaces[namespace] = []
            self._namespaces[namespace].append(entry)
        else:
            self._entries.append(entry)

    async def delete(self, entry_id: str, namespace: str | None = None) -> bool:
        if namespace:
            entries = self._namespaces.get(namespace, [])
            before = len(entries)
            self._namespaces[namespace] = [e for e in entries if e.id != entry_id]
            return len(self._namespaces[namespace]) < before
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        return len(self._entries) < before

    async def list_all(self, namespace: str | None = None) -> list[dict[str, Any]]:
        entries = self._namespaces.get(namespace, self._entries) if namespace else self._entries
        return [
            {"id": e.id, "content": e.content, "metadata": e.metadata}
            for e in entries
        ]

    async def count(self, namespace: str | None = None) -> int:
        if namespace:
            return len(self._namespaces.get(namespace, []))
        return len(self._entries)

    async def clear(self, namespace: str | None = None) -> None:
        if namespace:
            self._namespaces.pop(namespace, None)
        else:
            self._entries.clear()
            self._namespaces.clear()
