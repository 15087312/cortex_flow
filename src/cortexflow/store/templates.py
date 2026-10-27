"""Published workflow templates — the marketplace."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cortexflow.store.common import default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS marketplace_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',
  definition TEXT NOT NULL,
  author TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_marketplace_workflow
  ON marketplace_templates(workflow_id);
"""


class TemplateStore:
    """CRUD for marketplace templates."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def publish(
        self,
        workflow_id: str,
        name: str,
        description: str,
        definition: dict[str, Any],
        tags: list[str] | None = None,
        author: str = "",
    ) -> dict[str, Any]:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT version FROM marketplace_templates "
                "WHERE workflow_id = ? ORDER BY version DESC LIMIT 1",
                (workflow_id,),
            ).fetchone()
            version = (row["version"] if row else 0) + 1
            cur = self._conn.execute(
                "INSERT INTO marketplace_templates (workflow_id, name, "
                "description, tags, definition, author, version, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    workflow_id, name, description,
                    json.dumps(tags or [], ensure_ascii=False),
                    json.dumps(definition, ensure_ascii=False),
                    author, version,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            tid = cur.lastrowid
        return {"id": tid, "workflow_id": workflow_id, "name": name,
                "description": description, "tags": tags or [],
                "author": author, "version": version}

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, workflow_id, name, description, tags, author, "
                "version, created_at FROM marketplace_templates "
                "ORDER BY id DESC"
            ).fetchall()
        return [
            {"id": r["id"], "workflow_id": r["workflow_id"], "name": r["name"],
             "description": r["description"],
             "tags": json.loads(r["tags"] or "[]"), "author": r["author"],
             "version": r["version"], "created_at": r["created_at"]}
            for r in rows
        ]

    def get(self, template_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, workflow_id, name, description, tags, author, "
                "version, created_at, definition FROM marketplace_templates "
                "WHERE id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "workflow_id": row["workflow_id"],
            "name": row["name"], "description": row["description"],
            "tags": json.loads(row["tags"] or "[]"), "author": row["author"],
            "version": row["version"], "created_at": row["created_at"],
            "definition": json.loads(row["definition"]),
        }

    def delete(self, template_id: int) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM marketplace_templates WHERE id = ?", (template_id,)
            )
            return cur.rowcount > 0

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM marketplace_templates")