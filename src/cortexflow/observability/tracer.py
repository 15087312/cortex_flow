"""Execution tracer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class NodeTrace:
    """Node execution trace."""

    node_id: str
    node_type: str
    started_at: datetime
    completed_at: datetime | None = None
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    state: str = "pending"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tracer:
    """Execution tracer."""

    def __init__(self):
        self._traces: dict[str, list[NodeTrace]] = {}

    async def trace_node(
        self,
        flow_id: str,
        node_id: str,
        node_type: str,
        **kwargs: Any,
    ) -> NodeTrace:
        """Start tracing a node."""
        trace = NodeTrace(
            node_id=node_id,
            node_type=node_type,
            started_at=datetime.now(UTC),
            **kwargs,
        )
        if flow_id not in self._traces:
            self._traces[flow_id] = []
        self._traces[flow_id].append(trace)
        return trace

    async def complete_trace(
        self,
        flow_id: str,
        node_id: str,
        output_summary: dict[str, Any] | None = None,
        input_summary: dict[str, Any] | None = None,
        state: str = "completed",
        error: str | None = None,
    ) -> None:
        """Complete a trace."""
        if flow_id in self._traces:
            for trace in reversed(self._traces[flow_id]):
                if trace.node_id == node_id and trace.completed_at is None:
                    trace.completed_at = datetime.now(UTC)
                    if output_summary is not None:
                        trace.output_summary = output_summary
                    if input_summary is not None:
                        trace.input_summary = input_summary
                    trace.state = state
                    trace.error = error
                    break

    async def get_trace(self, flow_id: str) -> list[NodeTrace]:
        """Get trace for flow."""
        return self._traces.get(flow_id, [])
