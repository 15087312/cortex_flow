"""API routes."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from cortexflow.api.jwt import create_token, verify_token
from cortexflow.engine import Engine
from cortexflow.events.types import Event
from cortexflow.runtime.events import AskQuestion, WaitEvent
from cortexflow.store.auth import AuthStore
from cortexflow.store.executions import ExecutionStore
from cortexflow.store.templates import TemplateStore
from cortexflow.store.testcases import TestCaseStore
from cortexflow.store.workflows import WorkflowStore

logger = logging.getLogger(__name__)

# ── Auth (must be defined before `router` so Depends can reference it) ──

_engine: Engine | None = None
# NOTE: _workflows is a SQLite-backed WorkflowStore (not a dict) so flows
# survive backend restarts. It exposes .clear() so tests keep working.
_workflows = WorkflowStore()
_executions: dict[str, dict[str, Any]] = {}
_execution_log = ExecutionStore()
_testcases = TestCaseStore()
_auth = AuthStore()
_marketplace = TemplateStore()
# Set by server lifespan; None in tests and when the scheduler is off.
_scheduler: Any = None


def _auth_disabled() -> bool:
    return os.environ.get("CORTEXFLOW_DISABLE_AUTH", "") == "1"


def require_user(authorization: str = Header(default="")) -> str:
    """Auth dependency: returns the authenticated username."""
    if _auth_disabled():
        return "dev"
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = verify_token(_auth.get_secret(), authorization[7:].strip())
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


# Everything on this router requires auth (unless CORTEXFLOW_DISABLE_AUTH=1).
router = APIRouter(dependencies=[Depends(require_user)])
# Public endpoints (setup / login).
public = APIRouter()


class SetupRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


@public.get("/setup")
async def setup_status():
    """Whether the first (admin) account still needs to be created."""
    if _auth_disabled():
        return {"required": False, "users": 0}
    return {"required": _auth.count_users() == 0, "users": _auth.count_users()}


@public.post("/setup")
async def create_admin(req: SetupRequest):
    """Create the first admin account (only when no users exist)."""
    if _auth_disabled():
        raise HTTPException(status_code=400, detail="Auth disabled in dev mode")
    if _auth.count_users() > 0:
        raise HTTPException(status_code=409, detail="Admin already exists")
    if not _auth.create_user(req.username, req.password):
        raise HTTPException(status_code=400, detail="Invalid username/password")
    return {"token": create_token(_auth.get_secret(), req.username),
            "username": req.username}


@public.post("/login")
async def login(req: LoginRequest):
    if _auth_disabled():
        raise HTTPException(status_code=400, detail="Auth disabled in dev mode")
    if not _auth.verify_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_token(_auth.get_secret(), req.username),
            "username": req.username}


@public.get("/me")
async def me(username: str = Depends(require_user)):
    return {"username": username}


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine


async def _serialize_traces(engine: Engine, workflow_id: str) -> list[dict[str, Any]]:
    traces = await engine.get_trace(workflow_id)
    return [
        {
            "node_id": t.node_id,
            "node_type": t.node_type,
            "state": t.state,
            "started_at": t.started_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "error": t.error,
            "inputs": t.input_summary or {},
            "outputs": t.output_summary or {},
        }
        for t in traces
    ]


async def _execute_workflow(engine: Engine, workflow_id: str,
                            wf_data: dict[str, Any],
                            variables: dict[str, Any] | None) -> dict[str, Any]:
    """Run a workflow, persist execution history, return the API payload."""
    from cortexflow.dsl.schema import WorkflowDefinition

    started = datetime.now(UTC).isoformat()
    try:
        workflow = WorkflowDefinition(**wf_data["definition"])
        result = await engine.run(workflow, variables)
        traces = await _serialize_traces(engine, workflow_id)
        _executions[workflow_id] = {"status": "completed", "result": result}
        _execution_log.record(workflow_id, "completed", variables=variables,
                              result=result, traces=traces, started_at=started)
        return {"status": "completed", "workflow_id": workflow_id, "result": result}
    except AskQuestion as ask:
        traces = await _serialize_traces(engine, workflow_id)
        _executions[workflow_id] = {
            "status": "suspended", "node_id": ask.node_id, "question": ask.question,
        }
        _execution_log.record(workflow_id, "suspended", variables=variables,
                              error=ask.question, traces=traces, started_at=started)
        return {"status": "suspended", "workflow_id": workflow_id,
                "node_id": ask.node_id, "question": ask.question}
    except WaitEvent as w:
        traces = await _serialize_traces(engine, workflow_id)
        _executions[workflow_id] = {"status": "suspended", "event": w.event_type}
        _execution_log.record(workflow_id, "suspended", variables=variables,
                              error=f"waiting for {w.event_type}",
                              traces=traces, started_at=started)
        return {"status": "suspended", "workflow_id": workflow_id,
                "event": w.event_type}
    except Exception as exc:  # noqa: BLE001
        traces = await _serialize_traces(engine, workflow_id)
        _executions[workflow_id] = {"status": "failed", "error": str(exc)}
        _execution_log.record(workflow_id, "failed", variables=variables,
                              error=str(exc), traces=traces, started_at=started)
        raise HTTPException(status_code=500, detail=str(exc))


async def _on_event(event: Event) -> None:
    for eq in _event_queues:
        try:
            eq.put_nowait(event)
        except asyncio.QueueFull:
            pass


_event_queues: list[asyncio.Queue] = []


class WorkflowCreate(BaseModel):
    id: str
    name: str
    definition: dict


class WorkflowResponse(BaseModel):
    id: str
    name: str
    status: str
    version: int | None = None


class RunRequest(BaseModel):
    variables: dict[str, Any] | None = None


@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(workflow: WorkflowCreate):
    """Create a workflow (records version v1)."""
    if _workflows.exists(workflow.id):
        raise HTTPException(status_code=400, detail="Workflow already exists")
    saved = _workflows.save(workflow.id, workflow.name, workflow.definition,
                            message="created")
    return WorkflowResponse(id=saved["id"], name=saved["name"], status=saved["status"])


class WorkflowUpdate(BaseModel):
    name: str | None = None
    definition: dict | None = None
    message: str | None = None


@router.put("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, update: WorkflowUpdate):
    """Update a workflow (upsert; every save records a new version)."""
    current = _workflows.get(workflow_id)
    name = update.name if update.name is not None else (current["name"] if current else workflow_id)
    definition = update.definition if update.definition is not None else (current["definition"] if current else {})
    saved = _workflows.save(workflow_id, name, definition,
                            message=update.message or "updated")
    return WorkflowResponse(id=saved["id"], name=saved["name"],
                            status=saved["status"], version=saved.get("version"))


@router.get("/workflows")
async def list_workflows():
    """List workflows."""
    return _workflows.list()


@router.post("/workflows/validate")
async def validate_workflow(definition: dict):
    """Validate a workflow definition without saving."""
    try:
        from cortexflow.dsl.schema import WorkflowDefinition
        from cortexflow.dsl.validator import Validator
        wf = WorkflowDefinition(**definition)
        Validator().validate(wf)
        return {"valid": True, "errors": []}
    except Exception as exc:  # noqa: BLE001
        return {"valid": False, "errors": [{"message": str(exc)}]}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a workflow."""
    wf = _workflows.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow and its version history."""
    if not _workflows.delete(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "deleted"}


class RollbackRequest(BaseModel):
    version: int


class TestCaseCreate(BaseModel):
    name: str
    variables: dict[str, Any] | None = None


@router.get("/workflows/{workflow_id}/testcases")
async def list_testcases(workflow_id: str):
    """List saved variable sets for one-click replay."""
    if not _workflows.exists(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    cases = _testcases.list(workflow_id)
    return {"workflow_id": workflow_id, "testcases": cases, "count": len(cases)}


@router.post("/workflows/{workflow_id}/testcases")
async def create_testcase(workflow_id: str, testcase: TestCaseCreate):
    """Save current variables as a named test case."""
    if not _workflows.exists(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _testcases.create(workflow_id, testcase.name, testcase.variables or {})


@router.delete("/workflows/{workflow_id}/testcases/{case_id}")
async def delete_testcase(workflow_id: str, case_id: int):
    """Delete a test case."""
    if not _testcases.delete(workflow_id, case_id):
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"status": "deleted"}


@router.get("/workflows/{workflow_id}/versions")
async def list_workflow_versions(workflow_id: str):
    """List version history (newest first)."""
    if not _workflows.exists(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    versions = _workflows.list_versions(workflow_id)
    return {"workflow_id": workflow_id, "versions": versions, "count": len(versions)}


@router.get("/workflows/{workflow_id}/versions/{version}")
async def get_workflow_version(workflow_id: str, version: int):
    """Get a historical version's definition (read-only)."""
    snapshot = _workflows.get_version(workflow_id, version)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Version not found")
    return snapshot


