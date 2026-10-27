"""FastAPI server."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cortexflow.api import routes as routes_module
from cortexflow.api.routes import public, router


async def _run_scheduled(workflow: dict, variables: dict) -> None:
    """Execute one scheduled run; results land in _executions for the UI."""
    from cortexflow.dsl.schema import WorkflowDefinition
    from cortexflow.runtime.events import AskQuestion, WaitEvent

    engine = routes_module._get_engine()
    wf = WorkflowDefinition(**workflow["definition"])
    try:
        result = await engine.run(wf, variables)
        routes_module._executions[wf.id] = {
            "status": "completed", "result": result, "scheduled": True,
        }
    except (AskQuestion, WaitEvent) as w:
        # Nobody answers a scheduled ask — park it as suspended.
        routes_module._executions[wf.id] = {
            "status": "suspended", "scheduled": True,
            "question": getattr(w, "question", None),
        }
    except Exception as exc:  # noqa: BLE001
        routes_module._executions[wf.id] = {
            "status": "failed", "error": str(exc), "scheduled": True,
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the interval scheduler with the server."""
    from cortexflow.scheduler import Scheduler
    from cortexflow.store.schedules import ScheduleState

    scheduler = Scheduler(
        store=routes_module._workflows,
        state=ScheduleState(),
        run_workflow=_run_scheduled,
    )
    routes_module._scheduler = scheduler
    task = asyncio.create_task(scheduler.start())
    try:
        yield
    finally:
        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        routes_module._scheduler = None


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="CortexFlow API",
        description="Local-first, cognitive-driven workflow orchestration engine",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(public, prefix="/api")

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    frontend_dist = project_root / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

    return app
