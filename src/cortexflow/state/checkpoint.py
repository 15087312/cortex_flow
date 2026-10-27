"""Checkpoint - Suspend and resume.

The persistent :class:`CheckpointStore` implementation lives in
:mod:`cortexflow.store.checkpoints` (SQLite); it is re-exported here so
existing imports keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cortexflow.runtime.states import FlowState, NodeState
from cortexflow.store.checkpoints import CheckpointStore

__all__ = ["Checkpoint", "CheckpointStore"]


@dataclass
class Checkpoint:
    """Execution checkpoint."""

    flow_id: str
    flow_state: FlowState
    node_states: dict[str, NodeState]
    variables: dict[str, Any]
    blackboard_snapshot: dict[str, Any]
    current_node: str | None
    pending_events: list[str]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    # Added for persistence: recompile IR on resume instead of pickling it.
    workflow_id: str = ""
    definition: dict[str, Any] = field(default_factory=dict)
