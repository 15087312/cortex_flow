"""Tests for the single-node dry-run endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from cortexflow.api.server import create_app


def _flow(nodes: dict, variables: dict | None = None) -> dict:
    return {
        "id": "dbg",
        "name": "debug",
        "entry": next(iter(nodes)),
        "variables": variables or {},
        "nodes": nodes,
    }


@pytest.fixture
def app():
    return create_app()


async def _post(app, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/debug/node", json=payload)


@pytest.mark.asyncio
async def test_debug_code_node_returns_result(app):
    definition = _flow({
        "calc": {
            "type": "code",
            "inputs": {"numbers": "${numbers}"},
            "code": "output = sum(numbers) * 2",
            "output": "total",
        },
    })
    resp = await _post(app, {
        "definition": definition,
        "node_id": "calc",
        "variables": {"numbers": [1, 2, 3]},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"] == 12
    assert data["output"] == "total"
    assert data["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_debug_node_reports_failures_without_raising(app):
    definition = _flow({"boom": {"type": "code", "code": "output = 1 / 0"}})
    resp = await _post(app, {"definition": definition, "node_id": "boom"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "division" in data["error"]


@pytest.mark.asyncio
async def test_debug_node_does_not_emit_events(app):
    from cortexflow.api.routes import _get_engine

    engine = _get_engine()
    seen = []
    await engine.event_bus.subscribe("*", lambda e: seen.append(e))

    definition = _flow({
        "say": {"type": "message", "message": "debug hello"},
    })
    resp = await _post(app, {"definition": definition, "node_id": "say"})
    assert resp.status_code == 200
    assert resp.json()["result"] == "debug hello"
    assert seen == []


@pytest.mark.asyncio
async def test_debug_node_unknown_node(app):
    definition = _flow({"a": {"type": "state"}})
    resp = await _post(app, {"definition": definition, "node_id": "missing"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_debug_node_invalid_definition(app):
    resp = await _post(app, {
        "definition": {"id": "x", "name": "x", "entry": "nope", "nodes": {}},
        "node_id": "nope",
    })
    assert resp.status_code == 400
