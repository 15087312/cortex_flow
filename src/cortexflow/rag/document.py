"""Document model for RAG system."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """A document with content and metadata."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.doc_id:
            self.doc_id = hashlib.sha256(self.content.encode()).hexdigest()[:16]

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def word_count(self) -> int:
        import re
        return len(re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]+', self.content))

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata,
            "char_count": self.char_count,
            "word_count": self.word_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        return cls(
            content=data["content"],
            metadata=data.get("metadata", {}),
            doc_id=data.get("doc_id", ""),
        )


@dataclass
class Chunk:
    """A chunk of a document."""

    content: str
    doc_id: str
    chunk_id: str = ""
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chunk_id:
            self.chunk_id = f"{self.doc_id}_chunk_{self.chunk_index}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "metadata": self.metadata,
        }
