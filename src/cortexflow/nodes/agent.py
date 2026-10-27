"""Agent node - invoke an AI agent within a workflow."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("agent")
class AgentNode(BaseNode):
    """Invoke a registered agent with a message."""

    async def execute(self, context: ExecutionContext) -> Any:
        agent_id = self.config.get("agent_id") or self.config.get("agent")
        if not agent_id:
            raise ValueError("Agent node requires 'agent_id' field")

        message = self.config.get("message", "${input}")
        resolved_message = self.resolve({"msg": message}, context)["msg"]

        agent_registry = context.get_adapter("agent_registry")
        model_adapter = context.get_adapter("model")

        if not agent_registry:
            return {"agent_id": agent_id, "response": f"[mock] {resolved_message}", "status": "no_registry"}

        agent = agent_registry.get_or_create(agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found in registry")

        messages = agent.get_conversation_messages(str(resolved_message))
        agent.record_user_message(str(resolved_message))

        if model_adapter:
            defn = agent.definition
            try:
                result = await model_adapter.invoke(
                    tier=defn.tier or "default",
                    identity=defn.role or "assistant",
                    messages=messages,
                    temperature=defn.temperature,
                )
                response = result.get("output", "") if isinstance(result, dict) else str(result)
            except Exception as e:  # noqa: BLE001
                response = f"[LLM 调用失败: {e}]"
        else:
            response = f"[{agent.name}] Acknowledged: {resolved_message}"

        agent.record_response(response)

        memory_adapter = context.get_adapter("memory")
        if memory_adapter and defn.memory_namespace:
            await memory_adapter.store(
                content=f"User: {resolved_message}\nAgent: {response}",
                namespace=defn.memory_namespace,
                metadata={"agent_id": agent_id, "role": "conversation"},
            )

        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "response": response,
            "history_length": len(agent.history),
        }
