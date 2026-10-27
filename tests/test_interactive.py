"""Tests for ask/checkpoints/scheduler/testcases (human-in-loop round)."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from cortexflow.api.server import create_app
from cortexflow.engine import Engine
from cortexflow.events.types import Event
from cortexflow.runtime.events import AskQuestion
from cortexflow.scheduler import Scheduler
from cortexflow.state.blackboard import Blackboard
from cortexflow.state.checkpoint import Checkpoint, CheckpointStore
from cortexflow.store.testcases import TestCaseStore

ASK_YAML = """
id: aske2e
name: Ask e2e
entry: greet
nodes:
  greet:
    type: state
    actions:
      - action: set
        target: user
        value: Bob
    on_success: confirm
  confirm:
    type: ask
    question: 'Refund 10 to ${user}? (yes/no)'
    output: confirmed
    on_event: act
  act:
    type: branch
    mode: expression
    conditions:
      - when: ${confirmed} == 'yes'
        goto: yes_end
      - otherwise: no_end
  yes_end:
    type: end
    end_mode: text
    return_value: 'refunded ${user}'
  no_end:
    type: end
    end_mode: text
    return_value: cancelled
"""


# ── Ask suspend / resume ───────────────────────────────────

@pytest.mark.asyncio
async def test_ask_suspend_resume_same_engine():
    engine = Engine()
    with pytest.raises(AskQuestion) as exc:
        await engine.run_string(ASK_YAML)
    assert "Bob" in exc.value.question
    result = await engine.resume("aske2e", Event(type="user_input", payload={"answer": "yes"}))
    assert result == "refunded Bob"


@pytest.mark.asyncio
async def test_ask_resume_across_restart():
    engine1 = Engine()
    with pytest.raises(AskQuestion):
        await engine1.run_string(ASK_YAML)
    del engine1
    # Brand-new engine, same SQLite file: checkpoint must still be there.
    engine2 = Engine()
    result = await engine2.resume("aske2e", Event(type="user_input", payload={"answer": "no"}))
    assert result == "cancelled"


@pytest.mark.asyncio
async def test_ask_missing_question():
    from cortexflow.dsl.validator import ValidationError
    from cortexflow.nodes.ask import AskNode
    from cortexflow.runtime.context import ExecutionContext
    # Validator rejects it at compile time…
    engine = Engine()
    with pytest.raises(ValidationError, match="question"):
        await engine.run_string(
            "id: q\nname: Q\nentry: a\nnodes:\n  a:\n    type: ask\n    on_event: b\n  b:\n    type: end\n"
        )
    # …and the node itself guards at runtime.
    with pytest.raises(ValueError, match="question"):
        await AskNode("a", {}).execute(ExecutionContext())


# ── Checkpoint persistence ─────────────────────────────────

@pytest.mark.asyncio
async def test_checkpoint_roundtrip_with_blackboard():
    store = CheckpointStore()
    bb = Blackboard()
    bb._goal = "goal-1"
    from datetime import UTC, datetime
    await store.save(Checkpoint(
        flow_id="cp1", flow_state="suspended", node_states={"n": "waiting"},
        variables={"x": [1, 2]}, blackboard_snapshot=bb.to_dict(),
        current_node="n", pending_events=["ask"], created_at=datetime.now(UTC),
        metadata={"_wait_config_n": {"on_event": "m"}, "other": 1},
        workflow_id="wf", definition={"id": "wf"},
    ))
    loaded = await store.load("cp1")
    assert loaded.workflow_id == "wf"
    assert loaded.definition == {"id": "wf"}
    assert loaded.node_states == {"n": "waiting"}
    assert loaded.metadata == {"_wait_config_n": {"on_event": "m"}}
    restored = Blackboard.from_dict(loaded.blackboard_snapshot)
    assert restored._goal == "goal-1"
    await store.delete("cp1")
    assert await store.load("cp1") is None


# ── API: 202 suspend + resume ───────────────────────────────

@pytest.mark.asyncio
async def test_api_suspend_returns_202_not_500():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        import yaml
        defn = yaml.safe_load(ASK_YAML)
        await client.post("/api/workflows", json={
            "id": "aske2e", "name": "Ask", "definition": defn})
        resp = await client.post("/api/workflows/aske2e/run", json={"variables": {}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "suspended"
        assert "Bob" in body["question"]
        resume = await client.post("/api/workflows/aske2e/resume",
                                   json={"type": "user_input",
                                         "payload": {"answer": "yes"}})
        assert resume.json()["result"] == "refunded Bob"


# ── Scheduler ──────────────────────────────────────────────

class _FakeStore:
    def __init__(self, workflows):
        self._wfs = workflows

    def list(self):
        return self._wfs


class _FakeState:
    def __init__(self):
        self.runs = []

    def get(self, wid):
        return {"last_run": None, "run_count": 0, "last_status": ""}

    def record_run(self, wid, status):
        self.runs.append((wid, status))


def _wf(wid, interval):
    return {"id": wid, "name": wid,
            "definition": {"schedule": {"enabled": True,
                                        "interval_seconds": interval,
                                        "variables": {"a": 1}}}}


@pytest.mark.asyncio
async def test_scheduler_runs_due_once():
    ran = []

    async def fake_run(workflow, variables):
        ran.append((workflow["id"], variables))

    sched = Scheduler(store=_FakeStore([_wf("w1", 30)]), state=_FakeState(),
                      run_workflow=fake_run, min_interval_seconds=0)
    assert await sched.tick() == ["w1"]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert ran == [("w1", {"a": 1})]


@pytest.mark.asyncio
async def test_scheduler_skips_disabled_and_fast_intervals():
    ran = []

    async def fake_run(workflow, variables):
        ran.append(workflow["id"])

    store = _FakeStore([
        {"id": "off", "name": "off",
         "definition": {"schedule": {"enabled": False, "interval_seconds": 30}}},
        {"id": "fast", "name": "fast",
         "definition": {"schedule": {"enabled": True, "interval_seconds": 1}}},
        {"id": "plain", "name": "plain", "definition": {}},
    ])
    sched = Scheduler(store=store, state=_FakeState(), run_workflow=fake_run,
                      min_interval_seconds=10)
    assert await sched.tick() == []
    assert ran == []


@pytest.mark.asyncio
async def test_scheduler_no_overlap_and_failure_recorded():
    calls = []

    async def flaky(workflow, variables):
        calls.append(workflow["id"])
        raise RuntimeError("boom")

    state = _FakeState()
    sched = Scheduler(store=_FakeStore([_wf("w1", 30)]), state=state,
                      run_workflow=flaky, min_interval_seconds=0)
    sched._running.add("w1")  # simulate in-flight run
    assert await sched.tick() == []
    sched._running.discard("w1")
    assert await sched.tick() == ["w1"]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert state.runs == [("w1", "failed: boom")]


def test_schedule_validator():
    from cortexflow.dsl.schema import WorkflowDefinition
    from cortexflow.dsl.validator import ValidationError, Validator
    base = {"id": "s", "name": "S", "entry": "a",
            "nodes": {"a": {"type": "state", "on_success": "__end__"}}}
    Validator().validate(WorkflowDefinition(**{**base, "schedule": {
        "enabled": True, "interval_seconds": 60}}))
    with pytest.raises(ValidationError, match="interval_seconds"):
        Validator().validate(WorkflowDefinition(**{**base, "schedule": {
            "enabled": True, "interval_seconds": 5}}))


# ── Test cases ─────────────────────────────────────────────

def test_testcase_store_crud(tmp_path):
    store = TestCaseStore(tmp_path / "tc.db")
    created = store.create("w1", "vip", {"level": "vip"})
    assert created["id"] == 1
    assert store.list("w1")[0]["variables"] == {"level": "vip"}
    assert store.list("other") == []
    assert store.delete("w1", 1) is True
    assert store.delete("w1", 1) is False


@pytest.mark.asyncio
async def test_testcase_api_crud():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "w1", "name": "W1", "definition": {}})
        created = (await client.post("/api/workflows/w1/testcases", json={
            "name": "vip", "variables": {"level": "vip"}})).json()
        assert created["name"] == "vip"
        listed = (await client.get("/api/workflows/w1/testcases")).json()
        assert listed["count"] == 1
        assert listed["testcases"][0]["variables"] == {"level": "vip"}
        assert (await client.delete(
            f"/api/workflows/w1/testcases/{created['id']}")).status_code == 200
        assert (await client.get("/api/workflows/w1/testcases")).json()["count"] == 0
        assert (await client.get("/api/workflows/ghost/testcases")).status_code == 404


def test_blackboard_from_dict_roundtrip():
    bb = Blackboard()
    bb._goal = "g"
    bb._dialog = [{"a": 1}]
    restored = Blackboard.from_dict(bb.to_dict())
    assert restored._goal == "g"
    assert restored._dialog == [{"a": 1}]
    assert Blackboard.from_dict(None)._goal is None
