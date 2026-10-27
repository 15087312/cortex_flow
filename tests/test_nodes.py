"""Tests for nodes - registry, model, state."""

import pytest

from cortexflow.nodes.model import ModelNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.nodes.state import StateNode
from cortexflow.runtime.context import ExecutionContext


def test_node_registry():
    types = NodeRegistry.list_types()
    assert "model" in types
    assert "state" in types
    assert "tool" in types
    assert "branch" in types
    assert "loop" in types
    assert "parallel" in types
    assert "map" in types
    assert "wait" in types
    assert "subflow" in types
    assert "perception" in types


@pytest.mark.asyncio
async def test_model_node_mock():
    node = ModelNode(
        node_id="test",
        config={
            "tier": "default",
            "identity": "assistant",
            "custom_system": "You are helpful.",
            "input": {"text": "hello"},
        },
    )
    context = ExecutionContext()
    result = await node.execute(context)
    # Contract: the node returns the model *content* (unwrapped from the
    # adapter envelope), not the envelope dict itself.
    assert result == "Mock response from default/assistant"


@pytest.mark.asyncio
async def test_model_node_with_composer():
    class FakeComposer:
        def build_system(self, context):
            return f"System for {context['identity']}"

    node = ModelNode(
        node_id="test",
        config={
            "tier": "default",
            "identity": "bot",
            "prompt_strategy": "system_from_composer",
            "input": {"text": "hi"},
        },
    )
    context = ExecutionContext()
    context.adapters["prompt_composer"] = FakeComposer()
    result = await node.execute(context)
    assert "output" in result or "response" in result


@pytest.mark.asyncio
async def test_state_node_set():
    node = StateNode(
        node_id="test",
        config={
            "actions": [{"action": "set", "target": "my_var", "value": "my_value"}]
        },
    )
    context = ExecutionContext()
    await node.execute(context)
    assert context.variables.get("my_var") == "my_value"


@pytest.mark.asyncio
async def test_state_node_read():
    node = StateNode(
        node_id="test",
        config={
            "actions": [{"action": "read", "source": "input", "output": "output"}]
        },
    )
    context = ExecutionContext(variables={"input": "test_value"})
    await node.execute(context)
    assert context.variables.get("output") == "test_value"


@pytest.mark.asyncio
async def test_state_node_resolve_variable():
    node = StateNode(
        node_id="test",
        config={
            "actions": [{"action": "set", "target": "out", "value": "${src}"}]
        },
    )
    context = ExecutionContext(variables={"src": "resolved"})
    await node.execute(context)
    assert context.variables.get("out") == "resolved"


def test_node_registry_create():
    node = NodeRegistry.create("state", "s1", {"actions": []})
    assert node.node_id == "s1"


def test_node_registry_unknown_type():
    with pytest.raises(ValueError, match="Unknown node type"):
        NodeRegistry.create("nonexistent_type", "n1", {})
