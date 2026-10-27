"""Tests for persistence (SQLite store + versions) and routing nodes."""

import pytest

from cortexflow.engine import Engine
from cortexflow.nodes.aggregate import AggregateNode
from cortexflow.nodes.intent import IntentNode
from cortexflow.runtime.context import ExecutionContext
from cortexflow.store.workflows import WorkflowStore


def make_store(tmp_path):
    return WorkflowStore(tmp_path / "t.db")


# ── WorkflowStore ──────────────────────────────────────────

def test_store_save_get_list_delete(tmp_path):
    store = make_store(tmp_path)
    assert store.get("nope") is None
    store.save("w1", "W1", {"id": "w1"})
    got = store.get("w1")
    assert got["name"] == "W1"
    assert got["definition"] == {"id": "w1"}
    assert got["version"] == 1
    assert len(store.list()) == 1
    assert store.exists("w1")
    assert store.delete("w1") is True
    assert store.get("w1") is None
    assert store.delete("w1") is False


def test_store_versions_and_rollback(tmp_path):
    store = make_store(tmp_path)
    store.save("w1", "W1", {"id": "w1", "v": 1}, message="created")
    store.save("w1", "W1", {"id": "w1", "v": 2}, message="tweak")
    versions = store.list_versions("w1")
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[1]["message"] == "created"
    assert store.get_version("w1", 1)["definition"] == {"id": "w1", "v": 1}
    assert store.get_version("w1", 99) is None
    rolled = store.rollback("w1", 1)
    assert rolled["definition"] == {"id": "w1", "v": 1}
    assert rolled["version"] == 3
    assert store.list_versions("w1")[0]["message"] == "rollback to v1"
    assert store.rollback("w1", 99) is None
    assert store.rollback("ghost", 1) is None


def test_store_clear(tmp_path):
    store = make_store(tmp_path)
    store.save("w1", "W1", {})
    store.clear()
    assert store.list() == []
    assert store.list_versions("w1") == []


# ── Aggregate node ─────────────────────────────────────────

def _ctx(variables):
    return ExecutionContext(variables=dict(variables))


@pytest.mark.asyncio
async def test_aggregate_first():
    node = AggregateNode("m", {"groups": [
        {"output": "answer", "from": ["a", "b"], "strategy": "first"},
    ]})
    ctx = _ctx({"a": "", "b": "B!"})
    assert await node.execute(ctx) == {"answer": "B!"}
    assert ctx.get_variable("answer") == "B!"


@pytest.mark.asyncio
async def test_aggregate_strategies():
    node = AggregateNode("m", {"groups": [
        {"output": "last", "from": ["${x}", "${y}"], "strategy": "last"},
        {"output": "items", "from": ["l1", "l2"], "strategy": "concat"},
        {"output": "text", "from": ["s1", "s2"], "strategy": "concat"},
        {"output": "cfg", "from": ["d1", "d2"], "strategy": "merge"},
    ]})
    ctx = _ctx({"x": 1, "y": 2, "l1": [1], "l2": [2, 3],
                "s1": "a", "s2": "b",
                "d1": {"k": 1, "old": True}, "d2": {"k": 2}})
    result = await node.execute(ctx)
    assert result == {"last": 2, "items": [1, 2, 3], "text": "a\nb",
                      "cfg": {"k": 2, "old": True}}


@pytest.mark.asyncio
async def test_aggregate_errors():
    with pytest.raises(ValueError, match="groups"):
        await AggregateNode("m", {}).execute(_ctx({}))
    with pytest.raises(ValueError, match="unknown strategy"):
        await AggregateNode("m", {"groups": [
            {"output": "o", "from": ["x"], "strategy": "nope"},
        ]}).execute(_ctx({"x": 1}))


# ── Intent node ────────────────────────────────────────────

