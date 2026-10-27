"""Variable scope - Hierarchical variable resolution."""

from __future__ import annotations

from typing import Any


class VariableScope:
    """Hierarchical variable scope."""

    def __init__(self):
        self.global_scope: dict[str, Any] = {}
        self.flow_scope: dict[str, Any] = {}
        self.subflow_scope: dict[str, Any] = {}
        self.node_scope: dict[str, Any] = {}

    def get(self, path: str) -> Any:
        """Get variable by path (node > subflow > flow > global)."""
        parts = path.split(".")

        # Try node scope
        value = self._resolve_from(self.node_scope, parts)
        if value is not None:
            return value

        # Try subflow scope
        value = self._resolve_from(self.subflow_scope, parts)
        if value is not None:
            return value

        # Try flow scope
        value = self._resolve_from(self.flow_scope, parts)
        if value is not None:
            return value

        # Try global scope
        return self._resolve_from(self.global_scope, parts)

    def set(self, path: str, value: Any, scope: str = "node") -> None:
        """Set variable in specified scope."""
        parts = path.split(".")
        target = self._get_scope(scope)
        self._set_nested(target, parts, value)

    def _get_scope(self, scope: str) -> dict[str, Any]:
        """Get scope dict."""
        if scope == "global":
            return self.global_scope
        elif scope == "flow":
            return self.flow_scope
        elif scope == "subflow":
            return self.subflow_scope
        else:
            return self.node_scope

    def _resolve_from(self, scope: dict[str, Any], parts: list[str]) -> Any:
        """Resolve path from scope."""
        current = scope
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _set_nested(self, target: dict[str, Any], parts: list[str], value: Any) -> None:
        """Set nested value."""
        current = target
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def clear_node_scope(self) -> None:
        """Clear node scope."""
        self.node_scope.clear()

    def clear_subflow_scope(self) -> None:
        """Clear subflow scope."""
        self.subflow_scope.clear()
