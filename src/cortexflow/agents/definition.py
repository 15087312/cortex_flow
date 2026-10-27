"""Agent definition - describes an AI agent's identity and capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentDefinition:
    """Defines an AI agent's identity, role, and capabilities."""

    id: str
    name: str
    role: str = "assistant"
    description: str = ""
    system_prompt: str = ""
    tier: str = "default"
    provider: str = ""
    model: str = ""
    tools: list[str] = field(default_factory=list)
    memory_namespace: str = ""
    max_history: int = 20
    temperature: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tier": self.tier,
            "provider": self.provider,
            "model": self.model,
            "tools": self.tools,
            "memory_namespace": self.memory_namespace,
            "max_history": self.max_history,
            "temperature": self.temperature,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
