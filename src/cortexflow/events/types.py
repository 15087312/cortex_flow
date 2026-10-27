"""Event types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Event:
    """Event."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class EventType:
    """Built-in event types."""

    # Node events
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"

    # Flow events
    FLOW_STARTED = "flow.started"
    FLOW_COMPLETED = "flow.completed"
    FLOW_FAILED = "flow.failed"
    FLOW_SUSPENDED = "flow.suspended"
    FLOW_RESUMED = "flow.resumed"

    # External events
    USER_INPUT = "external.user_input"
    APPROVAL_GRANTED = "external.approval_granted"
    APPROVAL_DENIED = "external.approval_denied"
    PERCEPTION_TRIGGER = "external.perception_trigger"