@router.post("/workflows/{workflow_id}/rollback")
async def rollback_workflow(workflow_id: str, request: RollbackRequest):
    """Restore a historical version as current (records a new version)."""
    saved = _workflows.rollback(workflow_id, request.version)
    if not saved:
        raise HTTPException(status_code=404, detail="Workflow or version not found")
    return {"status": "rolled back", "workflow_id": workflow_id,
            "version": saved["version"]}


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: RunRequest | None = None):
    """Run a workflow."""
    wf_data = _workflows.get(workflow_id)
    if not wf_data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    engine = _get_engine()
    variables = request.variables if request else None
    return await _execute_workflow(engine, workflow_id, wf_data, variables)


@router.get("/workflows/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Get workflow execution status."""
    if workflow_id in _executions:
        return {"workflow_id": workflow_id, **_executions[workflow_id]}
    wf = _workflows.get(workflow_id)
    if wf:
        return {"workflow_id": workflow_id, "status": wf["status"]}
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow."""
    engine = _get_engine()
    await engine.cancel(workflow_id)
    return {"status": "cancelled", "workflow_id": workflow_id}


@router.post("/workflows/{workflow_id}/resume")
async def resume_workflow(workflow_id: str, event_data: dict[str, Any] | None = None):
    """Resume a suspended workflow."""
    engine = _get_engine()
    event = Event(
        type=(event_data or {}).get("type", "user_input"),
        payload=(event_data or {}).get("payload", {}),
    )
    try:
        result = await engine.resume(workflow_id, event)
        _executions[workflow_id] = {"status": "completed", "result": result}
        _execution_log.record(workflow_id, "completed",
                              variables=None, result=result,
                              traces=await _serialize_traces(engine, workflow_id),
                              error="resumed")
        return {"status": "resumed", "workflow_id": workflow_id, "result": result}
    except Exception as exc:  # noqa: BLE001
        _executions[workflow_id] = {"status": "failed", "error": str(exc)}
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workflows/{workflow_id}/trace")
async def get_workflow_trace(workflow_id: str):
    """Get execution trace."""
    engine = _get_engine()
    traces = await engine.get_trace(workflow_id)
    return {
        "workflow_id": workflow_id,
        "traces": [
            {
                "node_id": t.node_id,
                "node_type": t.node_type,
                "state": t.state,
                "started_at": t.started_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "error": t.error,
                "inputs": t.input_summary or {},
                "outputs": t.output_summary or {},
            }
            for t in traces
        ],
    }


@router.get("/metrics")
async def get_metrics():
    """Get engine metrics."""
    engine = _get_engine()
    return engine.get_metrics()


@router.get("/schedules")
async def list_schedules():
    """List interval schedules derived from workflow definitions."""
    if _scheduler is None:
        return {"schedules": [], "running": False}
    return {"schedules": _scheduler.status(), "running": True}


@router.websocket("/events")
async def event_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming."""
    await websocket.accept()
    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)
    _event_queues.append(queue)

    engine = _get_engine()
    await engine.event_bus.subscribe("*", _on_event)

    try:
        while True:
            event = await queue.get()
            await websocket.send_json({
                "type": event.type,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
            })
    except WebSocketDisconnect:
        pass
    finally:
        _event_queues.remove(queue)
        await engine.event_bus.unsubscribe("*", _on_event)


