"""Metrics collector."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Metrics collector."""

    def __init__(self):
        self._node_durations: dict[str, list[float]] = defaultdict(list)
        self._flow_durations: list[float] = []
        self._node_counts: dict[str, int] = defaultdict(int)
        self._error_counts: dict[str, int] = defaultdict(int)

    def record_node_duration(self, node_type: str, duration: float) -> None:
        """Record node duration."""
        self._node_durations[node_type].append(duration)
        self._node_counts[node_type] += 1

    def record_flow_completion(self, duration: float) -> None:
        """Record flow completion."""
        self._flow_durations.append(duration)

    def record_error(self, node_type: str) -> None:
        """Record error."""
        self._error_counts[node_type] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get statistics."""
        stats = {
            "flows_completed": len(self._flow_durations),
            "avg_flow_duration": (
                sum(self._flow_durations) / len(self._flow_durations)
                if self._flow_durations
                else 0
            ),
            "node_counts": dict(self._node_counts),
            "error_counts": dict(self._error_counts),
            "avg_node_durations": {
                node_type: sum(durations) / len(durations)
                for node_type, durations in self._node_durations.items()
                if durations
            },
        }
        return stats
