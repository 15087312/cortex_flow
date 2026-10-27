"""Tests for auth (JWT), execution history/replay, and marketplace."""

import pytest
from httpx import ASGITransport, AsyncClient

from cortexflow.api.jwt import create_token, verify_token
from cortexflow.api.server import create_app
from cortexflow.store.auth import AuthStore
from cortexflow.store.executions import ExecutionStore
from cortexflow.store.templates import TemplateStore

# ── JWT unit ───────────────────────────────────────────────

def test_jwt_roundtrip_and_expiry():
    token = create_token("secret", "alice", ttl=1000)
    assert verify_token("secret", token) == "alice"
    assert verify_token("wrong-secret", token) is None
    assert verify_token("secret", "garbage.token") is None
    expired = create_token("secret", "alice", ttl=-10)
    assert verify_token("secret", expired) is None


def test_jwt_tampered_payload_rejected():
    token = create_token("secret", "alice")
    header, payload, sig = token.split(".")
    assert verify_token("secret", f"{header}.{payload}XX.{sig}") is None


# ── Auth store ─────────────────────────────────────────────

def test_auth_store(tmp_path):
    store = AuthStore(tmp_path / "a.db")
    assert store.count_users() == 0
    assert store.create_user("  Admin ", "secret123") is True
    assert store.create_user("admin", "other") is False  # normalized dup
    assert store.count_users() == 1
    assert store.verify_user("admin", "secret123") is True
    assert store.verify_user("admin", "wrong") is False
    assert store.verify_user("nobody", "secret123") is False
    secret = store.get_secret()
    assert store.get_secret() == secret  # stable across calls


# ── Stores ─────────────────────────────────────────────────

def test_execution_store_crud(tmp_path):
    store = ExecutionStore(tmp_path / "e.db")
    rid = store.record("w1", "completed", variables={"a": 1}, result="ok",
                       traces=[{"node_id": "n", "state": "completed"}])
    got = store.get(rid)
    assert got["status"] == "completed"
    assert got["variables"] == {"a": 1}
    assert got["result"] == "ok"
    assert got["traces"][0]["node_id"] == "n"
    store.record("w1", "failed", error="boom")
    runs = store.list("w1")
    assert len(runs) == 2
    assert runs[0]["status"] == "failed"
    assert "traces" not in runs[0]  # list omits traces for lightness
    assert store.get(999) is None


def test_template_store_crud(tmp_path):
    store = TemplateStore(tmp_path / "t.db")
    published = store.publish("w1", "W1", "desc", {"id": "w1"}, tags=["a"])
    assert published["version"] == 1
    assert store.list()[0]["tags"] == ["a"]
    full = store.get(published["id"])
    assert full["definition"] == {"id": "w1"}
    assert store.delete(published["id"]) is True
    assert store.list() == []


# ── Auth API (auth FORCED on) ──────────────────────────────

AUTH_ON = True


@pytest.fixture(autouse=True)
def force_auth(monkeypatch):
    if AUTH_ON:
        monkeypatch.setenv("CORTEXFLOW_DISABLE_AUTH", "0")
    yield


@pytest.fixture
def authed():
    return None


@pytest.mark.asyncio
async def test_setup_login_me_flow(monkeypatch):
    monkeypatch.setenv("CORTEXFLOW_DISABLE_AUTH", "0")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        status = (await client.get("/api/setup")).json()
        assert status["required"] is True
        bad = await client.post("/api/login", json={"username": "a", "password": "b"})
        assert bad.status_code == 401
        setup = await client.post("/api/setup", json={
            "username": "admin", "password": "secret123"})
        assert setup.status_code == 200
        token = setup.json()["token"]
        me = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["username"] == "admin"
        login = await client.post("/api/login", json={
            "username": "admin", "password": "secret123"})
        token2 = login.json()["token"]
        assert token2  # same-second logins are byte-identical by design
        assert (await client.get("/api/me",
                                 headers={"Authorization": f"Bearer {token2}"})).json()["username"] == "admin"
        # second setup attempt rejected
        dup = await client.post("/api/setup", json={
            "username": "root", "password": "secret123"})
        assert dup.status_code == 409


@pytest.mark.asyncio
async def test_protected_endpoints_require_token(monkeypatch):
    monkeypatch.setenv("CORTEXFLOW_DISABLE_AUTH", "0")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/workflows")).status_code == 401
        assert (await client.get("/api/metrics")).status_code == 401
        await client.post("/api/setup", json={
            "username": "admin", "password": "secret123"})
        assert (await client.get("/api/workflows")).status_code == 401
        assert (await client.post("/api/login", json={
            "username": "admin", "password": "secret123"})).status_code == 200


@pytest.mark.asyncio
async def test_execution_replay_api(monkeypatch):
    monkeypatch.setenv("CORTEXFLOW_DISABLE_AUTH", "0")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/setup", json={
            "username": "admin", "password": "secret123"})
        token = (await client.post("/api/login", json={
            "username": "admin", "password": "secret123"})).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        defn = {
            "id": "w1", "name": "W1", "entry": "s",
            "config": {"default_tier": "default"},
            "nodes": {"s": {"type": "state",
                            "actions": [{"action": "set", "target": "result",
                                         "value": "hello ${who}"}],
                            "on_success": "__end__"}},
        }
        await client.post("/api/workflows", json={
            "id": "w1", "name": "W1", "definition": defn}, headers=h)
        run = await client.post("/api/workflows/w1/run",
                                json={"variables": {"who": "world"}}, headers=h)
        assert run.json()["result"] == "hello world"
        hist = (await client.get("/api/executions?workflow_id=w1", headers=h)).json()
        assert hist["executions"][0]["status"] == "completed"
        run_id = hist["executions"][0]["id"]
        detail = (await client.get(f"/api/executions/{run_id}", headers=h)).json()
        assert detail["traces"][0]["node_id"] == "s"
        replay = (await client.post(f"/api/executions/{run_id}/replay",
                                    headers=h)).json()
        assert replay["result"] == "hello world"
        assert (await client.get("/api/executions/9999", headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_marketplace_api(monkeypatch):
    monkeypatch.setenv("CORTEXFLOW_DISABLE_AUTH", "0")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/setup", json={
            "username": "admin", "password": "secret123"})
        token = (await client.post("/api/login", json={
            "username": "admin", "password": "secret123"})).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        defn = {"id": "w1", "name": "W1", "entry": "s",
                "nodes": {"s": {"type": "state"}}}
        await client.post("/api/workflows", json={
            "id": "w1", "name": "W1", "definition": defn}, headers=h)
        pub = await client.post("/api/marketplace", json={
            "workflow_id": "w1", "description": "demo", "tags": ["test"]}, headers=h)
        assert pub.status_code == 200
        tid = pub.json()["id"]
        assert pub.json()["author"] == "admin"
        assert (await client.get("/api/marketplace", headers=h)).json()["templates"][0]["id"] == tid
        full = (await client.get(f"/api/marketplace/{tid}", headers=h)).json()
        assert full["definition"]["id"] == "w1"
        assert (await client.delete(f"/api/marketplace/{tid}", headers=h)).status_code == 200
        assert (await client.delete(f"/api/marketplace/{tid}", headers=h)).status_code == 404
        bad = await client.post("/api/marketplace", json={"workflow_id": "ghost"}, headers=h)
        assert bad.status_code == 404