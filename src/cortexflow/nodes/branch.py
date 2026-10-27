"""Branch node - Conditional branching."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.utils.resolver import evaluate_condition


@NodeRegistry.register("branch")
class BranchNode(BaseNode):
    """Conditional branching. Returns the target node ID to route to."""

    async def execute(self, context: ExecutionContext) -> Any:
        mode = self.config.get("mode", "expression")
        conditions = self.config.get("conditions", [])

        if mode == "expression":
            return self._evaluate_expression(conditions, context)
        elif mode == "model_decision":
            return await self._model_decision(context)
        else:
            raise ValueError(f"Unknown branch mode: {mode}")

    def _evaluate_expression(
        self, conditions: list[dict], context: ExecutionContext
    ) -> str | None:
        for cond in conditions:
            when = cond.get("when")
            if when:
                if evaluate_condition(when, context.get_variable):
                    return cond.get("goto")
            otherwise = cond.get("otherwise")
            if otherwise:
                return otherwise
        return None

    async def _model_decision(self, context: ExecutionContext) -> str | None:
        model_config = self.config.get("model", {})
        prompt = self.config.get("prompt", "")
        output_mapping = self.config.get("output_mapping", {})
        tier = model_config.get("tier", "default")
        identity = model_config.get("identity", "router")

        model_adapter = context.get_adapter("model")
        if model_adapter:
            response = await model_adapter.invoke(
                tier=tier,
                identity=identity,
                messages=[
                    {"role": "system", "content": "You are a routing decision maker. Respond with exactly one of the given options."},
                    {"role": "user", "content": f"{prompt}\nOptions: {', '.join(output_mapping.keys())}"},
                ],
            )
            decision_text = response.get("response", response.get("output", ""))
            for key in output_mapping:
                if key in str(decision_text):
                    return output_mapping[key]

        decision = list(output_mapping.keys())[0] if output_mapping else None
        return output_mapping.get(decision)
