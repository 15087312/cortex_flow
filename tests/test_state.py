"""Tests for state management."""

import pytest

from cortexflow.state.blackboard import Blackboard
from cortexflow.state.checkpoint import Checkpoint, CheckpointStore
from cortexflow.state.variables import VariableScope


def test_blackboard_goal():
    """Test blackboard goal."""
    bb = Blackboard()
    bb.set_goal("Test goal")
    assert bb.get_goal() == "Test goal"


def test_blackboard_observations():
    """Test blackboard observations."""
    bb = Blackboard()
    bb.add_observation("large", "Observation 1")
    bb.add_observation("expert", "Observation 2")
    obs = bb.get_observations()
    assert len(obs) == 2
    obs_large = bb.get_observations(tier="large")
    assert len(obs_large) == 1


def test_blackboard_snapshot():
    """Test blackboard snapshot."""
    bb = Blackboard()
    bb.set_goal("Test")
    bb.add_observation("large", "Obs 1")
    bb.add_observation("expert", "Obs 2")
    snapshot = bb.snapshot_for("expert")
    assert snapshot["goal"] == "Test"
    assert len(snapshot["observations"]) == 2  # Expert sees all in this simple impl


def test_variable_scope():
    """Test variable scope."""
    scope = VariableScope()
    scope.set("x", 1, scope="global")
    scope.set("x", 2, scope="node")
    assert scope.get("x") == 2  # Node scope takes precedence
    scope.clear_node_scope()
    assert scope.get("x") == 1  # Falls back to global


def test_variable_scope_nested():
    """Test nested variable access."""
    scope = VariableScope()
    scope.set("data.nested.value", 42, scope="global")
    assert scope.get("data.nested.value") == 42


@pytest.mark.asyncio
async def test_checkpoint_store():
    """Test checkpoint store."""
    store = CheckpointStore()
    checkpoint = Checkpoint(
        flow_id="test_flow",
        flow_state="suspended",
        node_states={},
        variables={"x": 1},
        blackboard_snapshot={},
        current_node="node1",
        pending_events=["event1"],
        created_at=None,
    )
    from datetime import UTC, datetime

    checkpoint.created_at = datetime.now(UTC)
    await store.save(checkpoint)
    loaded = await store.load("test_flow")
    assert loaded is not None
    assert loaded.flow_id == "test_flow"
    assert loaded.variables["x"] == 1
    await store.delete("test_flow")
    loaded = await store.load("test_flow")
    assert loaded is None
