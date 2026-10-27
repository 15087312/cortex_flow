"""Interval scheduler - Run workflows with `schedule` sections periodically.

A workflow opts in via its definition::

    schedule:
      enabled: true
      interval_seconds: 300
      variables: {city: Shanghai}

The scheduler ticks every ``poll_seconds`` (default 15s) and starts any
due workflow whose previous run finished (no overlap). State persists in
SQLite so restarts don't double-fire or lose the last-run timestamp.
Cron expressions are deliberately out of scope; intervals cover the
need with zero new dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


class Scheduler:
    """Poll persisted workflows and run due schedules."""

    def __init__(
        self,
        store: Any,
        state: Any,
        run_workflow: Callable[..., Any],
        poll_seconds: float = 15.0,
        min_interval_seconds: float = 10.0,
    ):
        self._store = store
        self._state = state
        self._run_workflow = run_workflow
        self._poll_seconds = poll_seconds
        self._min_interval = min_interval_seconds
        self._running: set[str] = set()
        self._task: asyncio.Task | None = None
        self._stopped = False

    @staticmethod
    def schedule_of(definition: dict[str, Any]) -> dict[str, Any] | None:
        """Extract and normalize a workflow's schedule section."""
        sched = (definition or {}).get("schedule")
        if not isinstance(sched, dict) or not sched.get("enabled"):
            return None
        try:
            interval = float(sched.get("interval_seconds", 0))
        except (TypeError, ValueError):
            return None
        if interval <= 0:
            return None
        return {
            "enabled": True,
            "interval_seconds": interval,
            "variables": sched.get("variables") or {},
        }

    def due_workflows(self) -> list[dict[str, Any]]:
        """Workflows whose schedule is due (and not already running)."""
        now = datetime.now(timezone.utc)
        due = []
        for wf in self._store.list():
            sched = self.schedule_of(wf.get("definition") or {})
            if not sched:
                continue
            if sched["interval_seconds"] < self._min_interval:
                continue
            if wf["id"] in self._running:
                continue
            last_run = _parse_time(self._state.get(wf["id"]).get("last_run"))
            elapsed = (now - last_run).total_seconds() if last_run else float("inf")
            if elapsed >= sched["interval_seconds"]:
                due.append({"workflow": wf, "schedule": sched})
        return due

    async def tick(self) -> list[str]:
        """Run all due workflows once. Returns started workflow ids."""
        started = []
        for item in self.due_workflows():
            wid = item["workflow"]["id"]
            self._running.add(wid)
            started.append(wid)
            asyncio.create_task(self._run_guarded(
                wid, item["workflow"], item["schedule"],
            ))
        return started

    async def _run_guarded(self, workflow_id: str, workflow: dict[str, Any],
                           schedule: dict[str, Any]) -> None:
        try:
            await self._run_workflow(workflow, schedule.get("variables") or {})
            self._state.record_run(workflow_id, "completed")
        except Exception as exc:  # a failing schedule must not kill the loop
            logger.warning("Scheduled run of %s failed: %s", workflow_id, exc)
            self._state.record_run(workflow_id, f"failed: {exc}")
        finally:
            self._running.discard(workflow_id)

    async def start(self) -> None:
        """Poll forever until :meth:`stop`."""
        self._stopped = False
        while not self._stopped:
            try:
                await self.tick()
            except Exception as exc:  # never let the loop die
                logger.warning("Scheduler tick failed: %s", exc)
            await asyncio.sleep(self._poll_seconds)

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._stopped = True

    def status(self) -> list[dict[str, Any]]:
        """Human-readable schedule overview for the API."""
        out = []
        for wf in self._store.list():
            sched = self.schedule_of(wf.get("definition") or {})
            if not sched:
                continue
            st = self._state.get(wf["id"])
            out.append({
                "workflow_id": wf["id"],
                "name": wf.get("name", ""),
                "enabled": True,
                "interval_seconds": sched["interval_seconds"],
                "running": wf["id"] in self._running,
                "last_run": st.get("last_run"),
                "run_count": st.get("run_count", 0),
                "last_status": st.get("last_status", ""),
            })
        return out
