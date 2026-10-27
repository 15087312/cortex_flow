"""Ask node - Suspend the flow with a question for the user (Coze-style).

The flow suspends (persisted checkpoint, survives restarts) and the API
returns 202 ``suspended`` with the question. Resume via
``POST /workflows/{id}/resume`` with ``{"answer": ...}`` (or any payload);
the answer lands in ``output`` (default ``"answer"``) and execution
continues at ``on_event``::

    confirm:
      type: ask
      question: '为 ${user} 退款 ${amount} 元，确认吗？'
      output: confirmed
      on_event: do_refund
"""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import AskQuestion


@NodeRegistry.register("ask")
class AskNode(BaseNode):
    """Ask the user a question and suspend until answered."""

    async def execute(self, context: ExecutionContext) -> Any:
        question = self.config.get("question")
        if not question:
            raise ValueError(f"Ask node '{self.node_id}' missing 'question'")
        rendered = self.resolve(question, context)
        answer_var = self.config.get("output") or "answer"
        raise AskQuestion(
            question="" if rendered is None else str(rendered),
            answer_var=answer_var,
            node_id=self.node_id,
        )
