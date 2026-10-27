"""Compiler - Convert DSL to IR."""

from __future__ import annotations

from cortexflow.compiler.ir import (
    BlackboardConfigIR,
    EdgeIR,
    FlowIR,
    NodeIR,
    TierIR,
    VariableIR,
)
from cortexflow.dsl.schema import WorkflowDefinition
from cortexflow.dsl.validator import Validator


class Compiler:
    """Compile workflow DSL to IR."""

    def __init__(self):
        self.validator = Validator()

    def compile(self, workflow: WorkflowDefinition) -> FlowIR:
        """Compile workflow to IR."""
        self.validator.validate(workflow)

        nodes = self._compile_nodes(workflow)
        edges = self._compile_edges(workflow)
        variables = self._compile_variables(workflow)
        blackboard_config = self._compile_blackboard(workflow)
        tiers = self._compile_tiers(workflow)

        return FlowIR(
            id=workflow.id,
            name=workflow.name,
            entry=workflow.entry,
            nodes=nodes,
            edges=edges,
            variables=variables,
            blackboard_config=blackboard_config,
            tiers=tiers,
            metadata=workflow.metadata,
        )

    def _compile_nodes(self, workflow: WorkflowDefinition) -> dict[str, NodeIR]:
        """Compile nodes."""
        nodes = {}
        for node_id, node_def in workflow.nodes.items():
            config = node_def.model_dump(exclude_none=True)
            node_ir = NodeIR(
                id=node_id,
                type=node_def.type.value,
                config=config,
                on_success=node_def.on_success,
                on_error=node_def.on_error,
                resolved_tier=node_def.tier or workflow.config.default_tier,
                resolved_identity=node_def.identity or workflow.config.role,
            )
            nodes[node_id] = node_ir
        return nodes

    def _compile_edges(self, workflow: WorkflowDefinition) -> dict[str, list[EdgeIR]]:
        """Compile edges."""
        edges: dict[str, list[EdgeIR]] = {}
        for edge_def in workflow.edges:
            edge_ir = EdgeIR(
                from_node=edge_def.from_node,
                to_node=edge_def.to_node,
                condition=edge_def.condition,
                priority=edge_def.priority,
            )
            if edge_def.from_node not in edges:
                edges[edge_def.from_node] = []
            edges[edge_def.from_node].append(edge_ir)
        return edges

    def _compile_variables(
        self, workflow: WorkflowDefinition
    ) -> dict[str, VariableIR]:
        """Compile variables."""
        variables = {}
        for var_name, var_def in workflow.variables.items():
            var_ir = VariableIR(
                name=var_name,
                type=var_def.type,
                required=var_def.required,
                default=var_def.default,
                enum=var_def.enum,
            )
            variables[var_name] = var_ir
        return variables

    def _compile_blackboard(self, workflow: WorkflowDefinition) -> BlackboardConfigIR:
        """Compile blackboard config."""
        return BlackboardConfigIR(
            enabled=workflow.blackboard.enabled,
            visibility=dict(workflow.blackboard.visibility),
        )

    def _compile_tiers(self, workflow: WorkflowDefinition) -> dict[str, TierIR]:
        """Compile tier definitions."""
        tiers = {}
        for tier_name, tier_def in workflow.tiers.items():
            tier_ir = TierIR(
                name=tier_name,
                description=tier_def.description,
                model=tier_def.model,
                provider=tier_def.provider,
                max_concurrency=tier_def.max_concurrency,
                timeout=tier_def.timeout,
                tools=tier_def.tools,
                parent=tier_def.parent,
                metadata=tier_def.metadata,
            )
            tiers[tier_name] = tier_ir
        return tiers
