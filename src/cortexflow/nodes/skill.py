"""Skill node for workflow integration."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("skill")
class SkillNode(BaseNode):
    """Invokes a registered skill."""

    async def execute(self, context: ExecutionContext) -> Any:
        skill_id = self.resolve(self.config.get("skill_id") or self.config.get("skill"), context)
        if not skill_id:
            raise ValueError("Skill node requires 'skill_id' or 'skill' config")

        skill_registry = context.get_adapter("skill_registry")
        if not skill_registry:
            raise RuntimeError("Skill registry not available in execution context")

        params = {}
        raw_params = self.config.get("params") or self.config.get("args") or {}
        for key, value in raw_params.items():
            params[key] = self.resolve(value, context)

        if not params and self.config.get("input"):
            params["text"] = self.resolve(self.config["input"], context)

        result = await skill_registry.invoke(skill_id, **params)

        output_var = self.config.get("output")
        if output_var:
            context.set_variable(output_var, result)

        return {
            "skill_id": skill_id,
            "result": result,
            "output_variable": output_var,
        }
