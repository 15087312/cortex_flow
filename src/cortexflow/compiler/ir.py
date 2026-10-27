"""Intermediate representation for compiled workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VariableIR:
    """Variable in IR."""

    name: str
    type: str
    required: bool
    default: Any
    enum: list[Any] | None


@dataclass
class TierIR:
    """Tier in IR."""

    name: str
    description: str | None
    model: str | None
    provider: str | None
    max_concurrency: int
    timeout: int | None
    tools: list[str] | None
    parent: str | None
    metadata: dict[str, Any]


@dataclass
class NodeIR:
    """Node in IR."""

    id: str
    type: str
    config: dict[str, Any]
    on_success: str | None
    on_error: str | None
    resolved_tier: str
    resolved_identity: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class EdgeIR:
    """Edge in IR."""

    from_node: str
    to_node: str
    condition: str | None
    priority: int


@dataclass
class BlackboardConfigIR:
    """Blackboard config in IR."""

    enabled: bool
    visibility: dict[str, str]


@dataclass
class FlowIR:
    """Compiled workflow IR."""

    id: str
    name: str
    entry: str
    nodes: dict[str, NodeIR]
    edges: dict[str, list[EdgeIR]]
    variables: dict[str, VariableIR]
    blackboard_config: BlackboardConfigIR
    tiers: dict[str, TierIR]
    metadata: dict[str, Any]
