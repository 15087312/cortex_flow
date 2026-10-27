"""Tests for nodes - branch, loop, parallel, map, wait, perception, subflow."""

import pytest

from cortexflow.nodes.branch import BranchNode
from cortexflow.nodes.loop import LoopNode
from cortexflow.nodes.map import MapNode
from cortexflow.nodes.parallel import ParallelNode
from cortexflow.nodes.perception import PerceptionNode
from cortexflow.nodes.state import StateNode
from cortexflow.nodes.wait import WaitNode
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.events import WaitEvent


@pytest.mark.asyncio
async def test_branch_expression_true():
    node = BranchNode("b", {
        "mode": "expression",
        "conditions": [
            {"when": "${x} == 1", "goto": "path_a"},
            {"otherwise": "path_b"},
        ],
    })
    ctx = ExecutionContext(variables={"x": 1})
    result = await node.execute(ctx)
    assert result == "path_a"


@pytest.mark.asyncio
async def test_branch_expression_otherwise():
    node = BranchNode("b", {
        "mode": "expression",
        "conditions": [
            {"when": "${x} == 99", "goto": "path_a"},
            {"otherwise": "path_b"},
        ],
    })
    ctx = ExecutionContext(variables={"x": 2})
    result = await node.execute(ctx)
    assert result == "path_b"


@pytest.mark.asyncio
async def test_loop_count():
    node = LoopNode("loop", {
        "loop_mode": "count",
        "count": 3,
        "iterator_var": "i",
    })
    ctx = ExecutionContext()
    result = await node.execute(ctx)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_loop_foreach():
    node = LoopNode("loop", {
        "loop_mode": "foreach",
        "items": "${items}",
        "item_var": "cur",
    })
    ctx = ExecutionContext(variables={"items": [10, 20, 30]})
    result = await node.execute(ctx)
    assert result == [10, 20, 30]


@pytest.mark.asyncio
async def test_loop_foreach_with_index():
    node = LoopNode("loop", {
        "loop_mode": "foreach",
        "items": "${items}",
        "item_var": "cur",
        "index_var": "idx",
    })
    ctx = ExecutionContext(variables={"items": ["a", "b"]})
    result = await node.execute(ctx)
    assert result == ["a", "b"]
    assert ctx.get_variable("idx") == 1


@pytest.mark.asyncio
async def test_loop_condition():
    node = LoopNode("loop", {
        "loop_mode": "condition",
        "condition": "${counter} < 3",
        "iterator_var": "i",
    })
    ctx = ExecutionContext(variables={"counter": 5})
    result = await node.execute(ctx)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_loop_break_condition():
    node = LoopNode("loop", {
        "loop_mode": "foreach",
        "items": "${items}",
        "item_var": "cur",
        "break_condition": "${cur} == 20",
    })
    ctx = ExecutionContext(variables={"items": [10, 20, 30]})
    result = await node.execute(ctx)
    assert result == [10]


@pytest.mark.asyncio
async def test_loop_continue_condition():
    node = LoopNode("loop", {
        "loop_mode": "foreach",
        "items": "${items}",
        "item_var": "cur",
        "continue_condition": "${cur} == 20",
    })
    ctx = ExecutionContext(variables={"items": [10, 20, 30]})
    result = await node.execute(ctx)
    assert result == [10, 30]


@pytest.mark.asyncio
async def test_parallel_no_executor():
    node = ParallelNode("p", {
        "branches": ["a", "b"],
        "strategy": "all",
    })
    ctx = ExecutionContext()
    result = await node.execute(ctx)
    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_map_no_executor():
    node = MapNode("m", {
        "collection": "${items}",
        "element_var": "el",
    })
    ctx = ExecutionContext(variables={"items": [1, 2, 3]})
    result = await node.execute(ctx)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_wait_node_raises():
    node = WaitNode("w", {
        "event": "user_approval",
        "filter": {"id": "${req_id}"},
    })
    ctx = ExecutionContext(variables={"req_id": "abc"})
    with pytest.raises(WaitEvent) as exc_info:
        await node.execute(ctx)
    assert exc_info.value.event_type == "user_approval"
    assert exc_info.value.filter == {"id": "abc"}


@pytest.mark.asyncio
async def test_perception_node_mock():
    node = PerceptionNode("p", {
        "source": "screen",
        "config": {"interval": 1},
    })
    ctx = ExecutionContext()
    result = await node.execute(ctx)
    assert result["source"] == "screen"
    assert "data" in result


@pytest.mark.asyncio
async def test_perception_write_blackboard():
    node = PerceptionNode("p", {
        "source": "screen",
        "write_to_blackboard": True,
        "tier": "observer",
    })
    ctx = ExecutionContext()
    await node.execute(ctx)
    obs = ctx.blackboard.get_observations()
    assert len(obs) == 1


@pytest.mark.asyncio
async def test_state_node_append():
    node = StateNode("s", {
        "actions": [
            {"action": "append", "target": "items", "value": "a"},
            {"action": "append", "target": "items", "value": "b"},
        ],
    })
    ctx = ExecutionContext()
    await node.execute(ctx)
    assert ctx.get_variable("items") == ["a", "b"]


@pytest.mark.asyncio
async def test_state_node_resolve():
    node = StateNode("s", {
        "actions": [
            {"action": "set", "target": "out", "value": "${inp}"},
        ],
    })
    ctx = ExecutionContext(variables={"inp": "resolved_value"})
    await node.execute(ctx)
    assert ctx.get_variable("out") == "resolved_value"