class MemoryStoreRequest(BaseModel):
    content: str
    namespace: str | None = None
    metadata: dict[str, Any] | None = None


class MemoryQueryRequest(BaseModel):
    query: str
    namespace: str | None = None
    top_k: int = 5
    min_score: float = 0.0


@router.post("/memory/store")
async def memory_store(request: MemoryStoreRequest):
    """Store a memory entry."""
    engine = _get_engine()
    memory = engine._adapters.get("memory")
    if not memory:
        raise HTTPException(status_code=500, detail="Memory adapter not available")
    await memory.store(
        content=request.content,
        namespace=request.namespace,
        metadata=request.metadata or {},
    )
    return {"status": "stored"}


@router.post("/memory/query")
async def memory_query(request: MemoryQueryRequest):
    """Query memories."""
    engine = _get_engine()
    memory = engine._adapters.get("memory")
    if not memory:
        raise HTTPException(status_code=500, detail="Memory adapter not available")
    results = await memory.query(
        query=request.query,
        top_k=request.top_k,
        namespace=request.namespace,
        min_score=request.min_score,
    )
    return {"results": results}


@router.get("/memory/list")
async def memory_list(namespace: str | None = None):
    """List all memories."""
    engine = _get_engine()
    memory = engine._adapters.get("memory")
    if not memory:
        raise HTTPException(status_code=500, detail="Memory adapter not available")
    entries = await memory.list_all(namespace=namespace)
    return {"entries": entries, "count": len(entries)}


