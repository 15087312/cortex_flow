"""CortexFlow Engine - Main entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cortexflow.adapters.memory import VectorMemoryAdapter
from cortexflow.adapters.model_runtime import RealModelRuntimeAdapter
from cortexflow.adapters.perception import DefaultPerceptionAdapter
from cortexflow.adapters.prompt_composer import DefaultPromptComposerAdapter
from cortexflow.adapters.tool_runtime import RegistryToolAdapter
from cortexflow.agents.registry import AgentRegistry
from cortexflow.compiler.compiler import Compiler
from cortexflow.dsl.parser import Parser
from cortexflow.dsl.schema import WorkflowDefinition
from cortexflow.events.bus import EventBus
from cortexflow.events.types import Event
from cortexflow.memory.manager import MemoryManager
from cortexflow.observability.metrics import MetricsCollector
from cortexflow.observability.tracer import Tracer
from cortexflow.rag.pipeline import RAGPipeline
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.executor import Executor
from cortexflow.skills.builtins import register_builtin_skills
from cortexflow.skills.registry import SkillRegistry
from cortexflow.state.checkpoint import CheckpointStore


class Engine:
    """CortexFlow workflow engine."""

    def __init__(self):
        self.parser = Parser()
        self.compiler = Compiler()

        self.event_bus = EventBus()
        self.tracer = Tracer()
        self.metrics = MetricsCollector()
        self.checkpoint_store = CheckpointStore()

        self.executor = Executor(
            event_bus=self.event_bus,
            tracer=self.tracer,
            metrics=self.metrics,
            checkpoint_store=self.checkpoint_store,
        )

        self._model_adapter = RealModelRuntimeAdapter()
        self._agent_registry = AgentRegistry()
        self._skill_registry = SkillRegistry()
        register_builtin_skills(self._skill_registry)
        self._rag_pipeline = RAGPipeline()
        self._memory_manager = MemoryManager()

        self._adapters: dict[str, Any] = {
            "model": self._model_adapter,
            "tool": RegistryToolAdapter(),
            "prompt_composer": DefaultPromptComposerAdapter(),
            "perception": DefaultPerceptionAdapter(),
            "memory": VectorMemoryAdapter(),
            "agent_registry": self._agent_registry,
            "skill_registry": self._skill_registry,
            "rag": self._rag_pipeline,
            "memory_manager": self._memory_manager,
        }

        self._subflow_registry: dict[str, WorkflowDefinition] = {}
        self._running: dict[str, ExecutionContext] = {}

    def register_adapter(self, name: str, adapter: Any) -> None:
        """Register a custom adapter."""
        self._adapters[name] = adapter

    def register_subflow(self, workflow_id: str, workflow: WorkflowDefinition) -> None:
        """Register a sub-workflow definition."""
        self._subflow_registry[workflow_id] = workflow

    def load(self, path: str | Path) -> WorkflowDefinition:
        """Load a workflow definition from file."""
        return self.parser.parse_file(path)

    def load_from_string(self, content: str, format: str = "yaml") -> WorkflowDefinition:
        """Load a workflow definition from string."""
        return self.parser.parse_string(content, format)

    def compile(self, workflow: WorkflowDefinition):
        """Compile workflow to intermediate representation."""
        return self.compiler.compile(workflow)

    async def run(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Run a workflow."""
        ir = self.compile(workflow)
        exec_context = self._build_context(ir, context, workflow.model_dump())
        self._running[ir.id] = exec_context

        self._model_adapter.set_tier_cache(ir.tiers)

        for sub_id, sub_wf in self._subflow_registry.items():
            sub_ir = self.compile(sub_wf)
            self.executor.register_subflow(sub_id, sub_ir)

        try:
            return await self.executor.execute(ir, exec_context)
        finally:
            self._running.pop(ir.id, None)

    async def run_file(self, path: str | Path, context: dict[str, Any] | None = None):
        """Load and run a workflow from file."""
        workflow = self.load(path)
        return await self.run(workflow, context)

    async def run_string(self, content: str, context: dict[str, Any] | None = None):
        """Load and run a workflow from YAML string."""
        workflow = self.load_from_string(content)
        return await self.run(workflow, context)

    async def resume(self, flow_id: str, event: Event) -> Any:
        """Resume a suspended workflow (checkpoint may come from SQLite)."""
        from cortexflow.runtime.states import FlowState, NodeState
        from cortexflow.state.blackboard import Blackboard

        checkpoint = await self.checkpoint_store.load(flow_id)
        if not checkpoint:
            raise ValueError(f"No suspended flow: {flow_id}")

        # Recompile the IR from the persisted definition — the in-memory
        # IR object is never pickled, so resume works across restarts.
        ir = None
        if checkpoint.definition:
            ir = self.compile(WorkflowDefinition(**checkpoint.definition))

        node_states: dict[str, Any] = {}
        for node_id, state in (checkpoint.node_states or {}).items():
            try:
                node_states[node_id] = NodeState(state)
            except ValueError:
                node_states[node_id] = state

        metadata = {
            k: v for k, v in (checkpoint.metadata or {}).items()
            if k.startswith(("_wait_config_", "_ask_"))
        }
        if ir is not None:
            metadata["_flow"] = ir

        ctx = ExecutionContext(
            flow_id=checkpoint.flow_id,
            variables=dict(checkpoint.variables or {}),
            node_states=node_states,
            current_node=checkpoint.current_node,
            blackboard=Blackboard.from_dict(checkpoint.blackboard_snapshot),
            metadata=metadata,
            adapters=self._adapters,
            event_bus=self.event_bus,
            tracer=self.tracer,
            metrics=self.metrics,
        )
        try:
            ctx.state = FlowState(checkpoint.flow_state)
        except ValueError:
            pass

        await self.checkpoint_store.delete(flow_id)
        return await self.executor.resume(flow_id, event, ctx)

    async def cancel(self, flow_id: str) -> None:
        """Cancel a running workflow."""
        ctx = self._running.get(flow_id)
        if ctx:
            from cortexflow.runtime.states import FlowState
            ctx.state = FlowState.CANCELLED

    def get_trace(self, flow_id: str):
        """Get execution trace for a flow."""
        return self.tracer.get_trace(flow_id)

    def get_metrics(self):
        """Get collected metrics."""
        return self.metrics.get_stats()

    def _build_context(self, ir: Any, variables: dict[str, Any] | None,
                         definition: dict[str, Any] | None = None) -> ExecutionContext:
        from cortexflow.state.blackboard import Blackboard

        bb_config = ir.blackboard_config
        blackboard = Blackboard(visibility=bb_config.visibility) if bb_config.enabled else Blackboard()

        ctx = ExecutionContext(
            variables=variables or {},
            blackboard=blackboard,
            adapters=dict(self._adapters),
            event_bus=self.event_bus,
            tracer=self.tracer,
            metrics=self.metrics,
        )
        ctx.metadata["_flow"] = ir
        if definition is not None:
            # Persisted into checkpoints so resume can recompile the IR.
            ctx.metadata["_definition"] = definition
        return ctx
