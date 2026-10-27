"""Tests for API routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from cortexflow.api.routes import (
    _auth,
    _execution_log,
    _executions,
    _marketplace,
    _testcases,
    _workflows,
)
from cortexflow.api.server import create_app
from cortexflow.state.checkpoint import CheckpointStore


@pytest.fixture(autouse=True)
def clear_state():
    _workflows.clear()
    _executions.clear()
    _testcases.clear()
    _execution_log.clear()
    _marketplace.clear()
    _auth.clear()
    CheckpointStore().clear()
    yield
    _workflows.clear()
    _executions.clear()
    _testcases.clear()
    _execution_log.clear()
    _marketplace.clear()
    _auth.clear()
    CheckpointStore().clear()


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_create_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/workflows", json={
            "id": "wf1",
            "name": "Test WF",
            "definition": {
                "id": "wf1",
                "name": "Test WF",
                "entry": "step1",
                "nodes": {"step1": {"type": "state", "on_success": "__end__"}},
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "wf1"
        assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_duplicate_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"id": "wf1", "name": "Test", "definition": {}}
        await client.post("/api/workflows", json=payload)
        resp = await client.post("/api/workflows", json=payload)
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_workflows(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1", "name": "WF1", "definition": {},
        })
        resp = await client.get("/api/workflows")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1", "name": "WF1", "definition": {},
        })
        resp = await client.get("/api/workflows/wf1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "wf1"


@pytest.mark.asyncio
async def test_get_missing_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/workflows/nonexistent")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1", "name": "WF1", "definition": {},
        })
        resp = await client.delete("/api/workflows/wf1")
        assert resp.status_code == 200
        resp2 = await client.get("/api/workflows/wf1")
        assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_run_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1",
            "name": "WF1",
            "definition": {
                "id": "wf1",
                "name": "WF1",
                "entry": "step1",
                "config": {"default_tier": "default"},
                "nodes": {
                    "step1": {
                        "type": "state",
                        "actions": [{"action": "set", "target": "result", "value": "done"}],
                        "on_success": "__end__",
                    },
                },
            },
        })
        resp = await client.post("/api/workflows/wf1/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] == "done"


@pytest.mark.asyncio
async def test_run_with_variables(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1",
            "name": "WF1",
            "definition": {
                "id": "wf1",
                "name": "WF1",
                "entry": "step1",
                "config": {"default_tier": "default"},
                "nodes": {
                    "step1": {
                        "type": "state",
                        "actions": [{"action": "set", "target": "result", "value": "${input}"}],
                        "on_success": "__end__",
                    },
                },
            },
        })
        resp = await client.post("/api/workflows/wf1/run", json={
            "variables": {"input": "hello"},
        })
        assert resp.status_code == 200
        assert resp.json()["result"] == "hello"


@pytest.mark.asyncio
async def test_get_metrics(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "flows_completed" in data


async def _put(client, wid, name, definition, message=None):
    body = {"name": name, "definition": definition}
    if message:
        body["message"] = message
    return await client.put(f"/api/workflows/{wid}", json=body)


@pytest.mark.asyncio
async def test_update_workflow_records_versions(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1", "name": "WF1", "definition": {"id": "wf1", "v": 1},
        })
        resp = await _put(client, "wf1", "WF1", {"id": "wf1", "v": 2}, message="tweak")
        assert resp.status_code == 200
        versions = (await client.get("/api/workflows/wf1/versions")).json()
        assert versions["count"] == 2
        assert versions["versions"][0]["version"] == 2
        v1 = await client.get("/api/workflows/wf1/versions/1")
        assert v1.json()["definition"] == {"id": "wf1", "v": 1}


@pytest.mark.asyncio
async def test_rollback_workflow(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1", "name": "WF1", "definition": {"id": "wf1", "v": 1},
        })
        await _put(client, "wf1", "WF1", {"id": "wf1", "v": 2})
        resp = await client.post("/api/workflows/wf1/rollback", json={"version": 1})
        assert resp.status_code == 200
        assert resp.json()["version"] == 3
        current = (await client.get("/api/workflows/wf1")).json()
        assert current["definition"] == {"id": "wf1", "v": 1}
        assert current["version"] == 3


@pytest.mark.asyncio
async def test_rollback_missing_version_404(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/workflows", json={
            "id": "wf1", "name": "WF1", "definition": {},
        })
        resp = await client.post("/api/workflows/wf1/rollback", json={"version": 99})
        assert resp.status_code == 404
        resp2 = await client.get("/api/workflows/ghost/versions")
        assert resp2.status_code == 404
