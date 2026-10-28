"""Tests for the run-from-node debugger endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from cortexflow.api.server import create_app


def _flow(nodes: dict, entry: str | None = None, variables: dict | None = None) -> dict:
    return {
        "id": "dbg_run",
        "name": "debug run",
        "entry": entry or next(iter(nodes)),
        "variables": variables or {},
        "nodes": nodes,
    }


@pytest.fixture
def app():
    return create_app()


async def _post(app, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/debug/run", json=payload)


def _chat_flow() -> dict:
    return _flow({
        "calc": {
            "type": "code",
            "inputs": {"n": "${n}"},
            "code": "output = n * 2",
            "output": "total",
            "on_success": "say",
        },
        "say": {"type": "message", "message": "total is ${total}", "on_success": "__end__"},
    })


@pytest.mark.asyncio
async def test_run_from_node_to_end(app):
    resp = await _post(app, {
        "definition": _chat_flow(),
        "node_id": "calc",
        "variables": {"n": 4},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["start_node"] == "calc"
    assert [step["node_id"] for step in data["steps"]] == ["calc", "say"]
    assert [step["status"] for step in data["steps"]] == ["completed", "completed"]
    assert all(step["duration_ms"] is not None for step in data["steps"])
    assert data["messages"] == [
        {"role": "assistant", "content": "total is 8", "node_id": "say"},
    ]
    assert data["variables"]["total"] == 8


@pytest.mark.asyncio
async def test_run_from_middle_node_skips_earlier_nodes(app):
    resp = await _post(app, {
        "definition": _chat_flow(),
        "node_id": "say",
        "variables": {"total": 5},
    })
    data = resp.json()
    assert data["status"] == "completed"
    assert [step["node_id"] for step in data["steps"]] == ["say"]
    assert data["messages"][0]["content"] == "total is 5"


@pytest.mark.asyncio
async def test_run_defaults_to_entry(app):
    resp = await _post(app, {"definition": _chat_flow(), "variables": {"n": 1}})
    data = resp.json()
    assert data["status"] == "completed"
    assert data["start_node"] == "calc"


@pytest.mark.asyncio
async def test_run_reports_failure_with_step(app):
    definition = _flow({
        "boom": {"type": "code", "code": "output = 1 / 0"},
        "never": {"type": "message", "message": "nope"},
    })
    definition["nodes"]["boom"]["on_success"] = "never"
    resp = await _post(app, {"definition": definition, "node_id": "boom"})
    data = resp.json()
    assert data["status"] == "failed"
    assert "division" in data["error"]
    assert data["steps"][0]["status"] == "failed"
    assert "division" in data["steps"][0]["error"]


@pytest.mark.asyncio
async def test_run_stops_at_wait_node(app):
    definition = _flow({
        "hold": {"type": "wait", "event": "approval", "on_event": "done"},
        "done": {"type": "message", "message": "approved"},
    })
    resp = await _post(app, {"definition": definition, "node_id": "hold"})
    data = resp.json()
    assert data["status"] == "suspended"
    assert data["waiting"]["event_type"] == "approval"
    assert data["waiting"]["node_id"] == "hold"
    assert data["steps"][0]["node_id"] == "hold"


@pytest.mark.asyncio
async def test_run_does_not_publish_to_live_bus(app):
    from cortexflow.api.routes import _get_engine

    seen = []
    await _get_engine().event_bus.subscribe("*", lambda event: seen.append(event))
    resp = await _post(app, {"definition": _chat_flow(), "variables": {"n": 2}})
    assert resp.json()["status"] == "completed"
    assert seen == []


@pytest.mark.asyncio
async def test_run_unknown_node(app):
    resp = await _post(app, {"definition": _chat_flow(), "node_id": "missing"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_invalid_definition(app):
    resp = await _post(app, {
        "definition": {"id": "x", "name": "x", "entry": "nope", "nodes": {}},
        "node_id": "nope",
    })
    assert resp.status_code == 400
