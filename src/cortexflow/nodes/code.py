"""Code node - run a Python snippet inside a workflow (Coze-style code node).

Declared ``inputs`` are resolved first and exposed both as individual
variables and as the ``inputs`` mapping.  The snippet communicates its
result through an ``output`` variable::

    compute:
      type: code
      inputs:
        numbers: "${numbers}"
      code: |
        total = sum(numbers)
        output = {"total": total, "count": len(numbers)}
      output: stats

Available helpers inside the snippet: ``json``, ``re``, ``math``,
``datetime`` plus a whitelist of pure builtins (no ``open``, ``eval``,
``exec``, ``__import__``, ...).

.. warning::
   This is a guard rail, not a security sandbox: ``exec`` still runs in the
   host interpreter, so only run workflows you trust.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import math
import re
from datetime import datetime
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext

_SAFE_BUILTIN_NAMES = (
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "int",
    "isinstance",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
)

SAFE_BUILTINS: dict[str, Any] = {
    name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES
}


def _run_snippet(code: str, inputs: dict[str, Any]) -> Any:
    """Execute *code* synchronously and return its ``output`` variable."""
    namespace: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "__name__": "__cortexflow_code__",
        "inputs": inputs,
        "output": None,
        "json": json,
        "re": re,
        "math": math,
        "datetime": datetime,
    }
    # Coze-style: declared inputs are also plain variables.
    namespace.update(inputs)
    exec(compile(code, "<cortexflow:code>", "exec"), namespace)  # noqa: S102
    return namespace.get("output")


@NodeRegistry.register("code")
class CodeNode(BaseNode):
    """Run a Python snippet and return its ``output`` value."""

    async def execute(self, context: ExecutionContext) -> Any:
        code = self.config.get("code")
        if not code:
            raise ValueError(f"Code node '{self.node_id}' requires 'code'")

        language = str(self.config.get("language") or "python").lower()
        if language != "python":
            raise ValueError(
                f"Code node '{self.node_id}' only supports 'python', got '{language}'"
            )

        inputs = self.resolve(self.config.get("inputs") or {}, context)
        if not isinstance(inputs, dict):
            raise TypeError(
                f"Code node '{self.node_id}' inputs must be a mapping, "
                f"got {type(inputs).__name__}"
            )

        timeout = self.config.get("code_timeout", 10)
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_run_snippet, code, inputs), timeout
            )
        except TimeoutError as exc:
            raise TimeoutError(
                f"Code node '{self.node_id}' timed out after {timeout}s"
            ) from exc
