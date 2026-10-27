"""Tests for executor - lifecycle, events, tracing, metrics, retry, timeout, branch routing."""

import asyncio

import pytest

from cortexflow.compiler.ir import BlackboardConfigIR, FlowIR, NodeIR
from cortexflow.events.bus import EventBus
from cortexflow.events.types import EventType
from cortexflow.observability.metrics import MetricsCollector
from cortexflow.observability.tracer import Tracer
from cortexflow.runtime.context import ExecutionContext, FlowState, NodeState
from cortexflow.runtime.events import WaitEvent
from cortexflow.runtime.executor import Executor


def _make_flow(nodes: dict[str, NodeIR], entry: str = "start") -> FlowIR:
    return FlowIR(
        id="test_flow",
        name="Test",
        entry=entry,
        nodes=nodes,
        edges={},
        variables={},
        blackboard_config=BlackboardConfigIR(enabled=False, visibility={}),
        tiers={},
        metadata={},
    )


def _state_node(node_id: str, on_success: str = "__end__", **extra) -> NodeIR:
    config = {
        "type": "state",
        "actions": extra.get("actions", [{"action": "set", "target": "result", "value": node_id}]),
    }
    config.update(extra)
    return NodeIR(
        id=node_id,
        type="state",
        config=config,
        on_success=on_success,
        on_error=None,
        resolved_tier="default",
        resolved_identity="default",
    )


@pytest.mark.asyncio
async def test_execute_simple_flow():
    flow = _make_flow({"start": _state_node("start")})
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()
    await executor.execute(flow, ctx)
    assert ctx.state == FlowState.COMPLETED
    assert ctx.variables.get("result") == "start"


@pytest.mark.asyncio
async def test_execute_chain():
    nodes = {
        "a": _state_node("a", on_success="b", actions=[{"action": "set", "target": "a_done", "value": True}]),
        "b": _state_node("b", on_success="__end__", actions=[{"action": "set", "target": "b_done", "value": True}]),
    }
    flow = _make_flow(nodes, entry="a")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()
    await executor.execute(flow, ctx)
    assert ctx.state == FlowState.COMPLETED
    assert ctx.variables.get("a_done") is True
    assert ctx.variables.get("b_done") is True


@pytest.mark.asyncio
async def test_branch_routing():
    nodes = {
        "decide": NodeIR(
            id="decide",
            type="branch",
            config={
                "type": "branch",
                "mode": "expression",
                "conditions": [
                    {"when": "${x} == 1", "goto": "path_a"},
                    {"otherwise": "path_b"},
                ],
            },
            on_success="path_b",
            on_error=None,
            resolved_tier="default",
            resolved_identity="default",
        ),
        "path_a": _state_node("path_a", actions=[{"action": "set", "target": "chosen", "value": "a"}]),
        "path_b": _state_node("path_b", actions=[{"action": "set", "target": "chosen", "value": "b"}]),
    }
    flow = _make_flow(nodes, entry="decide")
    ctx = ExecutionContext(variables={"x": 1})
    ctx.metadata["_flow"] = flow
    executor = Executor()
    await executor.execute(flow, ctx)
    assert ctx.variables.get("chosen") == "a"


@pytest.mark.asyncio
async def test_events_published():
    events_received = []
    bus = EventBus()
    await bus.subscribe(EventType.FLOW_STARTED, lambda e: events_received.append(e))
    await bus.subscribe(EventType.FLOW_COMPLETED, lambda e: events_received.append(e))
    await bus.subscribe(EventType.NODE_STARTED, lambda e: events_received.append(e))
    await bus.subscribe(EventType.NODE_COMPLETED, lambda e: events_received.append(e))

    flow = _make_flow({"start": _state_node("start")})
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor(event_bus=bus)
    await executor.execute(flow, ctx)

    types = [e.type for e in events_received]
    assert EventType.FLOW_STARTED in types
    assert EventType.FLOW_COMPLETED in types
    assert EventType.NODE_STARTED in types
    assert EventType.NODE_COMPLETED in types


@pytest.mark.asyncio
async def test_tracing():
    tracer = Tracer()
    flow = _make_flow({"start": _state_node("start")})
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor(tracer=tracer)
    await executor.execute(flow, ctx)

    traces = await tracer.get_trace("test_flow")
    assert len(traces) >= 1
    assert traces[0].node_id == "start"
    assert traces[0].state == "completed"


@pytest.mark.asyncio
async def test_metrics():
    metrics = MetricsCollector()
    flow = _make_flow({"start": _state_node("start")})
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor(metrics=metrics)
    await executor.execute(flow, ctx)

    stats = metrics.get_stats()
    assert stats["flows_completed"] == 1
    assert "state" in stats["node_counts"]


