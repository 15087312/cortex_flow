"""Intent node - Rules-based intent routing without an LLM (Coze-style).

Scores candidate intents by keyword hits against the input text and routes
to the winner's ``goto`` target — the same routing mechanism as ``branch``
(the executor follows a returned node id)::

    route:
      type: intent
      input: ${user_text}
      intents:
        - name: refund
          keywords: [退款, 退钱, refund]
          goto: refund_flow
        - name: hours
          keywords: [几点, 营业, 时间]
          goto: hours_flow
      otherwise: fallback

Matching is case-insensitive substring search. Ties resolve to the first
intent with the top score. With no match, routes to ``otherwise``; with
neither, returns ``None`` and the chain ends.

A model/embedding-backed matcher can replace ``_score`` later without
changing the routing contract.
"""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("intent")
class IntentNode(BaseNode):
    """Detect intent and route to the matching branch."""

    async def execute(self, context: ExecutionContext) -> Any:
        intents = self.config.get("intents")
        if not intents:
            raise ValueError(
                f"Intent node '{self.node_id}' missing 'intents'"
            )
        raw_text = self.config.get("input", self.config.get("input_text"))
        text = self.resolve(raw_text, context) if raw_text is not None else ""
        text = "" if text is None else str(text)

        best_goto: str | None = None
        best_name: str | None = None
        best_score = 0
        for intent in intents:
            keywords = intent.get("keywords") or []
            if isinstance(keywords, str):
                keywords = [keywords]
            score = _score(text, keywords)
            if score > best_score:
                best_score = score
                best_goto = intent.get("goto")
                best_name = intent.get("name")

        if best_goto and best_score > 0:
            output_var = self.config.get("output")
            if output_var:
                context.set_variable(output_var, best_name)
            return best_goto

        otherwise = self.config.get("otherwise")
        if otherwise:
            output_var = self.config.get("output")
            if output_var:
                context.set_variable(output_var, None)
            return otherwise
        return None


def _score(text: str, keywords: list[Any]) -> int:
    """Count case-insensitive substring hits."""
    lowered = text.lower()
    hits = 0
    for kw in keywords:
        if kw and str(kw).lower() in lowered:
            hits += 1
    return hits
