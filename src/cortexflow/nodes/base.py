"""Base node class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from cortexflow.runtime.context import ExecutionContext
from cortexflow.utils.resolver import resolve_value


class BaseNode(ABC):
    """Base class for all nodes."""

    def __init__(self, node_id: str, config: dict[str, Any]):
        self.node_id = node_id
        self.config = config

    @abstractmethod
    async def execute(self, context: ExecutionContext) -> Any:
        """Execute node logic."""
        pass

    def validate_config(self) -> None:
        """Validate node configuration."""
        pass

    def get_dependencies(self) -> list[str]:
        """Get variable dependencies."""
        return []

    def resolve(self, data: Any, context: ExecutionContext) -> Any:
        """Resolve variable references using context."""
        return resolve_value(data, context.get_variable)
