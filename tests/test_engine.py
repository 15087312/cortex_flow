"""Tests for Engine integration."""

import pytest

from cortexflow.engine import Engine
from cortexflow.runtime.context import FlowState


@pytest.mark.asyncio
async def test_engine_run_state_flow():
    engine = Engine()
    yaml = """
id: "test"
name: "Test"
entry: "step1"
config:
  default_tier: "default"
nodes:
  step1:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "hello"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml)
    assert result == "hello"


@pytest.mark.asyncio
async def test_engine_run_with_variables():
    engine = Engine()
    yaml = """
id: "test"
name: "Test"
entry: "step1"
config:
  default_tier: "default"
nodes:
  step1:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "${input}"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml, context={"input": "world"})
    assert result == "world"


@pytest.mark.asyncio
async def test_engine_chain():
    engine = Engine()
    yaml = """
id: "test"
name: "Test"
entry: "a"
config:
  default_tier: "default"
nodes:
  a:
    type: "state"
    actions:
      - action: "set"
        target: "x"
        value: 1
    on_success: "b"
  b:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "${x}"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml)
    assert result == 1


@pytest.mark.asyncio
async def test_engine_branch():
    engine = Engine()
    yaml = """
id: "test"
name: "Test"
entry: "decide"
config:
  default_tier: "default"
nodes:
  decide:
    type: "branch"
    mode: "expression"
    conditions:
      - when: "${choice} == true"
        goto: "yes"
      - otherwise: "no"
  "yes":
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "yes"
    on_success: "__end__"
  "no":
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "no"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml, context={"choice": True})
    assert result == "yes"

    result2 = await engine.run_string(yaml, context={"choice": False})
    assert result2 == "no"


@pytest.mark.asyncio
async def test_engine_model_mock():
    engine = Engine()

    class MockModelAdapter:
        async def invoke(self, tier, identity, messages, **kwargs):
            return {"output": "mock response", "tier": tier, "identity": identity, "usage": {}}

    engine.register_adapter("model", MockModelAdapter())

    yaml = """
id: "test"
name: "Test"
entry: "call_model"
config:
  default_tier: "default"
nodes:
  call_model:
    type: "model"
    tier: "default"
    identity: "assistant"
    custom_system: "You are helpful."
    input:
      text: "hello"
    output: "model_result"
    on_success: "finalize"
  finalize:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "${model_result}"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml)
    # Contract: model node returns unwrapped content; finalize copies it to result.
    assert result == "mock response"


@pytest.mark.asyncio
async def test_engine_metrics():
    engine = Engine()
    yaml = """
id: "test"
name: "Test"
entry: "step1"
config:
  default_tier: "default"
nodes:
  step1:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: 42
    on_success: "__end__"
"""
    await engine.run_string(yaml)
    stats = engine.get_metrics()
    assert stats["flows_completed"] == 1


@pytest.mark.asyncio
async def test_engine_register_adapter():
    engine = Engine()

    class CustomModel:
        async def invoke(self, tier, identity, messages, **kwargs):
            return {"custom": True, "tier": tier}

    engine.register_adapter("model", CustomModel())
    yaml = """
id: "test"
name: "Test"
entry: "step1"
config:
  default_tier: "default"
nodes:
  step1:
    type: "model"
    tier: "my_tier"
    identity: "bot"
    input:
      text: "hi"
    output: "model_result"
    on_success: "finalize"
  finalize:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "${model_result}"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml)
    assert result["custom"] is True


@pytest.mark.asyncio
async def test_engine_cancel():
    engine = Engine()
    yaml = """
id: "cancel_test"
name: "Cancel Test"
entry: "step1"
config:
  default_tier: "default"
nodes:
  step1:
    type: "state"
    actions:
      - action: "set"
        target: "result"
        value: "done"
    on_success: "__end__"
"""
    result = await engine.run_string(yaml)
    assert result == "done"
