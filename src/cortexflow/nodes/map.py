"""Map node - Apply operation to each element in a collection."""

from __future__ import annotations

import asyncio
from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.utils.resolver import resolve_value


@NodeRegistry.register("map")
class MapNode(BaseNode):
    """Apply a body node to each element in a collection via executor dispatch."""

    async def execute(self, context: ExecutionContext) -> Any:
        collection_ref = self.config.get("collection")
        if not collection_ref:
            raise ValueError("Map node missing 'collection'")

        element_var = self.config.get("element_var", "element")
        index_var = self.config.get("index_var")
        output_collection = self.config.get("output_collection")
        concurrency = self.config.get("map_concurrency")
        map_body = self.config.get("map_body")

        collection = resolve_value(collection_ref, context.get_variable)
        if not isinstance(collection, (list, tuple)):
            raise TypeError(f"Map collection must be iterable, got {type(collection)}")

        if context.executor and map_body:
            if concurrency and concurrency > 1:
                results = await self._concurrent_map(
                    collection, element_var, index_var, concurrency, map_body, context
                )
            else:
                results = await self._sequential_map(
                    collection, element_var, index_var, map_body, context
                )
        else:
            results = [
                {"index": i, "element": item, "status": "no_executor"}
                for i, item in enumerate(collection)
            ]

        if output_collection:
            context.set_variable(output_collection, results)

        return results

    async def _sequential_map(
        self, collection, element_var, index_var, map_body, context
    ) -> list:
        results = []
        for i, item in enumerate(collection):
            context.set_variable(element_var, item)
            if index_var:
                context.set_variable(index_var, i)
            result = await context.executor.execute_sub_node(map_body, context, follow_chain=False)
            results.append(result)
        return results

    async def _concurrent_map(
        self, collection, element_var, index_var, concurrency, map_body, context
    ) -> list:
        semaphore = asyncio.Semaphore(concurrency)
        results = [None] * len(collection)

        async def process_item(i: int, item: Any):
            async with semaphore:
                ctx = context.clone()
                ctx.set_variable(element_var, item)
                if index_var:
                    ctx.set_variable(index_var, i)
                results[i] = await context.executor.execute_sub_node(map_body, ctx, follow_chain=False)

        tasks = [process_item(i, item) for i, item in enumerate(collection)]
        await asyncio.gather(*tasks)
        return results
