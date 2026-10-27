"""Loop node - Iteration with condition, count, until, foreach."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import LoopBreak, LoopContinue
from cortexflow.utils.resolver import evaluate_condition, resolve_value


@NodeRegistry.register("loop")
class LoopNode(BaseNode):
    """Loop execution with multiple modes.

    Returns iteration results. Body node dispatch is handled by the executor.
    """

    async def execute(self, context: ExecutionContext) -> Any:
        mode = self.config.get("loop_mode", "condition")
        max_iterations = self.config.get("max_iterations", 1000)

        if mode == "count":
            return await self._loop_count(context, max_iterations)
        elif mode == "condition":
            return await self._loop_condition(context, max_iterations)
        elif mode == "until":
            return await self._loop_until(context, max_iterations)
        elif mode == "foreach":
            return await self._loop_foreach(context, max_iterations)
        else:
            raise ValueError(f"Unknown loop mode: {mode}")

    async def _exec_body(self, context: ExecutionContext, default: Any) -> tuple[str, Any]:
        """Run the loop body chain.

        Returns ``(action, result)`` where action is one of ``"append"``
        (normal result), ``"break"`` (``break`` node hit) or ``"continue"``
        (``continue`` node hit).
        """
        body = self.config.get("body")
        try:
            if body and context.executor:
                result = await context.executor.execute_sub_node(
                    body, context, follow_chain=True
                )
                return "append", result
            return "append", default
        except LoopBreak:
            return "break", None
        except LoopContinue:
            return "continue", None

    async def _loop_count(self, context: ExecutionContext, max_iterations: int) -> Any:
        count = min(self.config.get("count", 1), max_iterations)
        iterator_var = self.config.get("iterator_var", "iteration")
        break_condition = self.config.get("break_condition")
        continue_condition = self.config.get("continue_condition")
        results = []

        for i in range(count):
            context.set_variable(iterator_var, i)

            if break_condition and evaluate_condition(break_condition, context.get_variable):
                break
            if continue_condition and evaluate_condition(continue_condition, context.get_variable):
                continue

            action, result = await self._exec_body(context, i)
            if action == "break":
                break
            if action == "continue":
                continue
            results.append(result)

        return results

    async def _loop_condition(self, context: ExecutionContext, max_iterations: int) -> Any:
        condition = self.config.get("condition")
        iterator_var = self.config.get("iterator_var", "iteration")
        break_condition = self.config.get("break_condition")
        continue_condition = self.config.get("continue_condition")
        results = []
        i = 0

        while i < max_iterations:
            if condition and not evaluate_condition(condition, context.get_variable):
                break
            context.set_variable(iterator_var, i)

            if break_condition and evaluate_condition(break_condition, context.get_variable):
                break
            if continue_condition and evaluate_condition(continue_condition, context.get_variable):
                i += 1
                continue

            action, result = await self._exec_body(context, i)
            if action == "break":
                break
            if action == "continue":
                i += 1
                continue
            results.append(result)
            i += 1

        return results

    async def _loop_until(self, context: ExecutionContext, max_iterations: int) -> Any:
        until = self.config.get("until")
        iterator_var = self.config.get("iterator_var", "iteration")
        break_condition = self.config.get("break_condition")
        continue_condition = self.config.get("continue_condition")
        results = []
        i = 0

        while i < max_iterations:
            context.set_variable(iterator_var, i)

            if break_condition and evaluate_condition(break_condition, context.get_variable):
                break
            if continue_condition and evaluate_condition(continue_condition, context.get_variable):
                i += 1
                continue

            action, result = await self._exec_body(context, i)
            if action == "break":
                break
            if action == "continue":
                i += 1
                continue
            results.append(result)

            if until and evaluate_condition(until, context.get_variable):
                break
            i += 1

        return results

    async def _loop_foreach(self, context: ExecutionContext, max_iterations: int) -> Any:
        items_ref = self.config.get("collection") or self.config.get("items") or self.config.get("foreach")
        if not items_ref:
            raise ValueError("Foreach loop needs 'collection', 'items', or 'foreach'")

        items = resolve_value(items_ref, context.get_variable)
        if not isinstance(items, (list, tuple)):
            raise TypeError(f"Foreach items must be iterable, got {type(items)}")

        item_var = self.config.get("item_var", "item")
        index_var = self.config.get("index_var")
        break_condition = self.config.get("break_condition")
        continue_condition = self.config.get("continue_condition")
        results = []

        for i, item in enumerate(items[:max_iterations]):
            context.set_variable(item_var, item)
            if index_var:
                context.set_variable(index_var, i)

            if break_condition and evaluate_condition(break_condition, context.get_variable):
                break
            if continue_condition and evaluate_condition(continue_condition, context.get_variable):
                continue

            action, result = await self._exec_body(context, item)
            if action == "break":
                break
            if action == "continue":
                continue
            results.append(result)

        return results
