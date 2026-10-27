"""Tool runtime adapter - Function registry and execution."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from cortexflow.adapters.base import ToolRuntimeAdapter

logger = logging.getLogger(__name__)


class RegistryToolAdapter(ToolRuntimeAdapter):
    """Tool adapter with a registry of callable functions."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._register_builtins()

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        description: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self._tools[name] = {
            "func": func,
            "description": description,
            "parameters": parameters or {},
        }

    def _register_builtins(self) -> None:
        self.register("echo", lambda text="": text, "Echo input text", {"text": "str"})
        self.register("concat", lambda a="", b="": f"{a}{b}", "Concatenate two strings", {"a": "str", "b": "str"})
        self.register("json_parse", lambda text="{}": __import__("json").loads(text), "Parse JSON string")
        self.register("length", lambda items=None: len(items or []), "Get length of a list")
        self.register("format_text", lambda template="", **kw: template.format(**kw), "Format text with variables")

    async def invoke(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {list(self._tools.keys())}")

        func = tool["func"]
        try:
            result = func(**args) if args else func()
        except TypeError as e:
            try:
                result = func(args) if args else func()
            except Exception:
                raise ValueError(f"Tool {tool_name} argument error: {e}") from e

        return {
            "tool": tool_name,
            "result": result,
            "args": args,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"],
            }
            for name, info in self._tools.items()
        ]

    def load_from_module(self, module_path: str) -> int:
        """Load tools from a Python module. Functions with _tool_description attr are registered."""
        try:
            mod = importlib.import_module(module_path)
        except ImportError as e:
            logger.error("Failed to import tool module %s: %s", module_path, e)
            return 0

        count = 0
        for name in dir(mod):
            obj = getattr(mod, name)
            if callable(obj) and hasattr(obj, "_tool_description"):
                self.register(
                    name=name,
                    func=obj,
                    description=getattr(obj, "_tool_description", ""),
                    parameters=getattr(obj, "_tool_parameters", None),
                )
                count += 1
        return count
