"""Model node - Call model instances."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("model")
class ModelNode(BaseNode):
    """Call a model instance via adapter."""

    async def execute(self, context: ExecutionContext) -> Any:
        tier = context.get_variable("_node_tier") or self.config.get("tier", "default")
        identity = self.config.get("identity", "default")
        prompt_strategy = self.config.get("prompt_strategy", "minimal")
        custom_system = self.config.get("custom_system")
        input_data = self.config.get("input", {})
        output_format = self.config.get("output_format", "text")

        resolved_input = self.resolve(input_data, context)

        messages = []
        if prompt_strategy != "none":
            composer = context.get_adapter("prompt_composer")
            if composer and prompt_strategy == "system_from_composer":
                system_prompt = composer.build_system({
                    "identity": identity,
                    "tier": tier,
                    "context": resolved_input,
                })
                messages.append({"role": "system", "content": system_prompt})
            elif custom_system:
                resolved_system = self.resolve(custom_system, context)
                messages.append({"role": "system", "content": resolved_system})

        messages.append({"role": "user", "content": str(resolved_input)})

        model_adapter = context.get_adapter("model")
        if model_adapter:
            result = await model_adapter.invoke(
                tier=tier,
                identity=identity,
                messages=messages,
                output_format=output_format,
            )
        else:
            result = {
                "tier": tier,
                "identity": identity,
                "input": resolved_input,
                "output": f"Mock response from {tier}/{identity}",
            }

        if isinstance(result, dict):
            content = result.get("output", result.get("content", result))
        else:
            # Adapters must return a dict, but tolerate raw values as content.
            content = result
        if output_format == "json" and isinstance(content, str):
            import json
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass

        outputs_spec = self.config.get("outputs")
        if outputs_spec:
            self._validate_outputs(outputs_spec, content)

        return content

    def _validate_outputs(self, specs: Any, content: Any) -> None:
        """Validate structured outputs (Coze-style).

        Contract: the node returns the model *content* (str, or parsed JSON
        when ``output_format`` is ``json``). When ``outputs`` declares named
        fields, they are checked against the parsed dict. Mismatches raise
        in ``strict_outputs`` mode and are ignored otherwise.
        """
        strict = bool(self.config.get("strict_outputs", False))
        if not isinstance(specs, list):
            if strict:
                raise ValueError(
                    f"Model node '{self.node_id}': 'outputs' must be a list"
                )
            return
        if not isinstance(content, dict):
            if strict:
                raise ValueError(
                    f"Model node '{self.node_id}': strict outputs declared but "
                    f"model returned non-JSON content of type {type(content).__name__}"
                )
            return
        errors: list[str] = []
        for spec in specs:
            if not isinstance(spec, dict) or "name" not in spec:
                errors.append(f"invalid output spec: {spec!r}")
                continue
            name = spec["name"]
            required = spec.get("required", True)
            if name not in content:
                if required:
                    errors.append(f"missing required output '{name}'")
                continue
            expected = str(spec.get("type", "any")).lower()
            if not _check_output_type(content[name], expected):
                errors.append(
                    f"output '{name}' expected type '{expected}', "
                    f"got {type(content[name]).__name__}"
                )
        if errors and strict:
            raise ValueError(
                f"Model node '{self.node_id}' output validation failed: "
                + "; ".join(errors)
            )


_OUTPUT_TYPE_CHECKS = {
    "string": str,
    "text": str,
    "number": (int, float),
    "integer": int,
    "int": int,
    "boolean": bool,
    "bool": bool,
    "array": list,
    "list": list,
    "object": dict,
    "dict": dict,
}


def _check_output_type(value: Any, expected: str) -> bool:
    """Check a value against a declared output type name."""
    if expected in ("any", "", "null", "none"):
        return True
    want = _OUTPUT_TYPE_CHECKS.get(expected)
    if want is None:
        return True  # unknown type names are not enforced
    if want is int and isinstance(value, bool):
        return False
    return isinstance(value, want)
