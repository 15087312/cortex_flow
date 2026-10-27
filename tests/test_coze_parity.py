"""Tests for Coze-parity features: end / break / continue / IO snapshots / structured outputs."""

import pytest

from cortexflow.engine import Engine


def make_engine_with_json_adapter(payload: str):
    """Engine whose model adapter returns a fixed JSON string."""
    engine = Engine()

    class JsonAdapter:
        async def invoke(self, tier, identity, messages, **kwargs):
            return {"output": payload, "tier": tier, "identity": identity}

    engine.register_adapter("model", JsonAdapter())
    return engine


# ── End node ───────────────────────────────────────────────

LOOP_YAML = """
id: loopctl
name: Loop control
entry: lp
nodes:
  lp:
    type: loop
    loop_mode: foreach
    items: ${nums}
    item_var: n
    body: check
    on_complete: done
  check:
    type: branch
    mode: expression
    conditions:
      - when: ${n} == 2
        goto: skip
      - when: ${n} == 4
        goto: stop
      - otherwise: keep
  skip:
    type: continue
  stop:
    type: break
  keep:
    type: state
    actions:
      - action: set
        target: last_kept
        value: ${n}
  done:
    type: end
    end_mode: text
    return_value: 'last kept: ${last_kept}'
"""


@pytest.mark.asyncio
async def test_end_variable_mode():
    engine = Engine()
    result = await engine.run_string(
        """
id: e1
name: E1
entry: s
nodes:
  s:
    type: state
    actions:
      - action: set
        target: greeting
        value: hi
    on_success: done
  done:
    type: end
    end_mode: variable
    return_value: ${greeting}
"""
    )
    assert result == "hi"


@pytest.mark.asyncio
async def test_end_text_mode_interpolates():
    engine = Engine()
    result = await engine.run_string(
        """
id: e2
name: E2
entry: s
nodes:
  s:
    type: state
    actions:
      - action: set
        target: who
        value: bob
    on_success: done
  done:
    type: end
    end_mode: text
    return_value: 'hello, ${who}!'
"""
    )
    assert result == "hello, bob!"


@pytest.mark.asyncio
async def test_end_unknown_mode_fails():
    engine = Engine()
    with pytest.raises(ValueError, match="end_mode"):
        await engine.run_string(
            """
id: e3
name: E3
entry: done
nodes:
  done:
    type: end
    end_mode: carrier-pigeon
    return_value: x
"""
        )


# ── Break / continue ───────────────────────────────────────

@pytest.mark.asyncio
async def test_break_continue_foreach():
    engine = Engine()
    result = await engine.run_string(LOOP_YAML, {"nums": [1, 2, 3, 4, 5]})
    # 1 kept, 2 skipped, 3 kept, 4 breaks the loop
    assert result == "last kept: 3"


@pytest.mark.asyncio
async def test_break_outside_loop_fails_flow():
    engine = Engine()
    with pytest.raises(Exception, match="(?i)break"):
        await engine.run_string(
            """
id: b1
name: B1
entry: lonely
nodes:
  lonely:
    type: break
"""
        )


# ── IO snapshots ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_trace_has_io_snapshots():
    engine = Engine()
    await engine.run_string(LOOP_YAML, {"nums": [1, 3]})
    traces = await engine.get_trace("loopctl")
    assert len(traces) > 0
    for trace in traces:
        assert trace.input_summary.get("config", {}).get("type") in {
            "loop", "branch", "continue", "state", "end",
        }
    done = [t for t in traces if t.node_id == "done"]
    assert done and done[0].output_summary.get("result") == "last kept: 3"


# ── Structured model outputs ───────────────────────────────

MODEL_JSON_YAML = """
id: mjson
name: Model JSON
entry: call
nodes:
  call:
    type: model
    tier: default
    identity: assistant
    input: {text: hi}
    output_format: json
    outputs:
      - {name: answer, type: string}
      - {name: score, type: number}
    strict_outputs: true
    output: parsed
    on_success: fin
  fin:
    type: end
    end_mode: variable
    return_value: parsed
"""


@pytest.mark.asyncio
async def test_model_structured_outputs_strict_pass():
    engine = make_engine_with_json_adapter('{"answer": "yes", "score": 0.9}')
    result = await engine.run_string(MODEL_JSON_YAML)
    assert result == {"answer": "yes", "score": 0.9}


@pytest.mark.asyncio
async def test_model_structured_outputs_strict_missing_field():
    engine = make_engine_with_json_adapter('{"answer": "yes"}')
    with pytest.raises(ValueError, match="score"):
        await engine.run_string(MODEL_JSON_YAML)


@pytest.mark.asyncio
async def test_model_structured_outputs_lenient_keeps_content():
    engine = make_engine_with_json_adapter('{"answer": "yes"}')
    result = await engine.run_string(
        MODEL_JSON_YAML.replace("strict_outputs: true", "strict_outputs: false")
    )
    assert result == {"answer": "yes"}


@pytest.mark.asyncio
async def test_model_structured_outputs_strict_rejects_text():
    engine = make_engine_with_json_adapter('just some prose, no JSON')
    with pytest.raises(ValueError, match="non-JSON"):
        await engine.run_string(MODEL_JSON_YAML)
