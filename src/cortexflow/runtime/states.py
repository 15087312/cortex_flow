"""Flow and node state enums."""

from __future__ import annotations

from enum import Enum


class FlowState(str, Enum):
    """Flow execution state."""

    PENDING = "pending"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeState(str, Enum):
    """Node execution state."""

    PENDING = "pending"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
