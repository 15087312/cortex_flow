"""SQLite-backed checkpoint store — suspended flows survive restarts.

Shares the database file with :mod:`cortexflow.store.workflows`
(``$CORTEXFLOW_DB_PATH`` or ``<project_root>/data/cortexflow.db``).

Only JSON-safe resume state is persisted: variables, node states,
blackboard snapshot, current node, wait/ask configs and the workflow
definition (used to recompile the IR on resume — the in-memory IR object
itself is deliberately *not* pickled).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cortexflow.state.checkpoint import Checkpoint


def _default_db_path() -> Path:
    env = os.environ.get("CORTEXFLOW_DB_PATH")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "cortexflow.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
  flow_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL DEFAULT '',
  definition TEXT NOT NULL DEFAULT '{}',
  variables TEXT NOT NULL DEFAULT '{}',
  node_states TEXT NOT NULL DEFAULT '{}',
  blackboard TEXT NOT NULL DEFAULT '{}',
  current_node TEXT,
  wait_configs TEXT NOT NULL DEFAULT '{}',
  pending_events TEXT NOT NULL DEFAULT '[]',
  flow_state TEXT NOT NULL DEFAULT '',
  created_at TEXT
);
"""


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class CheckpointStore:
    """Persistent store for suspended-flow checkpoints (async API)."""

    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if path else _default_db_path()
        self._lock = threading.Lock()
        if str(self._path) != ":memory:":
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    async def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint (upsert by flow_id)."""
        metadata = checkpoint.metadata or {}
        wait_configs = {
            k: v for k, v in metadata.items()
            if k.startswith(("_wait_config_", "_ask_"))
        }
        node_states = {}
        for node_id, state in (checkpoint.node_states or {}).items():
            node_states[node_id] = getattr(state, "value", state)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO checkpoints (flow_id, workflow_id, definition, "
                "variables, node_states, blackboard, current_node, "
                "wait_configs, pending_events, flow_state, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(flow_id) DO UPDATE SET "
                "workflow_id=excluded.workflow_id, definition=excluded.definition, "
                "variables=excluded.variables, node_states=excluded.node_states, "
                "blackboard=excluded.blackboard, current_node=excluded.current_node, "
                "wait_configs=excluded.wait_configs, "
                "pending_events=excluded.pending_events, "
                "flow_state=excluded.flow_state, created_at=excluded.created_at",
                (
                    checkpoint.flow_id,
                    getattr(checkpoint, "workflow_id", "") or "",
                    _dumps(getattr(checkpoint, "definition", {}) or {}),
                    _dumps(checkpoint.variables or {}),
                    _dumps(node_states),
                    _dumps(checkpoint.blackboard_snapshot or {}),
                    checkpoint.current_node,
                    _dumps(wait_configs),
                    _dumps(checkpoint.pending_events or []),
                    getattr(checkpoint.flow_state, "value", checkpoint.flow_state),
                    str(checkpoint.created_at) if checkpoint.created_at else None,
                ),
            )

    async def load(self, flow_id: str) -> Checkpoint | None:
        """Load a checkpoint."""
        from cortexflow.state.checkpoint import Checkpoint

        with self._lock:
            row = self._conn.execute(
                "SELECT flow_id, workflow_id, definition, variables, "
                "node_states, blackboard, current_node, wait_configs, "
                "pending_events, flow_state, created_at "
                "FROM checkpoints WHERE flow_id = ?",
                (flow_id,),
            ).fetchone()
        if not row:
            return None
        metadata = json.loads(row["wait_configs"] or "{}")
        return Checkpoint(
            flow_id=row["flow_id"],
            workflow_id=row["workflow_id"] or "",
            definition=json.loads(row["definition"] or "{}"),
            flow_state=row["flow_state"] or "",
            node_states=json.loads(row["node_states"] or "{}"),
            variables=json.loads(row["variables"] or "{}"),
            blackboard_snapshot=json.loads(row["blackboard"] or "{}"),
            current_node=row["current_node"],
            pending_events=json.loads(row["pending_events"] or "[]"),
            created_at=row["created_at"],
            metadata=metadata,
        )

    async def delete(self, flow_id: str) -> None:
        """Delete a checkpoint."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM checkpoints WHERE flow_id = ?", (flow_id,))

    async def list(self) -> list[str]:
        """List checkpoint IDs."""
        with self._lock:
            rows = self._conn.execute("SELECT flow_id FROM checkpoints").fetchall()
        return [r["flow_id"] for r in rows]

    async def clear(self) -> None:
        """Delete all checkpoints (used by tests)."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM checkpoints")
