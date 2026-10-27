"""Workflow validator."""

from __future__ import annotations

from cortexflow.dsl.schema import NodeType, WorkflowDefinition


class ValidationError(Exception):
    """Validation error."""



class Validator:
    """Validate workflow definitions."""

    def validate(self, workflow: WorkflowDefinition) -> None:
        """Validate workflow."""
        self._validate_entry(workflow)
        self._validate_nodes_reachable(workflow)
        self._validate_node_references(workflow)
        self._validate_variables(workflow)
        self._validate_tiers(workflow)
        self._validate_schedule(workflow)

    def _validate_entry(self, workflow: WorkflowDefinition) -> None:
        """Validate entry node exists."""
        if workflow.entry not in workflow.nodes:
            raise ValidationError(f"Entry node '{workflow.entry}' not found")

    def _validate_nodes_reachable(self, workflow: WorkflowDefinition) -> None:
        """Validate all nodes are reachable from entry."""
        reachable = set()
        to_visit = [workflow.entry]

        while to_visit:
            node_id = to_visit.pop()
            if node_id in reachable:
                continue
            if node_id not in workflow.nodes:
                # Unknown references are reported by _validate_node_references.
                continue
            reachable.add(node_id)

            node = workflow.nodes[node_id]
            if node.on_success and node.on_success != "__end__":
                to_visit.append(node.on_success)
            if node.on_error and node.on_error != "__end__":
                to_visit.append(node.on_error)

            if node.type == NodeType.BRANCH and node.conditions:
                for cond in node.conditions:
                    if cond.goto and cond.goto != "__end__":
                        to_visit.append(cond.goto)
                    if cond.otherwise and cond.otherwise != "__end__":
                        to_visit.append(cond.otherwise)

            if node.type == NodeType.PARALLEL and node.branches:
                for branch_id in node.branches:
                    if branch_id != "__end__":
                        to_visit.append(branch_id)

            if node.type == NodeType.LOOP:
                body = node.body
                if isinstance(body, str):
                    to_visit.append(body)
                elif isinstance(body, list):
                    to_visit.extend(body)
                if node.on_complete and node.on_complete != "__end__":
                    to_visit.append(node.on_complete)

            if node.type == NodeType.MAP and node.map_body:
                to_visit.append(node.map_body)

            if node.type == NodeType.INTENT:
                for intent in node.intents or []:
                    goto = intent.get("goto") if isinstance(intent, dict) else None
                    if goto and goto != "__end__":
                        to_visit.append(goto)
                if node.otherwise and node.otherwise != "__end__":
                    to_visit.append(node.otherwise)

            if node.type in (NodeType.WAIT, NodeType.ASK):
                if node.on_event and node.on_event != "__end__":
                    to_visit.append(node.on_event)
                if node.on_timeout and node.on_timeout != "__end__":
                    to_visit.append(node.on_timeout)
                if node.on_cancel and node.on_cancel != "__end__":
                    to_visit.append(node.on_cancel)

        all_nodes = set(workflow.nodes.keys())
        unreachable = all_nodes - reachable
        if unreachable:
            raise ValidationError(f"Unreachable nodes: {unreachable}")

    def _validate_node_references(self, workflow: WorkflowDefinition) -> None:
        """Validate node references are valid."""
        all_ids = set(workflow.nodes.keys()) | {"__end__"}

        for node_id, node in workflow.nodes.items():
            if node.on_success and node.on_success not in all_ids:
                raise ValidationError(
                    f"Node '{node_id}' references unknown node '{node.on_success}'"
                )
            if node.on_error and node.on_error not in all_ids:
                raise ValidationError(
                    f"Node '{node_id}' references unknown node '{node.on_error}'"
                )

            if node.type == NodeType.SUBFLOW and not node.flow:
                raise ValidationError(f"Subflow node '{node_id}' missing 'flow' field")

            if node.type == NodeType.TOOL and not node.tool:
                raise ValidationError(f"Tool node '{node_id}' missing 'tool' field")

            if node.type == NodeType.BRANCH and not node.conditions:
                raise ValidationError(f"Branch node '{node_id}' missing 'conditions'")

            if node.type == NodeType.LOOP:
                if not node.body:
                    raise ValidationError(f"Loop node '{node_id}' missing 'body'")
                if (
                    node.loop_mode
                    and node.loop_mode.value == "foreach"
                    and not node.items
                    and not node.foreach
                ):
                    raise ValidationError(
                        f"Foreach loop '{node_id}' needs 'items' or 'foreach'"
                    )

            if node.type == NodeType.PARALLEL:
                if not node.branches:
                    raise ValidationError(f"Parallel node '{node_id}' missing 'branches'")
                for branch_id in node.branches:
                    if branch_id not in all_ids:
                        raise ValidationError(
                            f"Parallel node '{node_id}' references unknown branch '{branch_id}'"
                        )

            if node.type == NodeType.MAP and (not node.collection or not node.map_body):
                missing = "collection" if not node.collection else "map_body"
                raise ValidationError(f"Map node '{node_id}' missing '{missing}'")

            if node.type == NodeType.MAP and node.map_body not in all_ids:
                raise ValidationError(
                    f"Map node '{node_id}' references unknown body '{node.map_body}'"
                )

            if node.type == NodeType.AGGREGATE and not node.groups:
                raise ValidationError(f"Aggregate node '{node_id}' missing 'groups'")

            if node.type == NodeType.INTENT:
                if not node.intents:
                    raise ValidationError(f"Intent node '{node_id}' missing 'intents'")
                for intent in node.intents:
                    goto = intent.get("goto") if isinstance(intent, dict) else None
                    if goto and goto not in all_ids:
                        raise ValidationError(
                            f"Intent node '{node_id}' references unknown node '{goto}'"
                        )
                if node.otherwise and node.otherwise not in all_ids:
                    raise ValidationError(
                        f"Intent node '{node_id}' references unknown node "
                        f"'{node.otherwise}'"
                    )

            if node.type == NodeType.ASK and not node.question:
                raise ValidationError(f"Ask node '{node_id}' missing 'question'")

            if node.type == NodeType.CODE and not node.code:
                raise ValidationError(f"Code node '{node_id}' missing 'code'")
            if node.type == NodeType.CODE and node.language != "python":
                raise ValidationError(
                    f"Code node '{node_id}' only supports 'python', "
                    f"got '{node.language}'"
                )

            if node.type == NodeType.DATABASE:
                action = node.db_action
                if action not in {"query", "insert", "update", "delete", "execute"}:
                    raise ValidationError(
                        f"Database node '{node_id}' has unknown db_action '{action}'"
                    )
                if not node.sql and not node.table:
                    raise ValidationError(
                        f"Database node '{node_id}' needs 'sql' or 'table'"
                    )
                if action in {"insert", "update"} and not node.values:
                    raise ValidationError(
                        f"Database node '{node_id}' {action} needs 'values'"
                    )
                if action in {"update", "delete"} and not node.where and not node.allow_all:
                    raise ValidationError(
                        f"Database node '{node_id}' {action} needs 'where' "
                        f"(or allow_all: true)"
                    )

            if node.type == NodeType.TEXT and not node.text_action:
                raise ValidationError(f"Text node '{node_id}' missing 'text_action'")

    def _validate_variables(self, workflow: WorkflowDefinition) -> None:
        """Validate variable definitions."""
        for var_name, var_def in workflow.variables.items():
            if var_def.enum and var_def.default is not None and var_def.default not in var_def.enum:
                raise ValidationError(
                    f"Variable '{var_name}' default value not in enum"
                )

    def _validate_schedule(self, workflow: WorkflowDefinition) -> None:
        """Validate the optional schedule trigger section."""
        sched = workflow.schedule
        if not sched:
            return
        if not isinstance(sched, dict):
            raise ValidationError("Workflow 'schedule' must be a mapping")
        if sched.get("enabled"):
            try:
                interval = float(sched.get("interval_seconds", 0))
            except (TypeError, ValueError):
                raise ValidationError(
                    "Schedule 'interval_seconds' must be a number"
                )
            if interval < 10:
                raise ValidationError(
                    "Schedule 'interval_seconds' must be >= 10"
                )

    def _validate_tiers(self, workflow: WorkflowDefinition) -> None:
        """Validate tier references."""
        defined_tiers = set(workflow.tiers.keys())
        if defined_tiers:
            for node_id, node in workflow.nodes.items():
                if node.tier and node.tier not in defined_tiers:
                    raise ValidationError(
                        f"Node '{node_id}' references undefined tier '{node.tier}'"
                    )
            for tier_name, tier_def in workflow.tiers.items():
                if tier_def.parent and tier_def.parent not in defined_tiers:
                    raise ValidationError(
                        f"Tier '{tier_name}' references undefined parent '{tier_def.parent}'"
                    )
