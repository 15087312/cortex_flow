"""Collaboration patterns for multi-agent workflows."""

from __future__ import annotations

import json
from typing import Any

from cortexflow.agents.agent import Agent
from cortexflow.agents.registry import AgentRegistry


class CollaborationEngine:
    """Orchestrates multi-agent collaboration patterns."""

    def __init__(self, registry: AgentRegistry, model_adapter: Any = None):
        self._registry = registry
        self._model_adapter = model_adapter

    async def _call_agent(self, agent: Agent, message: str, context: dict[str, Any] | None = None) -> str:
        if not self._model_adapter:
            return f"[{agent.name}] Acknowledged: {message}"

        messages = agent.get_conversation_messages(message)
        agent.record_user_message(message)

        defn = agent.definition
        try:
            result = await self._model_adapter.invoke(
                tier=defn.tier or "default",
                identity=defn.role or "assistant",
                messages=messages,
                temperature=defn.temperature,
            )
            response = result.get("output", "") if isinstance(result, dict) else str(result)
        except Exception as e:  # noqa: BLE001
            response = f"[LLM 调用失败: {e}]"
        agent.record_response(response)
        return response

    async def supervisor_pattern(
        self,
        supervisor_id: str,
        worker_ids: list[str],
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        supervisor = self._registry.get_or_create(supervisor_id)
        if not supervisor:
            raise ValueError(f"Agent '{supervisor_id}' not found")

        plan_response = await self._call_agent(
            supervisor,
            f"Create a plan to accomplish this task by delegating to available workers: {worker_ids}\n\nTask: {task}",
            context,
        )

        try:
            plan = json.loads(plan_response)
            steps = plan.get("steps", [])
        except (json.JSONDecodeError, TypeError):
            steps = [{"agent": worker_ids[0] if worker_ids else supervisor_id, "task": task}]

        results = {}
        for step in steps:
            agent_id = step.get("agent", supervisor_id)
            step_task = step.get("task", task)
            agent = self._registry.get_or_create(agent_id)
            if not agent:
                results[agent_id] = f"Agent '{agent_id}' not found"
                continue
            result = await self._call_agent(agent, step_task, context)
            results[agent_id] = result

        summary = await self._call_agent(
            supervisor,
            f"Here are the results from the workers:\n{json.dumps(results, ensure_ascii=False, indent=2)}\n\nProvide a final summary.",
            context,
        )

        return {
            "pattern": "supervisor",
            "plan": steps,
            "worker_results": results,
            "final_summary": summary,
        }

    async def debate_pattern(
        self,
        agent_ids: list[str],
        topic: str,
        rounds: int = 3,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agents = []
        for aid in agent_ids:
            agent = self._registry.get_or_create(aid)
            if agent:
                agents.append(agent)

        if len(agents) < 2:
            raise ValueError("Debate requires at least 2 agents")

        history: list[dict[str, str]] = []

        for round_num in range(rounds):
            round_messages = {}
            for agent in agents:
                prev = "\n".join(
                    f"[{m['agent']}]: {m['content'][:200]}" for m in history[-6:]
                )
                prompt = f"Topic: {topic}\n\nPrevious discussion:\n{prev}\n\nRound {round_num + 1}/{rounds}. Share your perspective."
                response = await self._call_agent(agent, prompt, context)
                round_messages[agent.id] = response
                history.append({"agent": agent.id, "round": round_num + 1, "content": response})

        consensus_agent = agents[0]
        full_history = "\n".join(
            f"[{h['agent']} (Round {h['round']})]: {h['content']}" for h in history
        )
        consensus = await self._call_agent(
            consensus_agent,
            f"Based on this debate, synthesize a consensus position:\n\n{full_history}",
            context,
        )

        return {
            "pattern": "debate",
            "topic": topic,
            "rounds": rounds,
            "history": history,
            "consensus": consensus,
        }

    async def pipeline_pattern(
        self,
        agent_ids: list[str],
        initial_input: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agents = []
        for aid in agent_ids:
            agent = self._registry.get_or_create(aid)
            if agent:
                agents.append(agent)

        if not agents:
            raise ValueError("Pipeline requires at least 1 agent")

        current_input = initial_input
        stage_results = {}

        for agent in agents:
            result = await self._call_agent(agent, current_input, context)
            stage_results[agent.id] = result
            current_input = result

        return {
            "pattern": "pipeline",
            "stages": [a.id for a in agents],
            "stage_results": stage_results,
            "final_output": current_input,
        }

    async def vote_pattern(
        self,
        agent_ids: list[str],
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agents = []
        for aid in agent_ids:
            agent = self._registry.get_or_create(aid)
            if agent:
                agents.append(agent)

        if len(agents) < 2:
            raise ValueError("Vote requires at least 2 agents")

        responses = {}
        for agent in agents:
            prompt = (
                f"Answer this question independently and concisely:\n\n{question}\n\n"
                "Provide your answer, then rate your confidence 1-10."
            )
            result = await self._call_agent(agent, prompt, context)
            responses[agent.id] = result

        judge = agents[0]
        all_answers = "\n".join(
            f"[{aid}]: {resp}" for aid, resp in responses.items()
        )
        synthesis = await self._call_agent(
            judge,
            f"Here are independent answers to the question '{question}':\n\n{all_answers}\n\nSynthesize the best consensus answer.",
            context,
        )

        return {
            "pattern": "vote",
            "question": question,
            "individual_responses": responses,
            "consensus_answer": synthesis,
        }
