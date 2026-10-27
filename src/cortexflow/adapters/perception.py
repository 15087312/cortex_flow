"""Perception adapter - Interface with perception system."""

from __future__ import annotations

from typing import Any

from cortexflow.adapters.base import PerceptionAdapter


class DefaultPerceptionAdapter(PerceptionAdapter):
    """Default perception adapter (mock implementation)."""

    async def collect(self, source: str, config: dict[str, Any]) -> dict[str, Any]:
        """Collect perception data."""
        # TODO: Integrate with actual perception system
        return {
            "source": source,
            "config": config,
            "data": f"Mock perception data from {source}",
        }
