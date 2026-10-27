"""RAG pipeline for document retrieval and generation."""

from __future__ import annotations

from typing import Any

from cortexflow.rag.document import Document, Chunk
from cortexflow.rag.loader import TextLoader, FileLoader
from cortexflow.rag.splitter import TextSplitter, RecursiveTextSplitter


class DocumentStore:
    """In-memory document store with vector search."""

    def __init__(self, dim: int = 128) -> None:
        self._dim = dim
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, Chunk] = {}
        self._embeddings: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float]:
        import hashlib
        import math

        vec = [0.0] * self._dim
        tokens = text.lower().split()

        for i, token in enumerate(tokens):
            h = hashlib.md5(token.encode()).hexdigest()
            for j in range(0, min(len(h), self._dim * 2), 2):
                idx = int(h[j:j+2], 16) % self._dim
                weight = 1.0 / (1.0 + 0.1 * i)
                vec[idx] += weight

        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def add_document(self, doc: Document) -> None:
        self._documents[doc.doc_id] = doc
        self._embeddings[doc.doc_id] = self._embed(doc.content)

    def add_chunk(self, chunk: Chunk) -> None:
        self._chunks[chunk.chunk_id] = chunk
        self._embeddings[chunk.chunk_id] = self._embed(chunk.content)

    def add_chunks(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self.add_chunk(chunk)

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        filter_doc_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        import math

        query_vec = self._embed(query)

        scores = []
        for emb_id, emb_vec in self._embeddings.items():
            if filter_doc_ids:
                doc_id = emb_id.split("_chunk_")[0] if "_chunk_" in emb_id else emb_id
                if doc_id not in filter_doc_ids:
                    continue

            score = sum(a * b for a, b in zip(query_vec, emb_vec))
            if score >= min_score:
                scores.append((emb_id, score))

        scores.sort(key=lambda x: -x[1])
        results = []

        for emb_id, score in scores[:top_k]:
            if emb_id in self._chunks:
                chunk = self._chunks[emb_id]
                results.append({
                    "type": "chunk",
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "content": chunk.content,
                    "score": score,
                    "metadata": chunk.metadata,
                })
            elif emb_id in self._documents:
                doc = self._documents[emb_id]
                results.append({
                    "type": "document",
                    "doc_id": doc.doc_id,
                    "content": doc.content,
                    "score": score,
                    "metadata": doc.metadata,
                })

        return results

    def get_document(self, doc_id: str) -> Document | None:
        return self._documents.get(doc_id)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    def list_documents(self) -> list[dict[str, Any]]:
        return [doc.to_dict() for doc in self._documents.values()]

    def list_chunks(self, doc_id: str | None = None) -> list[dict[str, Any]]:
        chunks = self._chunks.values()
        if doc_id:
            chunks = [c for c in chunks if c.doc_id == doc_id]
        return [c.to_dict() for c in chunks]

    def delete_document(self, doc_id: str) -> bool:
        if doc_id not in self._documents:
            return False

        del self._documents[doc_id]
        self._embeddings.pop(doc_id, None)

        chunk_ids = [cid for cid in self._chunks if cid.startswith(f"{doc_id}_chunk_")]
        for cid in chunk_ids:
            del self._chunks[cid]
            self._embeddings.pop(cid, None)

        return True

    def clear(self) -> None:
        self._documents.clear()
        self._chunks.clear()
        self._embeddings.clear()

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


class RAGPipeline:
    """Complete RAG pipeline: load -> split -> index -> retrieve."""

    def __init__(
        self,
        store: DocumentStore | None = None,
        splitter: TextSplitter | RecursiveTextSplitter | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self.store = store or DocumentStore()
        self.splitter = splitter or RecursiveTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self._text_loader = TextLoader()
        self._file_loader = FileLoader()

    def ingest_text(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        split: bool = True,
    ) -> dict[str, Any]:
        docs = self._text_loader.load(text, metadata)
        self.store.add_document(docs[0])

        chunk_count = 0
        if split:
            chunks = self.splitter.split_documents(docs)
            self.store.add_chunks(chunks)
            chunk_count = len(chunks)

        return {
            "doc_id": docs[0].doc_id,
            "char_count": docs[0].char_count,
            "chunk_count": chunk_count,
        }

    def ingest_file(
        self,
        path: str,
        metadata: dict[str, Any] | None = None,
        split: bool = True,
    ) -> dict[str, Any]:
        docs = self._file_loader.load(path, metadata)
        results = []

        for doc in docs:
            self.store.add_document(doc)
            chunk_count = 0
            if split:
                chunks = self.splitter.split_documents([doc])
                self.store.add_chunks(chunks)
                chunk_count = len(chunks)
            results.append({
                "doc_id": doc.doc_id,
                "source": doc.metadata.get("source", ""),
                "chunk_count": chunk_count,
            })

        return {"documents": results, "total": len(results)}

    def ingest_directory(
        self,
        path: str,
        metadata: dict[str, Any] | None = None,
        split: bool = True,
    ) -> dict[str, Any]:
        docs = self._file_loader.load_directory(path, metadata)
        total_chunks = 0

        for doc in docs:
            self.store.add_document(doc)
            if split:
                chunks = self.splitter.split_documents([doc])
                self.store.add_chunks(chunks)
                total_chunks += len(chunks)

        return {
            "documents_loaded": len(docs),
            "chunks_created": total_chunks,
        }

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        return self.store.search(query, top_k=top_k, min_score=min_score)

    def retrieve_and_format(
        self,
        query: str,
        top_k: int = 5,
        template: str = "Context:\n{context}\n\nQuery: {query}",
    ) -> str:
        results = self.retrieve(query, top_k=top_k)
        context = "\n\n---\n\n".join(r["content"] for r in results)
        return template.format(context=context, query=query)

    def get_stats(self) -> dict[str, Any]:
        return {
            "document_count": self.store.document_count,
            "chunk_count": self.store.chunk_count,
        }
