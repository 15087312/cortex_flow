"""Agent registry - manages agent definitions and instances."""

from __future__ import annotations

from typing import Any

from cortexflow.agents.definition import AgentDefinition
from cortexflow.agents.agent import Agent


class AgentRegistry:
    """Registry for agent definitions and live agent instances."""

    def __init__(self):
        self._definitions: dict[str, AgentDefinition] = {}
        self._instances: dict[str, Agent] = {}
        self._register_builtins()

    def register(self, definition: AgentDefinition) -> None:
        self._definitions[definition.id] = definition

    def unregister(self, agent_id: str) -> None:
        self._definitions.pop(agent_id, None)
        self._instances.pop(agent_id, None)

    def get_definition(self, agent_id: str) -> AgentDefinition | None:
        return self._definitions.get(agent_id)

    def get_or_create(self, agent_id: str) -> Agent | None:
        if agent_id in self._instances:
            return self._instances[agent_id]
        defn = self._definitions.get(agent_id)
        if not defn:
            return None
        agent = Agent(defn)
        self._instances[agent_id] = agent
        return agent

    def get_instance(self, agent_id: str) -> Agent | None:
        return self._instances.get(agent_id)

    def list_definitions(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._definitions.values()]

    def list_instances(self) -> list[str]:
        return list(self._instances.keys())

    def reset_instance(self, agent_id: str) -> None:
        defn = self._definitions.get(agent_id)
        if defn:
            self._instances[agent_id] = Agent(defn)

    def _register_builtins(self) -> None:
        self.register(AgentDefinition(
            id="planner",
            name="Planner",
            role="planner",
            description="Breaks down complex tasks into steps and delegates to other agents",
            system_prompt=(
                "You are a task planner. Your job is to analyze user requests, "
                "break them into concrete steps, and decide which specialist agent "
                "should handle each step. Output a JSON plan with the structure: "
                '{"steps": [{"agent": "agent_id", "task": "description"}, ...]}'
            ),
            tools=[],
        ))

        self.register(AgentDefinition(
            id="coder",
            name="Coder",
            role="coder",
            description="Writes and reviews code",
            system_prompt=(
                "You are an expert programmer. Write clean, efficient code. "
                "When given a task, produce working code with brief explanations. "
                "Always include error handling and follow best practices."
            ),
            tools=["echo", "concat"],
        ))

        self.register(AgentDefinition(
            id="reviewer",
            name="Reviewer",
            role="reviewer",
            description="Reviews output quality and provides feedback",
            system_prompt=(
                "You are a quality reviewer. Analyze the given output critically. "
                "Check for correctness, completeness, and quality. "
                "Provide specific feedback and suggestions for improvement. "
                "Rate the output 1-10 and explain your rating."
            ),
            tools=[],
        ))

        self.register(AgentDefinition(
            id="researcher",
            name="Researcher",
            role="researcher",
            description="Gathers and synthesizes information",
            system_prompt=(
                "You are a research specialist. Gather relevant information, "
                "synthesize findings from multiple sources, and present "
                "well-organized summaries with key insights."
            ),
            tools=[],
        ))

        self.register(AgentDefinition(
            id="summarizer",
            name="Summarizer",
            role="summarizer",
            description="Summarizes long content into concise summaries",
            system_prompt=(
                "You are a summarization expert. Condense long content into "
                "clear, concise summaries while preserving key information. "
                "Use bullet points when appropriate."
            ),
            tools=[],
        ))
