"""Text splitters for RAG system."""

from __future__ import annotations

import re
from typing import Any

from cortexflow.rag.document import Document, Chunk


class TextSplitter:
    """Split text into chunks with configurable size and overlap."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separator: str = "\n",
        length_function: Any = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
        self._length = length_function or len

    def split_text(self, text: str) -> list[str]:
        if self._length(text) <= self.chunk_size:
            return [text]

        if self.separator == "sentence":
            splits = re.split(r'(?<=[.!?。！？])\s*', text)
        elif self.separator == "paragraph":
            splits = text.split("\n\n")
        elif self.separator == "char":
            splits = list(text)
        else:
            splits = text.split(self.separator)

        splits = [s for s in splits if s.strip()]

        chunks = []
        current = ""

        for split in splits:
            if self._length(current) + self._length(split) > self.chunk_size and current:
                chunks.append(current.strip())
                if self.chunk_overlap > 0:
                    words = current.split()
                    overlap_count = max(1, len(words) // 5)
                    current = " ".join(words[-overlap_count:]) + " " + split
                else:
                    current = split
            else:
                current = current + self.separator + split if current else split

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def split_documents(self, documents: list[Document]) -> list[Chunk]:
        chunks = []
        for doc in documents:
            text_chunks = self.split_text(doc.content)
            for i, chunk_text in enumerate(text_chunks):
                chunks.append(Chunk(
                    content=chunk_text,
                    doc_id=doc.doc_id,
                    chunk_index=i,
                    metadata={**doc.metadata, "chunk_index": i, "total_chunks": len(text_chunks)},
                ))
        return chunks


class RecursiveTextSplitter:
    """Recursively split text using multiple separators."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", ". ", " ", ""]

    def split_text(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if not separators:
            return [text]

        separator = separators[0]
        remaining_seps = separators[1:]

        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        splits = [s for s in splits if s.strip()]

        chunks = []
        for split in splits:
            if len(split) <= self.chunk_size:
                chunks.append(split)
            elif remaining_seps:
                sub_chunks = self._split_recursive(split, remaining_seps)
                chunks.extend(sub_chunks)
            else:
                for i in range(0, len(split), self.chunk_size - self.chunk_overlap):
                    chunks.append(split[i:i + self.chunk_size])

        return self._merge_with_overlap(chunks)

    def _merge_with_overlap(self, chunks: list[str]) -> list[str]:
        if not chunks:
            return []

        merged = []
        current = chunks[0]

        for i in range(1, len(chunks)):
            if len(current) + len(chunks[i]) + 1 <= self.chunk_size:
                current = current + " " + chunks[i]
            else:
                merged.append(current)
                if self.chunk_overlap > 0:
                    words = current.split()
                    overlap_count = max(1, len(words) // 5)
                    current = " ".join(words[-overlap_count:]) + " " + chunks[i]
                else:
                    current = chunks[i]

        if current:
            merged.append(current)

        return merged

    def split_documents(self, documents: list[Document]) -> list[Chunk]:
        chunks = []
        for doc in documents:
            text_chunks = self.split_text(doc.content)
            for i, chunk_text in enumerate(text_chunks):
                chunks.append(Chunk(
                    content=chunk_text,
                    doc_id=doc.doc_id,
                    chunk_index=i,
                    metadata={**doc.metadata, "chunk_index": i, "total_chunks": len(text_chunks)},
                ))
        return chunks


class SemanticSplitter:
    """Split text based on semantic boundaries (sentence/topic changes)."""

    def __init__(
        self,
        max_chunk_size: int = 500,
        min_chunk_size: int = 100,
    ) -> None:
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def split_text(self, text: str) -> list[str]:
        sentences = re.split(r'(?<=[.!?。！？\n])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) > self.max_chunk_size and current:
                if len(current) >= self.min_chunk_size:
                    chunks.append(current.strip())
                    current = sentence
                else:
                    current = current + " " + sentence
            else:
                current = current + " " + sentence if current else sentence

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def split_documents(self, documents: list[Document]) -> list[Chunk]:
        chunks = []
        for doc in documents:
            text_chunks = self.split_text(doc.content)
            for i, chunk_text in enumerate(text_chunks):
                chunks.append(Chunk(
                    content=chunk_text,
                    doc_id=doc.doc_id,
                    chunk_index=i,
                    metadata={**doc.metadata, "chunk_index": i, "total_chunks": len(text_chunks)},
                ))
        return chunks
