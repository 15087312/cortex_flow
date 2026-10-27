"""Document loaders for RAG system."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, ClassVar

from cortexflow.rag.document import Document

logger = logging.getLogger(__name__)


class TextLoader:
    """Load documents from raw text."""

    def load(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        return [Document(content=text, metadata=metadata or {"source": "text"})]


class FileLoader:
    """Load documents from files."""

    SUPPORTED_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {".txt", ".md", ".json", ".csv", ".yaml", ".yml"}
    )

    def load(
        self,
        path: str | Path,
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
    ) -> list[Document]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if path.is_dir():
            return self.load_directory(path, metadata, encoding)

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        content = path.read_text(encoding=encoding)
        meta = {
            "source": str(path),
            "filename": path.name,
            "extension": path.suffix,
            "size": path.stat().st_size,
            **(metadata or {}),
        }
        return [Document(content=content, metadata=meta)]

    def load_directory(
        self,
        directory: str | Path,
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
        recursive: bool = True,
    ) -> list[Document]:
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        documents = []
        pattern = "**/*" if recursive else "*"
        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                try:
                    docs = self.load(file_path, metadata, encoding)
                    documents.extend(docs)
                except Exception:
                    logger.warning("Skipping unreadable file %s", file_path, exc_info=True)

        return documents


class DirectoryLoader(FileLoader):
    """Alias for FileLoader with directory focus."""


class JSONLoader:
    """Load documents from JSON data."""

    def load(
        self,
        data: Any,
        content_key: str = "content",
        metadata_keys: list[str] | None = None,
    ) -> list[Document]:
        import json

        if isinstance(data, str):
            if os.path.isfile(data):
                with open(data, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.loads(data)

        documents = []
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            content = str(item.get(content_key, ""))
            if not content:
                continue

            meta = {"source": "json"}
            if metadata_keys:
                for key in metadata_keys:
                    if key in item:
                        meta[key] = item[key]
            else:
                meta = {k: v for k, v in item.items() if k != content_key and not isinstance(v, (dict, list))}
                meta["source"] = "json"

            documents.append(Document(content=content, metadata=meta))

        return documents


class CSVLoader:
    """Load documents from CSV data."""

    def load(
        self,
        path_or_text: str,
        content_column: str = "content",
        metadata_columns: list[str] | None = None,
    ) -> list[Document]:
        import csv
        import io

        if os.path.isfile(path_or_text):
            with open(path_or_text, encoding="utf-8") as f:
                text = f.read()
            source = path_or_text
        else:
            text = path_or_text
            source = "csv_text"

        reader = csv.DictReader(io.StringIO(text))
        documents = []

        for i, row in enumerate(reader):
            content = str(row.get(content_column, ""))
            if not content:
                content_parts = [f"{k}: {v}" for k, v in row.items() if v]
                content = "\n".join(content_parts)

            meta = {"source": source, "row_index": i}
            if metadata_columns:
                for col in metadata_columns:
                    if col in row:
                        meta[col] = row[col]
            else:
                for k, v in row.items():
                    if k != content_column:
                        meta[k] = v

            documents.append(Document(content=content, metadata=meta))

        return documents
