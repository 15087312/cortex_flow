"""Workflow executor - Core execution engine with lifecycle support."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from cortexflow.compiler.ir import FlowIR, NodeIR
from cortexflow.events.types import Event, EventType
from cortexflow.runtime.context import ExecutionContext, FlowState, NodeState
from cortexflow.runtime.dispatcher import NodeDispatcher
from cortexflow.runtime.events import AskQuestion, LoopBreak, LoopContinue, WaitEvent
from cortexflow.state.checkpoint import Checkpoint, CheckpointStore
from cortexflow.utils.snapshot import snapshot_value

logger = logging.getLogger(__name__)

__all__ = ["Executor"]


class Executor:
    """Execute workflows with events, tracing, metrics, retry, timeout, and suspend/resume."""

    def __init__(
        self,
        event_bus: Any = None,
        tracer: Any = None,
        metrics: Any = None,
        checkpoint_store: CheckpointStore | None = None,
        persist_checkpoints: bool = True,
    ):
        self.dispatcher = NodeDispatcher()
        self.event_bus = event_bus
        self.tracer = tracer
        self.metrics = metrics
        self.checkpoint_store = checkpoint_store or CheckpointStore()
        # Editor dry-runs flip this off so they never leave resumable state.
        self.persist_checkpoints = persist_checkpoints
        self._subflow_registry: dict[str, FlowIR] = {}

    def register_subflow(self, flow_id: str, flow_ir: FlowIR) -> None:
        """Register a sub-workflow for subflow node execution."""
        self._subflow_registry[flow_id] = flow_ir

    async def execute(self, flow: FlowIR, context: ExecutionContext) -> Any:
        """Execute a workflow from entry to completion."""
        context.executor = self
        context.flow_id = flow.id
        context.state = FlowState.RUNNING
        flow_start = time.monotonic()

        await self._publish(EventType.FLOW_STARTED, {"flow_id": flow.id})

        current_node = flow.entry
        try:
            while current_node:
                node_ir = flow.nodes[current_node]
                context.current_node = current_node
                context.node_states[current_node] = NodeState.ACTIVE

                try:
                    result = await self._execute_with_lifecycle(node_ir, context)
                except WaitEvent:
                    raise
                except Exception:
                    context.node_states[current_node] = NodeState.FAILED
                    if node_ir.on_error and node_ir.on_error in flow.nodes:
                        current_node = node_ir.on_error
                        continue
                    raise

                context.node_states[current_node] = NodeState.COMPLETED

                if node_ir.config.get("output"):
                    context.set_variable(node_ir.config["output"], result)

                if isinstance(result, str) and node_ir.type in ("branch", "intent") and result in flow.nodes:
                    current_node = result
                elif node_ir.type == "loop" and node_ir.config.get("on_complete"):
                    target = node_ir.config["on_complete"]
                    current_node = target if target != "__end__" else None
                else:
                    next_node = node_ir.on_success
                    current_node = next_node if next_node and next_node != "__end__" else None

        except WaitEvent as e:
            context.node_states[context.current_node] = NodeState.WAITING
            context.state = FlowState.SUSPENDED
            await self._publish(EventType.FLOW_SUSPENDED, {
                "flow_id": flow.id,
                "node_id": context.current_node,
                "event_type": e.event_type,
                "filter": e.filter,
            })
            await self._save_checkpoint(context, e)
            raise

        except Exception as exc:
            context.state = FlowState.FAILED
            await self._publish(EventType.FLOW_FAILED, {
                "flow_id": flow.id,
                "error": str(exc),
            })
            if self.metrics:
                self.metrics.record_flow_completion(time.monotonic() - flow_start)
            raise

        context.state = FlowState.COMPLETED
        if self.metrics:
            self.metrics.record_flow_completion(time.monotonic() - flow_start)
        await self._publish(EventType.FLOW_COMPLETED, {"flow_id": flow.id})
        return context.variables.get("result")

    async def execute_sub_node(
        self, node_id: str, context: ExecutionContext, *, follow_chain: bool = True
    ) -> Any:
        """Execute a sub-node by ID (for loop/parallel/map body dispatch).

        If *follow_chain* is True (default), follows on_success routing until
        __end__ — used by parallel branches.  Set to False for loop/map bodies
        that should execute exactly one node.
        """
        if follow_chain:
            return await self._execute_node_chain(node_id, context)
        return await self._execute_single_node(node_id, context)

    async def execute_subflow(
        self,
        flow_id: str,
        input_variables: dict[str, Any],
        parent_context: ExecutionContext,
        share_blackboard: bool = False,
    ) -> Any:
        """Execute a sub-workflow."""
        sub_flow = self._subflow_registry.get(flow_id)
        if not sub_flow:
            raise ValueError(f"Unknown subflow: {flow_id}")

        sub_ctx = parent_context.clone()
        sub_ctx.variables.update(input_variables)
        sub_ctx.flow_id = f"{parent_context.flow_id}/{flow_id}"
        sub_ctx.node_states = {}
        sub_ctx.state = FlowState.PENDING
        if not share_blackboard:
            from cortexflow.state.blackboard import Blackboard
            sub_ctx.blackboard = Blackboard()

        return await self.execute(sub_flow, sub_ctx)

    async def resume(self, flow_id: str, event: Event, context: ExecutionContext) -> Any:
        """Resume a suspended workflow after an event arrives."""
        context.executor = self
        context.state = FlowState.RUNNING
        await self._publish(EventType.FLOW_RESUMED, {"flow_id": flow_id})

        node_id = context.current_node
        if not node_id:
            raise ValueError("No current node to resume")

        for nid, ns in context.node_states.items():
            if ns == NodeState.WAITING:
                node_id = nid
                break

        context.node_states[node_id] = NodeState.ACTIVE
        context.set_variable("_wait_event_result", event.payload)

        # Ask nodes: deliver the answer into its output variable.
        ask_config = context.metadata.get(f"_ask_{node_id}", {})
        if ask_config:
            payload = event.payload
            if isinstance(payload, dict) and "answer" in payload:
                payload = payload["answer"]
            context.set_variable(ask_config.get("answer_var", "answer"), payload)

        try:
            wait_config = context.metadata.get(f"_wait_config_{node_id}", {})
            on_event = wait_config.get("on_event")

            if on_event:
                context.current_node = on_event
                return await self._continue_from(context, node_id)
            else:
                raise ValueError("Wait node has no on_event target")

        except Exception as exc:
            context.state = FlowState.FAILED
            await self._publish(EventType.FLOW_FAILED, {
                "flow_id": flow_id,
                "error": str(exc),
            })
            raise

    # ── Internal: lifecycle ───────────────────────────────────────

    async def _execute_with_lifecycle(self, node_ir: NodeIR, context: ExecutionContext) -> Any:
        """Execute a single node with retry, timeout, tracing, events, metrics."""
        retry_max = node_ir.config.get("retry", {}).get("max_retries", 0)
        retry_delay = node_ir.config.get("retry", {}).get("delay", 1.0)
        retry_backoff = node_ir.config.get("retry", {}).get("backoff", 2.0)
        timeout = node_ir.config.get("timeout")

        await self._publish(EventType.NODE_STARTED, {
            "flow_id": context.flow_id,
            "node_id": node_ir.id,
            "node_type": node_ir.type,
        })

        trace = None
        if self.tracer:
            trace = await self.tracer.trace_node(
                flow_id=context.flow_id,
                node_id=node_ir.id,
                node_type=node_ir.type,
                input_summary={"config": snapshot_value(node_ir.config)},
            )

        start = time.monotonic()
        last_exc: Exception | None = None

        for attempt in range(retry_max + 1):
            try:
                if timeout:
                    async with asyncio.timeout(timeout):
                        result = await self.dispatcher.dispatch(node_ir, context)
                else:
                    result = await self.dispatcher.dispatch(node_ir, context)

                duration = time.monotonic() - start
                if self.metrics:
                    self.metrics.record_node_duration(node_ir.type, duration)
                if self.tracer and trace:
                    await self.tracer.complete_trace(
                        flow_id=context.flow_id,
                        node_id=node_ir.id,
                        output_summary={"result": snapshot_value(result)},
                    )
                await self._publish(EventType.NODE_COMPLETED, {
                    "flow_id": context.flow_id,
                    "node_id": node_ir.id,
                    "duration": duration,
                })
                return result

            except WaitEvent as w:
                context.metadata[f"_wait_config_{node_ir.id}"] = {
                    "on_event": node_ir.config.get("on_event"),
                    "on_timeout": node_ir.config.get("on_timeout"),
                }
                if isinstance(w, AskQuestion):
                    context.metadata[f"_ask_{node_ir.id}"] = {
                        "question": w.question,
                        "answer_var": w.answer_var,
                    }
                if self.tracer and trace:
                    await self.tracer.complete_trace(
                        flow_id=context.flow_id,
                        node_id=node_ir.id,
                        state="waiting",
                    )
                raise

            except (LoopBreak, LoopContinue) as flow_signal:
                # Control-flow signals for loop bodies: not errors, no retry.
                # A stray signal with no enclosing loop surfaces as flow
                # failure via the generic handler in execute().
                if self.tracer and trace:
                    await self.tracer.complete_trace(
                        flow_id=context.flow_id,
                        node_id=node_ir.id,
                        output_summary={
                            "control": "break"
                            if isinstance(flow_signal, LoopBreak)
                            else "continue"
                        },
                    )
                raise

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if self.metrics:
                    self.metrics.record_error(node_ir.type)
                if attempt < retry_max:
                    delay = retry_delay * (retry_backoff ** attempt)
                    logger.warning(
                        "Node %s attempt %d failed: %s — retrying in %.1fs",
                        node_ir.id, attempt + 1, exc, delay,
                    )
                    await asyncio.sleep(delay)

        if self.tracer and trace:
            await self.tracer.complete_trace(
                flow_id=context.flow_id,
                node_id=node_ir.id,
                state="failed",
                error=str(last_exc),
            )
        await self._publish(EventType.NODE_FAILED, {
            "flow_id": context.flow_id,
            "node_id": node_ir.id,
            "error": str(last_exc),
        })
        raise last_exc  # type: ignore[misc]

    # ── Internal: chain / single execution ────────────────────────

    async def _execute_node_chain(self, start_node_id: str, context: ExecutionContext) -> Any:
        """Execute a chain of nodes following on_success and branch routing."""
        current = start_node_id
        result = None
        while current:
            node_ir = self._lookup_node(current, context)
            if not node_ir:
                break
            context.node_states[current] = NodeState.ACTIVE
            result = await self._execute_with_lifecycle(node_ir, context)
            context.node_states[current] = NodeState.COMPLETED
            if node_ir.config.get("output"):
                context.set_variable(node_ir.config["output"], result)
            if isinstance(result, str) and node_ir.type in ("branch", "intent") and self._lookup_node(result, context) is not None:
                current = result
            elif node_ir.type == "loop" and node_ir.config.get("on_complete"):
                target = node_ir.config["on_complete"]
                current = target if target != "__end__" else None
            else:
                nxt = node_ir.on_success
                current = nxt if nxt and nxt != "__end__" else None
        return result

    async def _execute_single_node(self, node_id: str, context: ExecutionContext) -> Any:
        """Execute exactly one node without following routing."""
        node_ir = self._lookup_node(node_id, context)
        if not node_ir:
            raise ValueError(f"Node not found: {node_id}")
        context.node_states[node_id] = NodeState.ACTIVE
        result = await self._execute_with_lifecycle(node_ir, context)
        context.node_states[node_id] = NodeState.COMPLETED
        if node_ir.config.get("output"):
            context.set_variable(node_ir.config["output"], result)
        return result

    async def _continue_from(self, context: ExecutionContext, after_node: str) -> Any:
        """Continue execution from a target node (used after resume)."""
        current = context.current_node
        result = None
        while current:
            node_ir = self._lookup_node(current, context)
            if not node_ir:
                break
            context.node_states[current] = NodeState.ACTIVE
            result = await self._execute_with_lifecycle(node_ir, context)
            context.node_states[current] = NodeState.COMPLETED
            if node_ir.config.get("output"):
                context.set_variable(node_ir.config["output"], result)
            if isinstance(result, str) and node_ir.type in ("branch", "intent"):
                target = self._lookup_node(result, context)
                if target is not None:
                    current = result
                    continue
            if node_ir.type == "loop" and node_ir.config.get("on_complete"):
                target = node_ir.config["on_complete"]
                current = target if target != "__end__" else None
                continue
            nxt = node_ir.on_success
            current = nxt if nxt and nxt != "__end__" else None
        context.state = FlowState.COMPLETED
        return result

    def _lookup_node(self, node_id: str, context: ExecutionContext) -> NodeIR | None:
        """Look up a NodeIR from the flow stored in metadata."""
        flow: FlowIR | None = context.metadata.get("_flow")
        if flow and node_id in flow.nodes:
            return flow.nodes[node_id]
        return None

    # ── Internal: suspend / checkpoint ────────────────────────────

    async def _save_checkpoint(self, context: ExecutionContext, wait_event: WaitEvent) -> None:
        if not self.persist_checkpoints:
            return
        checkpoint = Checkpoint(
            flow_id=context.flow_id,
            workflow_id=context.flow_id.split("/")[0],
            definition=dict(context.metadata.get("_definition") or {}),
            flow_state=context.state,
            node_states=dict(context.node_states),
            variables=dict(context.variables),
            blackboard_snapshot=context.blackboard.to_dict(),
            current_node=context.current_node,
            pending_events=[wait_event.event_type],
            created_at=datetime.now(UTC),
            metadata=dict(context.metadata),
        )
        await self.checkpoint_store.save(checkpoint)

    # ── Internal: event helpers ───────────────────────────────────

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_bus:
            await self.event_bus.publish(Event(type=event_type, payload=payload))
