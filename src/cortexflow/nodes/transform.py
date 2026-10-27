"""Data Transformation node - Transform and map data structures."""

from __future__ import annotations

import json
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry


@NodeRegistry.register("transform")
class TransformNode(BaseNode):
    """Transform data using mapping expressions."""

    async def execute(self, context: Any) -> Any:
        input_data = self.resolve(self.config.get("input", "${_last_result}"), context)
        mapping = self.config.get("mapping", {})
        output_format = self.config.get("output_format", "dict")

        if not mapping:
            return input_data

        result = self._apply_mapping(input_data, mapping, context)

        if output_format == "json":
            return json.dumps(result, ensure_ascii=False, indent=2)
        elif output_format == "string":
            return str(result)
        else:
            return result

    def _apply_mapping(self, data: Any, mapping: dict, context: Any) -> dict:
        """Apply mapping rules to transform data."""
        result = {}

        for target_path, source_expr in mapping.items():
            value = self._extract_value(data, source_expr, context)
            self._set_nested_value(result, target_path, value)

        return result

    def _extract_value(self, data: Any, expr: Any, context: Any) -> Any:
        """Extract value from data using expression."""
        if isinstance(expr, str):
            if expr.startswith("${") and expr.endswith("}"):
                return self.resolve(expr, context)
            elif expr.startswith("$."):
                return self._jsonpath_extract(data, expr)
            elif "{{" in expr:
                return self._template_eval(expr, data, context)
            else:
                return expr
        elif isinstance(expr, dict):
            return {k: self._extract_value(data, v, context) for k, v in expr.items()}
        elif isinstance(expr, list):
            return [self._extract_value(data, item, context) for item in expr]
        else:
            return expr

    def _jsonpath_extract(self, data: Any, path: str) -> Any:
        """Simple JSONPath-like extraction (e.g., $.user.name)."""
        parts = path.replace("$.", "").split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None

            if current is None:
                return None

        return current

    def _template_eval(self, template: str, data: Any, context: Any) -> str:
        """Evaluate template expressions like {{user.name}}."""
        import re

        def replace_var(match):
            var_path = match.group(1).strip()
            value = self._jsonpath_extract(data, f"$.{var_path}")
            if value is None:
                value = context.get_variable(var_path)
            return str(value) if value is not None else ""

        return re.sub(r"\{\{([^}]+)\}\}", replace_var, template)

    def _set_nested_value(self, obj: dict, path: str, value: Any) -> None:
        """Set a value in a nested dictionary using dot notation."""
        parts = path.split(".")
        current = obj

        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value
