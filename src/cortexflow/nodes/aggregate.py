"""Aggregate node - Merge branch outputs into unified variables (Coze-style).

Each group merges one variable from several candidate sources::

    merge:
      type: aggregate
      groups:
        - output: answer
          from: [vip_answer, normal_answer]
          strategy: first        # first | last | concat | merge
        - output: all_items
          from: [a_items, b_items]
          strategy: concat

Strategies:

- ``first`` (default): first source that is neither ``None`` nor ``""``
  (empty list counts as empty too).
- ``last``: last non-empty source.
- ``concat``: lists are concatenated, strings joined with ``"\\n"``,
  anything else collected into a list.
- ``merge``: dicts are shallow-merged (later sources win); non-dict
  sources fall back to ``first`` semantics.

Returns ``{output_name: value}`` for all groups.
"""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


@NodeRegistry.register("aggregate")
class AggregateNode(BaseNode):
    """Merge upstream branch outputs."""

    async def execute(self, context: ExecutionContext) -> Any:
        groups = self.config.get("groups")
        if not groups:
            raise ValueError(
                f"Aggregate node '{self.node_id}' missing 'groups'"
            )
        merged: dict[str, Any] = {}
        for group in groups:
            output = group.get("output")
            if not output:
                raise ValueError(
                    f"Aggregate node '{self.node_id}': group missing 'output': "
                    f"{group!r}"
                )
            sources = group.get("from", [])
            if isinstance(sources, str):
                sources = [sources]
            values = [self._resolve_ref(ref, context) for ref in sources]
            strategy = (group.get("strategy") or "first").lower()
            if strategy == "first":
                merged[output] = next(
                    (v for v in values if not _is_empty(v)), None
                )
            elif strategy == "last":
                non_empty = [v for v in values if not _is_empty(v)]
                merged[output] = non_empty[-1] if non_empty else None
            elif strategy == "concat":
                merged[output] = _concat(values)
            elif strategy == "merge":
                merged[output] = _merge_dicts(values)
            else:
                raise ValueError(
                    f"Aggregate node '{self.node_id}': unknown strategy "
                    f"'{strategy}' (expected first|last|concat|merge)"
                )
            context.set_variable(output, merged[output])
        return merged

    def _resolve_ref(self, ref: Any, context: ExecutionContext) -> Any:
        """Resolve a source reference.

        Bare names (``vip_answer``) refer to variables, exactly like
        ``${vip_answer}``; anything else goes through normal resolution.
        """
        if isinstance(ref, str) and "${" not in ref:
            return context.get_variable(ref)
        return self.resolve(ref, context)


def _concat(values: list[Any]) -> Any:
    items = [v for v in values if not _is_empty(v)]
    if not items:
        return None
    if all(isinstance(v, list) for v in items):
        return [x for v in items for x in v]
    if all(isinstance(v, str) for v in items):
        return "\n".join(items)
    return items


def _merge_dicts(values: list[Any]) -> Any:
    dicts = [v for v in values if isinstance(v, dict)]
    if not dicts:
        return next((v for v in values if not _is_empty(v)), None)
    merged: dict[str, Any] = {}
    for d in dicts:
        merged.update(d)
    return merged
