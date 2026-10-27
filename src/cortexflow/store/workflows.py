"""SQLite-backed workflow persistence with version history (Coze-style).

Workflows survive backend restarts. Every save snapshots a new version so
flows can be inspected and rolled back from the frontend history panel.

Database path: ``$CORTEXFLOW_DB_PATH`` or ``<project_root>/data/cortexflow.db``.
Tests point the env var at a temp file via ``tests/conftest.py``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _default_db_path() -> Path:
    env = os.environ.get("CORTEXFLOW_DB_PATH")
    if env:
        return Path(env)
    # src/cortexflow/store/workflows.py -> parents[3] == project root
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "cortexflow.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  definition TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'created',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  definition TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(workflow_id, version)
);
CREATE INDEX IF NOT EXISTS idx_versions_workflow
  ON workflow_versions(workflow_id, version);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStore:
    """Thread-safe SQLite store for workflows + version history."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else _default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + explicit lock: safe for uvicorn workers threads
        # and the httpx ASGI test transport.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    # ── workflows ──────────────────────────────────────────

    def clear(self) -> None:
        """Delete all workflows and versions (used by tests)."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM workflow_versions")
            self._conn.execute("DELETE FROM workflows")

    def exists(self, workflow_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            return row is not None

    def save(
        self, workflow_id: str, name: str, definition: dict[str, Any],
        message: str = "", status: str = "created",
    ) -> dict[str, Any]:
        """Upsert a workflow; every save appends a version snapshot."""
        now = _now()
        payload = json.dumps(definition, ensure_ascii=False)
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT id FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if existing:
                self._conn.execute(
                    "UPDATE workflows SET name = ?, definition = ?, "
                    "status = ?, updated_at = ? WHERE id = ?",
                    (name, payload, status, now, workflow_id),
                )
            else:
                self._conn.execute(
                    "INSERT INTO workflows (id, name, definition, status, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (workflow_id, name, payload, status, now, now),
                )
            row = self._conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM workflow_versions "
                "WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            version = (row[0] or 0) + 1
            self._conn.execute(
                "INSERT INTO workflow_versions "
                "(workflow_id, version, name, definition, message, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (workflow_id, version, name, payload,
                 message or ("created" if version == 1 else f"updated to v{version}"),
                 now),
            )
        return self.get(workflow_id) or {
            "id": workflow_id, "name": name, "definition": definition,
            "status": status, "created_at": now, "updated_at": now,
            "version": version,
        }

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, definition, status, created_at, updated_at "
                "FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if not row:
                return None
            vrow = self._conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM workflow_versions "
                "WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        return {
            "id": row["id"],
            "name": row["name"],
            "definition": json.loads(row["definition"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": vrow[0] if vrow else 0,
        }

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT w.id, w.name, w.definition, w.status, w.created_at, "
                "w.updated_at, COALESCE(MAX(v.version), 0) AS version "
                "FROM workflows w LEFT JOIN workflow_versions v "
                "ON v.workflow_id = w.id "
                "GROUP BY w.id ORDER BY w.updated_at DESC"
            ).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "definition": json.loads(r["definition"]),
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "version": r["version"],
            }
            for r in rows
        ]

    def delete(self, workflow_id: str) -> bool:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM workflow_versions WHERE workflow_id = ?",
                (workflow_id,),
            )
            cur = self._conn.execute(
                "DELETE FROM workflows WHERE id = ?", (workflow_id,)
            )
            return cur.rowcount > 0

    # ── versions ───────────────────────────────────────────

    def list_versions(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT version, name, message, created_at "
                "FROM workflow_versions WHERE workflow_id = ? "
                "ORDER BY version DESC",
                (workflow_id,),
            ).fetchall()
        return [
            {
                "version": r["version"],
                "name": r["name"],
                "message": r["message"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_version(self, workflow_id: str, version: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT version, name, definition, message, created_at "
                "FROM workflow_versions WHERE workflow_id = ? AND version = ?",
                (workflow_id, version),
            ).fetchone()
        if not row:
            return None
        return {
            "workflow_id": workflow_id,
            "version": row["version"],
            "name": row["name"],
            "definition": json.loads(row["definition"]),
            "message": row["message"],
            "created_at": row["created_at"],
        }

    def rollback(self, workflow_id: str, version: int) -> dict[str, Any] | None:
        """Restore a historical version as current (records a new version)."""
        snapshot = self.get_version(workflow_id, version)
        if not snapshot:
            return None
        current = self.get(workflow_id)
        if not current:
            return None
        return self.save(
            workflow_id, snapshot["name"], snapshot["definition"],
            message=f"rollback to v{version}",
            status=current.get("status", "created"),
        )
