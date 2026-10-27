"""End node - Terminate a flow with a return value (Coze-style).

Two modes:
- ``variable`` (default): ``return_value`` names a variable (``"${x}"`` or
  plain ``"x"``); the variable's value becomes the flow result.
- ``text``: ``return_value`` is a template string; ``${var}`` placeholders
  are interpolated and the rendered text becomes the flow result.

In both modes the value is written to the ``result`` variable, which is
what :meth:`Executor.execute` returns.
"""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("end")
class EndNode(BaseNode):
    """Terminate the flow with an explicit return value."""

    async def execute(self, context: ExecutionContext) -> Any:
        mode = (self.config.get("end_mode") or "variable").lower()
        if mode not in ("variable", "text"):
            raise ValueError(
                f"End node '{self.node_id}' has unknown end_mode '{mode}' "
                "(expected 'variable' or 'text')"
            )
        raw = self.config.get("return_value")

        if mode == "variable":
            if raw is None:
                value = context.get_variable("result")
            elif isinstance(raw, str):
                name = raw[2:-1] if raw.startswith("${") and raw.endswith("}") else raw
                value = context.get_variable(name)
            else:
                value = self.resolve(raw, context)
        else:
            value = self.resolve(raw, context) if raw is not None else ""
            if not isinstance(value, str):
                value = "" if value is None else str(value)

        context.set_variable("result", value)
        return value
