"""Collaboration node - multi-agent collaboration patterns."""

from __future__ import annotations

from typing import Any

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


@NodeRegistry.register("collaborate")
class CollaborateNode(BaseNode):
    """Run a multi-agent collaboration pattern."""

    async def execute(self, context: ExecutionContext) -> Any:
        pattern = self.config.get("pattern", "pipeline")
        agent_ids = self.config.get("agents", [])
        task = self.config.get("task", "${input}")
        rounds = self.config.get("rounds", 3)
        supervisor_id = self.config.get("supervisor", "")

        resolved = self.resolve({"task": task, "agents": agent_ids}, context)
        task_text = str(resolved["task"])
        resolved_agents = resolved["agents"] if isinstance(resolved["agents"], list) else agent_ids

        agent_registry = context.get_adapter("agent_registry")
        model_adapter = context.get_adapter("model")

        if not agent_registry:
            return {"pattern": pattern, "error": "Agent registry not available"}

        from cortexflow.agents.collaboration import CollaborationEngine
        engine = CollaborationEngine(agent_registry, model_adapter)

        if pattern == "supervisor":
            sup_id = supervisor_id or (resolved_agents[0] if resolved_agents else "planner")
            workers = resolved_agents[1:] if len(resolved_agents) > 1 else resolved_agents
            result = await engine.supervisor_pattern(sup_id, workers, task_text)

        elif pattern == "debate":
            result = await engine.debate_pattern(resolved_agents, task_text, rounds=rounds)

        elif pattern == "pipeline":
            result = await engine.pipeline_pattern(resolved_agents, task_text)

        elif pattern == "vote":
            result = await engine.vote_pattern(resolved_agents, task_text)

        else:
            raise ValueError(f"Unknown collaboration pattern: {pattern}")

        return result