INTENTS = [
    {"name": "refund", "keywords": ["退款", "refund"], "goto": "refund_flow"},
    {"name": "hours", "keywords": ["几点", "营业"], "goto": "hours_flow"},
]


@pytest.mark.asyncio
async def test_intent_match_and_otherwise():
    node = IntentNode("r", {"input": "${text}", "intents": INTENTS,
                            "otherwise": "fallback", "output": "hit"})
    ctx = _ctx({"text": "怎么退款退钱啊"})
    assert await node.execute(ctx) == "refund_flow"
    assert ctx.get_variable("hit") == "refund"
    ctx2 = _ctx({"text": "今天天气不错"})
    assert await node.execute(ctx2) == "fallback"
    assert ctx2.get_variable("hit") is None


@pytest.mark.asyncio
async def test_intent_tie_goes_first():
    node = IntentNode("r", {"input": "${text}", "intents": INTENTS})
    # Both match once → first wins.
    assert await node.execute(_ctx({"text": "退款几点办"})) == "refund_flow"


@pytest.mark.asyncio
async def test_intent_no_match_no_otherwise_ends_chain():
    node = IntentNode("r", {"input": "${text}", "intents": INTENTS})
    assert await node.execute(_ctx({"text": "无关"})) is None


@pytest.mark.asyncio
async def test_intent_missing_intents():
    with pytest.raises(ValueError, match="intents"):
        await IntentNode("r", {}).execute(_ctx({}))


# ── Engine routing through intent ──────────────────────────

INTENT_YAML = """
id: intentdemo
name: Intent demo
entry: route
nodes:
  route:
    type: intent
    input: ${text}
    intents:
      - {name: bug, keywords: [报错, bug], goto: bugfix}
      - {name: hi, keywords: [你好, hello], goto: greet}
    otherwise: fallback
  bugfix:
    type: state
    actions:
      - {action: set, target: out, value: fixing}
    on_success: done
  greet:
    type: state
    actions:
      - {action: set, target: out, value: greeting}
    on_success: done
  fallback:
    type: state
    actions:
      - {action: set, target: out, value: unknown}
    on_success: done
  done:
    type: end
    end_mode: variable
    return_value: out
"""


@pytest.mark.asyncio
async def test_intent_routes_flow():
    engine = Engine()
    assert await engine.run_string(INTENT_YAML, {"text": "报了个bug"}) == "fixing"
    assert await engine.run_string(INTENT_YAML, {"text": "hello你好"}) == "greeting"
    assert await engine.run_string(INTENT_YAML, {"text": "zzz"}) == "unknown"


# ── Validator ──────────────────────────────────────────────

def test_validator_accepts_new_nodes():
    from cortexflow.dsl.schema import WorkflowDefinition
    from cortexflow.dsl.validator import Validator
    wf = WorkflowDefinition(**{
        "id": "v", "name": "V", "entry": "route",
        "nodes": {
            "route": {"type": "intent", "input": "${t}",
                       "intents": [{"name": "a", "keywords": ["x"],
                                    "goto": "a_flow"}],
                       "otherwise": "fb"},
            "a_flow": {"type": "state", "on_success": "merge"},
            "fb": {"type": "state", "on_success": "merge"},
            "merge": {"type": "aggregate",
                       "groups": [{"output": "o", "from": ["x"]}],
                       "on_success": "done"},
            "done": {"type": "end", "return_value": "o"},
        },
    })
    Validator().validate(wf)  # must not raise


def test_validator_rejects_bad_intent_ref():
    from cortexflow.dsl.schema import WorkflowDefinition
    from cortexflow.dsl.validator import Validator, ValidationError
    wf = WorkflowDefinition(**{
        "id": "v", "name": "V", "entry": "route",
        "nodes": {
            "route": {"type": "intent",
                       "intents": [{"name": "a", "keywords": ["x"],
                                    "goto": "ghost"}]},
        },
    })
    with pytest.raises(ValidationError, match="ghost"):
        Validator().validate(wf)