@router.delete("/memory/clear")
async def memory_clear(namespace: str | None = None):
    """Clear memories."""
    engine = _get_engine()
    memory = engine._adapters.get("memory")
    if not memory:
        raise HTTPException(status_code=500, detail="Memory adapter not available")
    await memory.clear(namespace=namespace)
    return {"status": "cleared"}


@router.get("/tools")
async def list_tools():
    """List available tools."""
    engine = _get_engine()
    tool_adapter = engine._adapters.get("tool")
    if not tool_adapter:
        return {"tools": []}
    tools = tool_adapter.list_tools() if hasattr(tool_adapter, "list_tools") else []
    return {"tools": tools}


class RAGIngestTextRequest(BaseModel):
    text: str
    metadata: dict[str, Any] | None = None
    split: bool = True


class RAGIngestFileRequest(BaseModel):
    path: str
    metadata: dict[str, Any] | None = None
    split: bool = True


class RAGRetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.0
    format_output: bool = False
    template: str = "Context:\n{context}\n\nQuery: {query}"


@router.post("/rag/ingest/text")
async def rag_ingest_text(request: RAGIngestTextRequest):
    """Ingest raw text into the RAG document store."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    result = rag.ingest_text(request.text, request.metadata, split=request.split)
    return {"status": "ingested", **result}


@router.post("/rag/ingest/file")
async def rag_ingest_file(request: RAGIngestFileRequest):
    """Ingest a file into the RAG document store."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    try:
        result = rag.ingest_file(request.path, request.metadata, split=request.split)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ingested", **result}


@router.post("/rag/retrieve")
async def rag_retrieve(request: RAGRetrieveRequest):
    """Retrieve relevant document chunks from the RAG store."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    if request.format_output:
        formatted = rag.retrieve_and_format(
            request.query, top_k=request.top_k, template=request.template,
        )
        return {"query": request.query, "formatted": formatted}
    results = rag.retrieve(request.query, top_k=request.top_k, min_score=request.min_score)
    return {"query": request.query, "results": results, "count": len(results)}


@router.get("/rag/documents")
async def rag_list_documents():
    """List all documents in the RAG store."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    docs = rag.store.list_documents()
    return {"documents": docs, "count": len(docs)}


@router.get("/rag/chunks")
async def rag_list_chunks(doc_id: str | None = None):
    """List chunks in the RAG store, optionally filtered by document."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    chunks = rag.store.list_chunks(doc_id=doc_id)
    return {"chunks": chunks, "count": len(chunks)}


@router.get("/rag/stats")
async def rag_stats():
    """Get RAG pipeline statistics."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    return rag.get_stats()


