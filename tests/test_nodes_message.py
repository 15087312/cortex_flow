"""Tests for the message node (chat output) and its event."""

import pytest

from cortexflow.dsl.validator import ValidationError
from cortexflow.engine import Engine
from cortexflow.events.bus import EventBus
from cortexflow.nodes.message import MessageNode
from cortexflow.runtime.context import ExecutionContext


@pytest.mark.asyncio
async def test_message_node_renders_template_and_returns_text():
    node = MessageNode("m", {"message": "已处理 ${count} 条", "role": "assistant"})
    ctx = ExecutionContext(variables={"count": 3})
    assert await node.execute(ctx) == "已处理 3 条"


@pytest.mark.asyncio
async def test_message_node_appends_to_history():
    node = MessageNode("m", {"message": "hi"})
    ctx = ExecutionContext()
    await node.execute(ctx)
    await node.execute(ctx)
    assert ctx.get_variable("messages") == [
        {"role": "assistant", "content": "hi", "node_id": "m"},
        {"role": "assistant", "content": "hi", "node_id": "m"},
    ]


@pytest.mark.asyncio
async def test_message_node_publishes_event():
    bus = EventBus()
    received = []
    await bus.subscribe("*", lambda e: received.append(e))

    node = MessageNode("m", {"message": "hello", "role": "user"})
    await node.execute(ExecutionContext(flow_id="f1", event_bus=bus))

    assert len(received) == 1
    assert received[0].type == "flow.message"
    assert received[0].payload == {
        "flow_id": "f1",
        "node_id": "m",
        "role": "user",
        "content": "hello",
    }


@pytest.mark.asyncio
async def test_message_node_serialises_non_string_payloads():
    node = MessageNode("m", {"message": "${data}"})
    ctx = ExecutionContext(variables={"data": {"ok": True, "n": 1}})
    assert await node.execute(ctx) == '{"ok": true, "n": 1}'


@pytest.mark.asyncio
async def test_message_node_validates_role_and_content():
    with pytest.raises(ValueError, match="requires 'message'"):
        await MessageNode("m", {}).execute(ExecutionContext())
    with pytest.raises(ValueError, match="unknown role"):
        await MessageNode("m", {"message": "x", "role": "bot"}).execute(
            ExecutionContext()
        )


def test_validator_checks_message_nodes():
    engine = Engine()
    flow = """
id: m
name: m
entry: n
nodes:
  n:
    type: message
"""
    with pytest.raises(ValidationError, match="missing 'message'"):
        engine.compile(engine.load_from_string(flow))

    flow = """
id: m
name: m
entry: n
nodes:
  n:
    type: message
    message: hi
    role: bot
"""
    with pytest.raises(ValidationError, match="unknown role"):
        engine.compile(engine.load_from_string(flow))


async def test_message_node_in_workflow_streams_to_ui():
    engine = Engine()
    received = []
    await engine.event_bus.subscribe("*", lambda e: received.append(e))

    flow = """
id: chat
name: chat
entry: say
nodes:
  say:
    type: message
    role: assistant
    message: "结果是 ${value}"
    output: reply
    on_success: done
  done:
    type: end
    end_mode: variable
    return_value: ${reply}
"""
    result = await engine.run_string(flow, {"value": 42})
    assert result == "结果是 42"
    messages = [e for e in received if e.type == "flow.message"]
    assert messages and messages[0].payload["content"] == "结果是 42"
