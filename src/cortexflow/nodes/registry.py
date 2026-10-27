"""Node registry."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode


class NodeRegistry:
    """Registry for node types."""

    _registry: dict[str, type[BaseNode]] = {}

    @classmethod
    def register(cls, node_type: str):
        """Register node type."""

        def decorator(node_class: type[BaseNode]):
            cls._registry[node_type] = node_class
            return node_class

        return decorator

    @classmethod
    def create(cls, node_type: str, node_id: str, config: dict[str, Any]) -> BaseNode:
        """Create node instance."""
        node_class = cls._registry.get(node_type)
        if not node_class:
            raise ValueError(f"Unknown node type: {node_type}")
        return node_class(node_id, config)

    @classmethod
    def list_types(cls) -> list[str]:
        """List registered node types."""
        return list(cls._registry.keys())
