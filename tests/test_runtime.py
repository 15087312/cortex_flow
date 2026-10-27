"""Tests for runtime layer - context, executor, events."""


from cortexflow.runtime.context import ExecutionContext, FlowState, NodeState


def test_execution_context_creation():
    ctx = ExecutionContext(flow_id="test_flow")
    assert ctx.flow_id == "test_flow"
    assert ctx.state == FlowState.PENDING
    assert ctx.current_node is None


def test_flow_state_transitions():
    ctx = ExecutionContext(flow_id="test_flow")
    assert ctx.state == FlowState.PENDING
    ctx.state = FlowState.RUNNING
    assert ctx.state == FlowState.RUNNING
    ctx.state = FlowState.COMPLETED
    assert ctx.state == FlowState.COMPLETED


def test_node_state_tracking():
    ctx = ExecutionContext(flow_id="test_flow")
    ctx.node_states["start"] = NodeState.ACTIVE
    assert ctx.node_states["start"] == NodeState.ACTIVE
    ctx.node_states["start"] = NodeState.COMPLETED
    assert ctx.node_states["start"] == NodeState.COMPLETED


def test_variable_resolution():
    ctx = ExecutionContext(flow_id="test_flow")
    ctx.set_variable("user", {"name": "Alice", "age": 30})
    assert ctx.get_variable("user.name") == "Alice"
    assert ctx.get_variable("user.age") == 30


def test_variable_default_value():
    ctx = ExecutionContext(flow_id="test_flow")
    assert ctx.get_variable("missing.path", default="fallback") == "fallback"


def test_blackboard_integration():
    ctx = ExecutionContext(flow_id="test_flow")
    ctx.blackboard.set_goal("Test goal")
    assert ctx.blackboard.get_goal() == "Test goal"


def test_metadata():
    ctx = ExecutionContext(flow_id="test_flow")
    ctx.metadata["key"] = "value"
    assert ctx.metadata["key"] == "value"


def test_context_clone():
    ctx = ExecutionContext(flow_id="test_flow", variables={"x": 1})
    ctx.adapters["model"] = "mock_adapter"
    clone = ctx.clone()
    assert clone.flow_id == "test_flow"
    assert clone.variables["x"] == 1
    assert clone.adapters["model"] == "mock_adapter"
    clone.variables["x"] = 2
    assert ctx.variables["x"] == 1


def test_context_get_adapter():
    ctx = ExecutionContext()
    ctx.adapters["model"] = "test_adapter"
    assert ctx.get_adapter("model") == "test_adapter"
    assert ctx.get_adapter("missing") is None


def test_set_variable_nested():
    ctx = ExecutionContext()
    ctx.set_variable("a.b.c", 42)
    assert ctx.get_variable("a.b.c") == 42
    assert ctx.get_variable("a.b") == {"c": 42}
