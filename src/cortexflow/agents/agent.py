"""Agent - an AI agent with conversation history and memory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from cortexflow.agents.definition import AgentDefinition


@dataclass
class Message:
    """A single message in agent conversation history."""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp, "metadata": self.metadata}


class Agent:
    """An AI agent with identity, conversation history, and memory access."""

    def __init__(self, definition: AgentDefinition):
        self.definition = definition
        self._history: list[Message] = []
        self._shared_state: dict[str, Any] = {}

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def role(self) -> str:
        return self.definition.role

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> None:
        msg = Message(role=role, content=content, metadata=metadata or {})
        self._history.append(msg)
        if len(self._history) > self.definition.max_history:
            self._history = self._history[-self.definition.max_history:]

    def get_conversation_messages(self, user_message: str) -> list[dict[str, str]]:
        messages = []
        if self.definition.system_prompt:
            messages.append({"role": "system", "content": self.definition.system_prompt})
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_message})
        return messages

    def record_response(self, content: str) -> None:
        self.add_message("assistant", content)

    def record_user_message(self, content: str) -> None:
        self.add_message("user", content)

    def set_shared(self, key: str, value: Any) -> None:
        self._shared_state[key] = value

    def get_shared(self, key: str, default: Any = None) -> Any:
        return self._shared_state.get(key, default)

    def clear_history(self) -> None:
        self._history.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "history": [m.to_dict() for m in self._history],
            "shared_state": dict(self._shared_state),
        }
