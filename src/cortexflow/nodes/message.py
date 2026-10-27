"""Message node - emit a chat message (Coze-style message node).

The node renders ``message`` (``${var}`` interpolation is supported) and
publishes it on the event bus as ``flow.message``, so a connected UI can
append it to the conversation.  The message is also appended to the
``messages`` variable (``[{role, content, node_id}, ...]``) for later nodes.

    reply:
      type: message
      role: assistant
      message: "已处理 ${count} 条记录"
      output: reply_text

``role`` is one of ``assistant`` (default), ``user`` or ``system``.
"""

from __future__ import annotations

import json

from cortexflow.events.types import Event, EventType
from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext

_ROLES = {"assistant", "user", "system"}


@NodeRegistry.register("message")
class MessageNode(BaseNode):
    """Publish a chat message and record it in the conversation history."""

    async def execute(self, context: ExecutionContext) -> str:
        raw = self.resolve(self.config.get("message"), context)
        if raw is None or raw == "":
            raise ValueError(f"Message node '{self.node_id}' requires 'message'")

        content = (
            raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        )
        role = str(self.config.get("role") or "assistant").lower()
        if role not in _ROLES:
            raise ValueError(
                f"Message node '{self.node_id}' has unknown role '{role}' "
                f"(expected {'|'.join(sorted(_ROLES))})"
            )

        history = context.get_variable("messages")
        if not isinstance(history, list):
            history = []
        context.set_variable(
            "messages",
            [*history, {"role": role, "content": content, "node_id": self.node_id}],
        )

        if context.event_bus:
            await context.event_bus.publish(
                Event(
                    type=EventType.MESSAGE,
                    payload={
                        "flow_id": context.flow_id,
                        "node_id": self.node_id,
                        "role": role,
                        "content": content,
                    },
                )
            )
        return content
