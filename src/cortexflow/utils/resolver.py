"""Shared variable resolution utilities."""

from __future__ import annotations

import re
from typing import Any


def resolve_value(data: Any, get_variable: callable) -> Any:
    """Resolve variable references in data structures.

    Args:
        data: Data to resolve (strings with ${...}, dicts, lists, or literals)
        get_variable: Callable that takes a path string and returns the value

    Supports:
        - Full variable reference: "${var}" → returns the variable value
        - String interpolation: "prefix-${var}-suffix" → returns "prefix-value-suffix"
        - Nested structures: dicts and lists are resolved recursively
    """
    if isinstance(data, str):
        # Check if it's a full variable reference: exactly "${varname}"
        if data.startswith("${") and data.endswith("}") and "}" not in data[2:-1]:
            var_path = data[2:-1]
            return get_variable(var_path)
        # Check if it contains embedded variable references
        elif "${" in data:
            return _interpolate_string(data, get_variable)
        return data
    elif isinstance(data, dict):
        return {k: resolve_value(v, get_variable) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_value(item, get_variable) for item in data]
    return data


def _interpolate_string(s: str, get_variable: callable) -> str:
    """Replace all ${...} patterns in a string with their resolved values."""
    def replace_var(match):
        var_path = match.group(1)
        value = get_variable(var_path)
        return str(value) if value is not None else ""

    return re.sub(r'\$\{([^}]+)\}', replace_var, s)


def evaluate_condition(expr: str, get_variable: callable) -> bool:
    """Evaluate a condition expression.

    Supports:
        - ${var} → truthy check
        - ${var} == value
        - ${var} != value
        - ${var} > number
        - ${var} < number
        - ${var} >= number
        - ${var} <= number
    """
    if not expr or not isinstance(expr, str):
        return False

    expr = expr.strip()

    if expr.startswith("${") and expr.endswith("}"):
        value = get_variable(expr[2:-1])
        return bool(value)

    for op in ("==", "!=", ">=", "<=", ">", "<"):
        if op in expr:
            left, right = expr.split(op, 1)
            left_val = _resolve_operand(left.strip(), get_variable)
            right_val = _resolve_operand(right.strip(), get_variable)

            if op == "==":
                return _coerce_compare(left_val, right_val) == 0
            elif op == "!=":
                return _coerce_compare(left_val, right_val) != 0
            elif op in (">", "<", ">=", "<="):
                try:
                    l, r = float(left_val), float(right_val)
                except (TypeError, ValueError):
                    return False
                if op == ">":
                    return l > r
                elif op == "<":
                    return l < r
                elif op == ">=":
                    return l >= r
                else:
                    return l <= r

    return False


def _resolve_operand(operand: str, get_variable: callable) -> Any:
    if operand.startswith("${") and operand.endswith("}"):
        return get_variable(operand[2:-1])
    if len(operand) >= 2 and operand[0] in ("'", '"') and operand[-1] == operand[0]:
        return operand[1:-1]
    if operand.lower() == "true":
        return True
    if operand.lower() == "false":
        return False
    if operand.lower() == "null" or operand.lower() == "none":
        return None
    try:
        return int(operand)
    except ValueError:
        try:
            return float(operand)
        except ValueError:
            return operand


def _coerce_compare(left: Any, right: Any) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return -1
    if right is None:
        return 1
    if isinstance(left, bool) or isinstance(right, bool):
        return 0 if bool(left) == bool(right) else (-1 if bool(left) < bool(right) else 1)
    try:
        l, r = float(left), float(right)
        return (l > r) - (l < r)
    except (TypeError, ValueError):
        sl, sr = str(left), str(right)
        return (sl > sr) - (sl < sr)
