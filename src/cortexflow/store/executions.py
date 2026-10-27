"""Execution history with trace snapshots — powers run history & replay."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cortexflow.store.common import default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id TEXT NOT NULL,
  status TEXT NOT NULL,
  variables TEXT NOT NULL DEFAULT '{}',
  result TEXT,
  error TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  traces TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_executions_workflow
  ON executions(workflow_id, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionStore:
    """Append-only run log with per-run IO snapshots."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def record(
        self,
        workflow_id: str,
        status: str,
        variables: dict[str, Any] | None = None,
        result: Any = None,
        error: str | None = None,
        traces: list[dict[str, Any]] | None = None,
        started_at: str | None = None,
    ) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO executions (workflow_id, status, variables, "
                "result, error, started_at, completed_at, traces) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    workflow_id, status,
                    json.dumps(variables or {}, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False, default=str)
                    if result is not None else None,
                    error,
                    started_at or _now(),
                    _now(),
                    json.dumps(traces or [], ensure_ascii=False, default=str),
                ),
            )
            return int(cur.lastrowid)

    def list(self, workflow_id: str | None = None,
             limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._lock:
            if workflow_id:
                rows = self._conn.execute(
                    "SELECT id, workflow_id, status, variables, result, error, "
                    "started_at, completed_at FROM executions "
                    "WHERE workflow_id = ? ORDER BY id DESC LIMIT ?",
                    (workflow_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, workflow_id, status, variables, result, error, "
                    "started_at, completed_at FROM executions "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r, with_traces=False) for r in rows]

    def get(self, run_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, workflow_id, status, variables, result, error, "
                "started_at, completed_at, traces FROM executions WHERE id = ?",
                (run_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM executions")

    def _row_to_dict(self, row, with_traces: bool = True) -> dict[str, Any]:
        out = {
            "id": row["id"],
            "workflow_id": row["workflow_id"],
            "status": row["status"],
            "variables": json.loads(row["variables"] or "{}"),
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
        }
        if with_traces:
            out["traces"] = json.loads(row["traces"] or "[]")
        return out