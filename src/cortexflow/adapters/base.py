"""Adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ModelRuntimeAdapter(ABC):
    """Model runtime adapter interface."""

    @abstractmethod
    async def invoke(
        self,
        tier: str,
        identity: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Invoke model."""
        pass


class ToolRuntimeAdapter(ABC):
    """Tool runtime adapter interface."""

    @abstractmethod
    async def invoke(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Invoke tool."""
        pass


class PromptComposerAdapter(ABC):
    """Prompt composer adapter interface."""

    @abstractmethod
    def build_system(self, context: dict[str, Any]) -> str:
        """Build system prompt."""
        pass


class PerceptionAdapter(ABC):
    """Perception adapter interface."""

    @abstractmethod
    async def collect(self, source: str, config: dict[str, Any]) -> dict[str, Any]:
        """Collect perception data."""
        pass


class MemoryAdapter(ABC):
    """Memory adapter interface."""

    @abstractmethod
    async def query(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Query memory."""
        pass

    @abstractmethod
    async def store(self, content: str, **kwargs: Any) -> None:
        """Store in memory."""
        pass