@router.delete("/rag/clear")
async def rag_clear():
    """Clear all documents from the RAG store."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    rag.store.clear()
    return {"status": "cleared"}


@router.delete("/rag/documents/{doc_id}")
async def rag_delete_document(doc_id: str):
    """Delete a specific document and its chunks from the RAG store."""
    engine = _get_engine()
    rag = engine._adapters.get("rag")
    if not rag:
        raise HTTPException(status_code=500, detail="RAG pipeline not available")
    deleted = rag.store.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "doc_id": doc_id}


def _examples_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "examples"


def _scan_examples() -> list[dict[str, Any]]:
    """扫描 examples/（含 integrations/ 子目录）下的 YAML 示例，仅返回白名单映射。"""
    import yaml

    base = _examples_dir()
    if not base.is_dir():
        return []
    files: list[Path] = sorted(base.glob("*.yaml")) + sorted(base.glob("*.yml"))
    sub = base / "integrations"
    if sub.is_dir():
        files += sorted(sub.glob("*.yaml")) + sorted(sub.glob("*.yml"))
    results = []
    for f in files:
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            logger.debug("Skipping unparsable template %s", f, exc_info=True)
            continue
        if not isinstance(data, dict) or "nodes" not in data:
            continue
        nodes = data.get("nodes") or {}
        results.append({
            "filename": f.relative_to(base).as_posix(),
            "id": str(data.get("id") or f.stem),
            "name": str(data.get("name") or f.stem),
            "description": str(data.get("description") or ""),
            "node_count": len(nodes) if isinstance(nodes, dict) else 0,
        })
    return results


@router.get("/examples")
async def list_examples():
    """列出仓库 examples/ 下的真实示例工作流（前端模板库用）。"""
    return {"examples": _scan_examples(), "count": len(_scan_examples())}


@router.get("/examples/{filename:path}")
async def get_example(filename: str):
    """读取单个示例的 YAML 原文。filename 必须命中扫描白名单，防目录穿越。"""
    allowed = {e["filename"]: e for e in _scan_examples()}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Example not found")
    content = (_examples_dir() / filename).read_text(encoding="utf-8")
    return {"filename": filename, "content": content, "meta": allowed[filename]}


class AgentCreateRequest(BaseModel):
    id: str
    name: str
    role: str = "assistant"
    description: str = ""
    system_prompt: str = ""
    tier: str = "default"
    provider: str = ""
    model: str = ""
    tools: list[str] = []
    memory_namespace: str = ""
    max_history: int = 20
    temperature: float = 0.7


class AgentMessageRequest(BaseModel):
    message: str


class CollaborateRequest(BaseModel):
    pattern: str = "pipeline"
    agents: list[str] = []
    task: str = ""
    supervisor: str = ""
    rounds: int = 3


@router.get("/agents")
async def list_agents():
    """List all registered agent definitions."""
    engine = _get_engine()
    registry = engine._agent_registry
    return {"agents": registry.list_definitions()}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get an agent definition."""
    engine = _get_engine()
    registry = engine._agent_registry
    defn = registry.get_definition(agent_id)
    if not defn:
        raise HTTPException(status_code=404, detail="Agent not found")
    instance = registry.get_instance(agent_id)
    return {
        "definition": defn.to_dict(),
        "history_length": len(instance.history) if instance else 0,
    }


@router.post("/agents")
async def create_agent(request: AgentCreateRequest):
    """Register a new agent definition."""
    engine = _get_engine()
    registry = engine._agent_registry
    from cortexflow.agents.definition import AgentDefinition
    defn = AgentDefinition(
        id=request.id,
        name=request.name,
        role=request.role,
        description=request.description,
        system_prompt=request.system_prompt,
        tier=request.tier,
        provider=request.provider,
        model=request.model,
        tools=request.tools,
        memory_namespace=request.memory_namespace,
        max_history=request.max_history,
        temperature=request.temperature,
    )
    registry.register(defn)
    return {"status": "created", "agent_id": request.id}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Unregister an agent."""
    engine = _get_engine()
    engine._agent_registry.unregister(agent_id)
    return {"status": "deleted", "agent_id": agent_id}


@router.post("/agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: AgentMessageRequest):
    """Send a message to an agent and get response."""
    engine = _get_engine()
    registry = engine._agent_registry
    agent = registry.get_or_create(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    model_adapter = engine._adapters.get("model")
    memory_adapter = engine._adapters.get("memory")

    agent.record_user_message(request.message)

    if model_adapter:
        messages = agent.get_conversation_messages(request.message)
        defn = agent.definition
        try:
            result = await model_adapter.invoke(
                tier=defn.tier or "default",
                identity=defn.role or "assistant",
                messages=messages,
                temperature=defn.temperature,
            )
            response = result.get("output", "") if isinstance(result, dict) else str(result)
        except Exception as e:  # noqa: BLE001
            response = f"[LLM 调用失败: {e}]"
    else:
        response = f"[{agent.name}] Acknowledged: {request.message}"

    agent.record_response(response)

    if memory_adapter and defn.memory_namespace:
        await memory_adapter.store(
            content=f"User: {request.message}\n{agent.name}: {response}",
            namespace=defn.memory_namespace,
            metadata={"agent_id": agent_id},
        )

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "response": response,
        "history_length": len(agent.history),
    }


@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset an agent's conversation history."""
    engine = _get_engine()
    engine._agent_registry.reset_instance(agent_id)
    return {"status": "reset", "agent_id": agent_id}


