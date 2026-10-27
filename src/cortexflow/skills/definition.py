"""Skill definition model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


SkillHandler = Callable[..., Awaitable[Any]]


@dataclass
class SkillDefinition:
    """Definition of a reusable skill."""

    id: str
    name: str
    description: str
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    _handler: SkillHandler | None = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)
    _loader: Callable[[], Awaitable[SkillHandler]] | None = field(default=None, repr=False)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    async def load(self) -> SkillHandler:
        if self._handler is not None:
            return self._handler
        if self._loader is not None:
            self._handler = await self._loader()
            self._loaded = True
            return self._handler
        raise RuntimeError(f"Skill '{self.id}' has no handler or loader")

    def unload(self) -> None:
        self._handler = None
        self._loaded = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "triggers": self.triggers,
            "parameters": self.parameters,
            "loaded": self._loaded,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillDefinition:
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            triggers=data.get("triggers", []),
            parameters=data.get("parameters", {}),
            metadata=data.get("metadata", {}),
        )
