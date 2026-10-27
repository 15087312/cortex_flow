"""Execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cortexflow.runtime.states import FlowState, NodeState
from cortexflow.state.blackboard import Blackboard

__all__ = ["ExecutionContext", "FlowState", "NodeState"]


@dataclass
class ExecutionContext:
    """Execution context carrying all runtime state and adapter references."""

    flow_id: str = ""
    state: FlowState = FlowState.PENDING
    node_states: dict[str, NodeState] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    current_node: str | None = None
    blackboard: Blackboard = field(default_factory=Blackboard)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Adapters (set by Engine)
    adapters: dict[str, Any] = field(default_factory=dict)

    # Services (set by Engine)
    event_bus: Any = None  # EventBus
    tracer: Any = None  # Tracer
    metrics: Any = None  # MetricsCollector

    # Executor reference for body dispatch (set by Executor)
    executor: Any = None

    def get_variable(self, path: str, default: Any = None) -> Any:
        """Get variable by dot-notation path with optional bracket indexing.

        Supports: var.field, var[0], var[index_var], var.field[0].sub
        """
        import re
        segments = path.split(".")
        value = self.variables
        for segment in segments:
            bracket_match = re.match(r'^([^\[]*)\[(.+)\]$', segment)
            if bracket_match:
                field_name, index_expr = bracket_match.group(1), bracket_match.group(2)
                if field_name:
                    if isinstance(value, dict):
                        value = value.get(field_name)
                    else:
                        return default
                    if value is None:
                        return default
                try:
                    idx = int(index_expr)
                except ValueError:
                    idx = self.variables.get(index_expr)
                    if idx is None:
                        return default
                if isinstance(value, (list, tuple)):
                    try:
                        value = value[idx]
                    except (IndexError, TypeError):
                        return default
                elif isinstance(value, dict):
                    value = value.get(idx)
                else:
                    return default
                if value is None:
                    return default
            else:
                if isinstance(value, dict):
                    value = value.get(segment)
                else:
                    return default
                if value is None:
                    return default
        return value

    def set_variable(self, path: str, value: Any) -> None:
        """Set variable by dot-notation path."""
        parts = path.split(".")
        if len(parts) == 1:
            self.variables[path] = value
        else:
            current = self.variables
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value

    def get_adapter(self, name: str) -> Any:
        """Get adapter by name."""
        return self.adapters.get(name)

    def clone(self) -> ExecutionContext:
        """Create a shallow clone for subflow/parallel execution."""
        return ExecutionContext(
            flow_id=self.flow_id,
            state=self.state,
            node_states=dict(self.node_states),
            variables=dict(self.variables),
            current_node=self.current_node,
            blackboard=self.blackboard,
            metadata=dict(self.metadata),
            adapters=self.adapters,
            event_bus=self.event_bus,
            tracer=self.tracer,
            metrics=self.metrics,
            executor=self.executor,
        )
