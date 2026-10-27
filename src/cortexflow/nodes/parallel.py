"""Parallel node - Concurrent branch execution."""

from __future__ import annotations

import asyncio
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("parallel")
class ParallelNode(BaseNode):
    """Execute branches concurrently via executor dispatch."""

    async def execute(self, context: ExecutionContext) -> Any:
        branches = self.config.get("branches", [])
        if not branches:
            raise ValueError("Parallel node missing 'branches'")

        strategy = self.config.get("strategy", "all")
        max_concurrency = self.config.get("max_concurrency")

        if context.executor:
            if max_concurrency and len(branches) > max_concurrency:
                results = await self._bounded_execute(branches, max_concurrency, context)
            else:
                results = await self._parallel_execute(branches, context)
        else:
            results = [{"branch_id": b, "status": "no_executor"} for b in branches]

        return self._apply_strategy(results, strategy)

    async def _parallel_execute(self, branches: list[str], context: ExecutionContext) -> list:
        tasks = [context.executor.execute_sub_node(b, context.clone()) for b in branches]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _bounded_execute(
        self, branches: list[str], max_concurrency: int, context: ExecutionContext
    ) -> list:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def bounded(branch_id: str):
            async with semaphore:
                return await context.executor.execute_sub_node(branch_id, context.clone())

        tasks = [bounded(b) for b in branches]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _apply_strategy(self, results: list, strategy: str) -> Any:
        if strategy == "any":
            for r in results:
                if not isinstance(r, Exception):
                    return r
            return results
        elif strategy == "race":
            for r in results:
                if not isinstance(r, Exception):
                    return r
            return None
        else:  # all
            return results
