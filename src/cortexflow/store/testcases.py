"""Test cases - Saved variable sets for one-click workflow replay.

Shares the database file with the other stores
(``$CORTEXFLOW_DB_PATH`` or ``<project_root>/data/cortexflow.db``).
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
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "cortexflow.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_testcases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id TEXT NOT NULL,
  name TEXT NOT NULL,
  variables TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_testcases_workflow
  ON workflow_testcases(workflow_id, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestCaseStore:
    """CRUD for per-workflow replayable variable sets."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else _default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def create(self, workflow_id: str, name: str,
               variables: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO workflow_testcases (workflow_id, name, variables, "
                "created_at) VALUES (?, ?, ?, ?)",
                (workflow_id, name,
                 json.dumps(variables or {}, ensure_ascii=False), _now()),
            )
            case_id = cur.lastrowid
            row = self._conn.execute(
                "SELECT id, workflow_id, name, variables, created_at "
                "FROM workflow_testcases WHERE id = ?",
                (case_id,),
            ).fetchone()
        return {
            "id": row["id"], "workflow_id": row["workflow_id"],
            "name": row["name"], "variables": json.loads(row["variables"]),
            "created_at": row["created_at"],
        }

    def list(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, workflow_id, name, variables, created_at "
                "FROM workflow_testcases WHERE workflow_id = ? ORDER BY id",
                (workflow_id,),
            ).fetchall()
        return [
            {"id": r["id"], "workflow_id": r["workflow_id"], "name": r["name"],
             "variables": json.loads(r["variables"]), "created_at": r["created_at"]}
            for r in rows
        ]

    def delete(self, workflow_id: str, case_id: int) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM workflow_testcases WHERE workflow_id = ? AND id = ?",
                (workflow_id, case_id),
            )
            return cur.rowcount > 0

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM workflow_testcases")