@router.post("/collaborate")
async def run_collaboration(request: CollaborateRequest):
    """Run a multi-agent collaboration pattern."""
    engine = _get_engine()
    registry = engine._agent_registry
    model_adapter = engine._adapters.get("model")

    from cortexflow.agents.collaboration import CollaborationEngine
    collab = CollaborationEngine(registry, model_adapter)

    if request.pattern == "supervisor":
        workers = request.agents[1:] if len(request.agents) > 1 else request.agents
        result = await collab.supervisor_pattern(
            request.supervisor or request.agents[0],
            workers,
            request.task,
        )
    elif request.pattern == "debate":
        result = await collab.debate_pattern(
            request.agents, request.task, rounds=request.rounds,
        )
    elif request.pattern == "pipeline":
        result = await collab.pipeline_pattern(request.agents, request.task)
    elif request.pattern == "vote":
        result = await collab.vote_pattern(request.agents, request.task)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown pattern: {request.pattern}")

    return result


class SkillInvokeRequest(BaseModel):
    params: dict[str, Any] = {}


@router.get("/skills")
async def list_skills(category: str | None = None):
    """List all registered skills with progressive loading status."""
    engine = _get_engine()
    skill_registry = engine._adapters.get("skill_registry")
    if not skill_registry:
        raise HTTPException(status_code=500, detail="Skill registry not available")
    skills = skill_registry.list_skills(category=category)
    return {
        "skills": skills,
        "loaded": skill_registry.get_loaded_count(),
        "total": skill_registry.get_total_count(),
    }


@router.get("/skills/categories")
async def list_skill_categories():
    """List all skill categories."""
    engine = _get_engine()
    skill_registry = engine._adapters.get("skill_registry")
    if not skill_registry:
        raise HTTPException(status_code=500, detail="Skill registry not available")
    return {"categories": skill_registry.list_categories()}


@router.post("/skills/{skill_id}/invoke")
async def invoke_skill(skill_id: str, request: SkillInvokeRequest):
    """Invoke a skill (loads it on-demand if not yet loaded)."""
    engine = _get_engine()
    skill_registry = engine._adapters.get("skill_registry")
    if not skill_registry:
        raise HTTPException(status_code=500, detail="Skill registry not available")
    try:
        result = await skill_registry.invoke(skill_id, **request.params)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))
    return {"skill_id": skill_id, "result": result}


@router.get("/skills/stats")
async def skill_stats():
    """Get skill registry loading statistics."""
    engine = _get_engine()
    skill_registry = engine._adapters.get("skill_registry")
    if not skill_registry:
        raise HTTPException(status_code=500, detail="Skill registry not available")
    return {
        "loaded": skill_registry.get_loaded_count(),
        "total": skill_registry.get_total_count(),
        "categories": skill_registry.list_categories(),
    }


class MemoryManagerStoreRequest(BaseModel):
    content: str
    memory_type: str = "short_term"
    importance: str = "medium"
    namespace: str = "default"
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None


class MemoryManagerSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.0
    namespace: str | None = None
    memory_type: str | None = None


