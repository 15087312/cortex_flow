"""Schedule state — last-run bookkeeping for the interval scheduler.

Shares the database file with the other stores
(``$CORTEXFLOW_DB_PATH`` or ``<project_root>/data/cortexflow.db``).
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


def _default_db_path() -> Path:
    env = os.environ.get("CORTEXFLOW_DB_PATH")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "cortexflow.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule_state (
  workflow_id TEXT PRIMARY KEY,
  last_run TEXT,
  run_count INTEGER NOT NULL DEFAULT 0,
  last_status TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ScheduleState:
    """Persist last-run timestamps so schedules survive restarts."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else _default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def get(self, workflow_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT workflow_id, last_run, run_count, last_status "
                "FROM schedule_state WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if not row:
            return {"workflow_id": workflow_id, "last_run": None,
                    "run_count": 0, "last_status": ""}
        return dict(row)

    def record_run(self, workflow_id: str, status: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO schedule_state (workflow_id, last_run, run_count, "
                "last_status) VALUES (?, ?, 1, ?) "
                "ON CONFLICT(workflow_id) DO UPDATE SET "
                "last_run=excluded.last_run, "
                "run_count=run_count + 1, last_status=excluded.last_status",
                (workflow_id, _now(), status),
            )

    def clear(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM schedule_state")