@pytest.mark.asyncio
async def test_retry_on_failure():
    call_count = 0

    from cortexflow.nodes.registry import NodeRegistry

    @NodeRegistry.register("_test_flaky")
    class FlakyNode:
        def __init__(self, node_id, config):
            self.node_id = node_id
            self.config = config

        async def execute(self, context):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return "success"

    node_ir = NodeIR(
        id="flaky",
        type="_test_flaky",
        config={"retry": {"max_retries": 3, "delay": 0.01, "backoff": 1}},
        on_success="__end__",
        on_error=None,
        resolved_tier="default",
        resolved_identity="default",
    )
    flow = _make_flow({"flaky": node_ir}, entry="flaky")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()
    await executor.execute(flow, ctx)
    assert call_count == 3
    assert ctx.state == FlowState.COMPLETED

    del NodeRegistry._registry["_test_flaky"]


@pytest.mark.asyncio
async def test_timeout_enforcement():
    from cortexflow.nodes.registry import NodeRegistry

    @NodeRegistry.register("_test_slow")
    class SlowNode:
        def __init__(self, node_id, config):
            self.node_id = node_id
            self.config = config

        async def execute(self, context):
            await asyncio.sleep(10)
            return "done"

    node_ir = NodeIR(
        id="slow",
        type="_test_slow",
        config={"timeout": 0.1},
        on_success="__end__",
        on_error=None,
        resolved_tier="default",
        resolved_identity="default",
    )
    flow = _make_flow({"slow": node_ir}, entry="slow")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await executor.execute(flow, ctx)
    assert ctx.state == FlowState.FAILED

    del NodeRegistry._registry["_test_slow"]


@pytest.mark.asyncio
async def test_suspend_on_wait_event():
    from cortexflow.nodes.registry import NodeRegistry

    @NodeRegistry.register("_test_wait")
    class TestWaitNode:
        def __init__(self, node_id, config):
            self.node_id = node_id
            self.config = config

        async def execute(self, context):
            raise WaitEvent("user_approval", {"id": "123"})

    node_ir = NodeIR(
        id="waiter",
        type="_test_wait",
        config={"event": "user_approval", "on_event": "next", "on_timeout": "timeout"},
        on_success="next",
        on_error=None,
        resolved_tier="default",
        resolved_identity="default",
    )
    flow = _make_flow({"waiter": node_ir}, entry="waiter")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()

    with pytest.raises(WaitEvent):
        await executor.execute(flow, ctx)

    assert ctx.state == FlowState.SUSPENDED
    checkpoint = await executor.checkpoint_store.load("test_flow")
    assert checkpoint is not None
    assert checkpoint.current_node == "waiter"

    del NodeRegistry._registry["_test_wait"]


@pytest.mark.asyncio
async def test_execute_sub_node_single():
    nodes = {
        "body": _state_node("body", on_success="next", actions=[{"action": "set", "target": "body_ran", "value": True}]),
        "next": _state_node("next", actions=[{"action": "set", "target": "next_ran", "value": True}]),
    }
    flow = _make_flow(nodes, entry="body")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()

    await executor.execute_sub_node("body", ctx, follow_chain=False)
    assert ctx.variables.get("body_ran") is True
    assert ctx.variables.get("next_ran") is None


@pytest.mark.asyncio
async def test_execute_sub_node_chain():
    nodes = {
        "body": _state_node("body", on_success="next", actions=[{"action": "set", "target": "body_ran", "value": True}]),
        "next": _state_node("next", on_success="__end__", actions=[{"action": "set", "target": "next_ran", "value": True}]),
    }
    flow = _make_flow(nodes, entry="body")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()

    await executor.execute_sub_node("body", ctx, follow_chain=True)
    assert ctx.variables.get("body_ran") is True
    assert ctx.variables.get("next_ran") is True


@pytest.mark.asyncio
async def test_on_error_routing():
    from cortexflow.nodes.registry import NodeRegistry

    @NodeRegistry.register("_test_fail")
    class FailNode:
        def __init__(self, node_id, config):
            self.node_id = node_id
            self.config = config

        async def execute(self, context):
            raise RuntimeError("intentional")

    nodes = {
        "fail": NodeIR(
            id="fail",
            type="_test_fail",
            config={},
            on_success="should_not_reach",
            on_error="handler",
            resolved_tier="default",
            resolved_identity="default",
        ),
        "should_not_reach": _state_node("should_not_reach"),
        "handler": _state_node("handler", actions=[{"action": "set", "target": "handled", "value": True}]),
    }
    flow = _make_flow(nodes, entry="fail")
    ctx = ExecutionContext()
    ctx.metadata["_flow"] = flow
    executor = Executor()

    await executor.execute(flow, ctx)

    assert ctx.node_states["fail"] == NodeState.FAILED
    assert ctx.node_states["handler"] == NodeState.COMPLETED
    assert ctx.variables.get("handled") is True
    assert ctx.state == FlowState.COMPLETED

    del NodeRegistry._registry["_test_fail"]