@router.post("/memory-manager/store")
async def memory_manager_store(request: MemoryManagerStoreRequest):
    """Store a memory entry with type and importance."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    from cortexflow.memory.types import MemoryImportance, MemoryType
    try:
        mem_type = MemoryType(request.memory_type)
        importance = MemoryImportance(request.importance)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    memory_id = mm.store(
        content=request.content,
        memory_type=mem_type,
        importance=importance,
        namespace=request.namespace,
        metadata=request.metadata,
        tags=request.tags,
    )
    return {"status": "stored", "memory_id": memory_id}


@router.post("/memory-manager/search")
async def memory_manager_search(request: MemoryManagerSearchRequest):
    """Search across memory stores."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    from cortexflow.memory.types import MemoryType
    mem_type = None
    if request.memory_type:
        try:
            mem_type = MemoryType(request.memory_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    results = mm.search(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        namespace=request.namespace,
        memory_type=mem_type,
    )
    return {"results": results, "count": len(results)}


@router.get("/memory-manager/stats")
async def memory_manager_stats():
    """Get memory manager statistics."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    return mm.get_stats()


@router.get("/memory-manager/list")
async def memory_manager_list(
    namespace: str | None = None,
    memory_type: str | None = None,
):
    """List all memories."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    from cortexflow.memory.types import MemoryType
    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType(memory_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    entries = mm.list_all(namespace=namespace, memory_type=mem_type)
    return {"entries": entries, "count": len(entries)}


@router.post("/memory-manager/consolidate")
async def memory_manager_consolidate(threshold: float = 0.6):
    """Consolidate short-term memories to long-term."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    consolidated = mm.consolidate(threshold=threshold)
    return {"status": "consolidated", "count": consolidated, "stats": mm.get_stats()}


@router.post("/memory-manager/decay")
async def memory_manager_decay():
    """Apply decay to all memories and forget weak ones."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    forgotten = mm.apply_decay()
    return {"status": "decayed", "forgotten": forgotten, "stats": mm.get_stats()}


@router.post("/memory-manager/save")
async def memory_manager_save():
    """Persist memories to disk."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    mm.save_to_disk()
    return {"status": "saved"}


@router.delete("/memory-manager/clear")
async def memory_manager_clear(
    namespace: str | None = None,
    memory_type: str | None = None,
):
    """Clear memories from the manager."""
    engine = _get_engine()
    mm = engine._adapters.get("memory_manager")
    if not mm:
        raise HTTPException(status_code=500, detail="Memory manager not available")
    from cortexflow.memory.types import MemoryType
    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid memory type: {memory_type}")
    cleared = mm.clear(namespace=namespace, memory_type=mem_type)
    return {"status": "cleared", "count": cleared}


# ── Execution history & replay ─────────────────────────────

@router.get("/executions")
async def list_executions(workflow_id: str | None = None, limit: int = 50):
    """List persisted execution runs (newest first)."""
    return {"executions": _execution_log.list(workflow_id=workflow_id, limit=limit)}


@router.get("/executions/{run_id}")
async def get_execution(run_id: int):
    """Get a single run incl. its trace snapshot."""
    record = _execution_log.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Execution not found")
    return record


@router.post("/executions/{run_id}/replay")
async def replay_execution(run_id: int):
    """Re-run a historical execution with its stored variables."""
    record = _execution_log.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Execution not found")
    wf_data = _workflows.get(record["workflow_id"])
    if not wf_data:
        raise HTTPException(status_code=404, detail="Workflow no longer exists")
    engine = _get_engine()
    return await _execute_workflow(engine, record["workflow_id"], wf_data,
                                   record.get("variables"))


# ── Marketplace ────────────────────────────────────────────

class MarketPublishRequest(BaseModel):
    workflow_id: str
    description: str = ""
    tags: list[str] | None = None


@router.get("/marketplace")
async def list_marketplace():
    """List published workflow templates."""
    return {"templates": _marketplace.list()}


@router.post("/marketplace")
async def publish_to_marketplace(req: MarketPublishRequest,
                                 user: str = Depends(require_user)):
    """Publish a workflow (its latest definition) to the marketplace."""
    wf = _workflows.get(req.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    saved = _marketplace.publish(
        workflow_id=req.workflow_id,
        name=wf.get("name") or req.workflow_id,
        description=req.description or (wf.get("definition") or {}).get("description", ""),
        definition=wf["definition"],
        tags=req.tags or [],
        author=user,
    )
    return saved


@router.get("/marketplace/{template_id}")
async def get_marketplace_template(template_id: int):
    """Get a template's full definition (for install/load)."""
    template = _marketplace.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/marketplace/{template_id}")
async def delete_marketplace_template(template_id: int):
    """Delete a published template."""
    if not _marketplace.delete(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "template_id": template_id}
