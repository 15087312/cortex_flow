"""Memory types and data structures."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """Types of memory."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"


class MemoryImportance(str, Enum):
    """Memory importance levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryEntry:
    """A single memory entry."""

    content: str
    memory_type: MemoryType
    importance: MemoryImportance = MemoryImportance.MEDIUM
    metadata: dict[str, Any] = field(default_factory=dict)
    memory_id: str = field(default="")
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    decay_rate: float = 0.1
    strength: float = 1.0
    namespace: str = "default"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.memory_id:
            hash_input = f"{self.content}{self.created_at}{self.namespace}"
            self.memory_id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def access(self) -> None:
        """Record an access to this memory."""
        self.last_accessed = time.time()
        self.access_count += 1
        self.strength = min(1.0, self.strength + 0.05)

    def apply_decay(self, current_time: float | None = None) -> None:
        """Apply memory decay based on time."""
        current_time = current_time or time.time()
        time_elapsed = current_time - self.last_accessed
        decay_factor = 1.0 / (1.0 + self.decay_rate * time_elapsed / 3600)
        self.strength *= decay_factor

    def should_consolidate(self, threshold: float = 0.6) -> bool:
        """Check if memory should be consolidated to long-term."""
        return (
            self.memory_type == MemoryType.SHORT_TERM
            and self.access_count >= 3
            and self.strength >= threshold
        )

    def should_forget(self, threshold: float = 0.1) -> bool:
        """Check if memory should be forgotten."""
        return self.strength < threshold and self.importance != MemoryImportance.CRITICAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "strength": self.strength,
            "namespace": self.namespace,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            importance=MemoryImportance(data.get("importance", "medium")),
            metadata=data.get("metadata", {}),
            memory_id=data.get("memory_id", ""),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0),
            decay_rate=data.get("decay_rate", 0.1),
            strength=data.get("strength", 1.0),
            namespace=data.get("namespace", "default"),
            tags=data.get("tags", []),
        )
