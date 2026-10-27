"""Cognitive blackboard - Shared state."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class Delegation:
    """Delegation record."""

    id: str
    caller_tier: str
    callee_tier: str
    task: dict[str, Any]
    status: str = "pending"
    progress: float = 0.0
    parent_id: str | None = None


@dataclass
class Observation:
    """Observation record."""

    tier: str
    content: str
    timestamp: float = 0.0


class Blackboard:
    """Cognitive blackboard - shared state across agents.

    Visibility is controlled per-tier via a config dict:
      {"architect": "all", "developer": "observations", "tester": "recent_5"}
    The values mean:
      "all"          — see everything
      "observations" — see only observations + goal/plan
      "recent_N"     — see last N observations
      "none"         — see nothing except own writes
    """

    def __init__(self, visibility: dict[str, str] | None = None):
        self._lock = RLock()
        self._visibility = visibility or {}
        self._goal: str | None = None
        self._plan: str | None = None
        self._observations: list[Observation] = []
        self._delegations: dict[str, Delegation] = {}
        self._dialog: list[dict[str, Any]] = []
        self._custom: dict[str, Any] = {}

    def set_visibility(self, visibility: dict[str, str]) -> None:
        """Update visibility config."""
        with self._lock:
            self._visibility = visibility

    def set_goal(self, goal: str) -> None:
        with self._lock:
            self._goal = goal

    def get_goal(self) -> str | None:
        with self._lock:
            return self._goal

    def set_plan(self, plan: str) -> None:
        with self._lock:
            self._plan = plan

    def get_plan(self) -> str | None:
        with self._lock:
            return self._plan

    def add_observation(self, tier: str, content: str) -> None:
        with self._lock:
            self._observations.append(
                Observation(tier=tier, content=content, timestamp=time.time())
            )

    def get_observations(self, tier: str | None = None, limit: int | None = None) -> list[Observation]:
        with self._lock:
            obs = self._observations
            if tier:
                obs = [o for o in obs if o.tier == tier]
            if limit:
                obs = obs[-limit:]
            return obs

    def write_delegation(self, delegation: Delegation) -> None:
        with self._lock:
            self._delegations[delegation.id] = delegation

    def get_delegation(self, delegation_id: str) -> Delegation | None:
        with self._lock:
            return self._delegations.get(delegation_id)

    def update_delegation_status(self, delegation_id: str, status: str) -> None:
        with self._lock:
            if delegation_id in self._delegations:
                self._delegations[delegation_id].status = status

    def write_dialog(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._dialog.append(entry)

    def read_dialog(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if limit:
                return self._dialog[-limit:]
            return self._dialog

    def set_custom(self, key: str, value: Any) -> None:
        with self._lock:
            self._custom[key] = value

    def get_custom(self, key: str) -> Any:
        with self._lock:
            return self._custom.get(key)

    def snapshot_for(self, tier: str) -> dict[str, Any]:
        """Get tier-filtered snapshot based on dynamic visibility config."""
        with self._lock:
            vis = self._visibility.get(tier, "all")

            snapshot: dict[str, Any] = {
                "goal": self._goal,
                "plan": self._plan,
            }

            if vis == "none":
                snapshot["observations"] = []
                snapshot["delegations"] = []
            elif vis == "observations":
                snapshot["observations"] = list(self._observations)
                snapshot["delegations"] = list(self._delegations.values())
            elif vis.startswith("recent_"):
                try:
                    n = int(vis.split("_", 1)[1])
                except (ValueError, IndexError):
                    n = 5
                snapshot["observations"] = self._observations[-n:]
                snapshot["delegations"] = list(self._delegations.values())
            else:
                snapshot["observations"] = list(self._observations)
                snapshot["delegations"] = list(self._delegations.values())
                snapshot["dialog"] = list(self._dialog)
                snapshot["custom"] = dict(self._custom)

            return snapshot

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "goal": self._goal,
                "plan": self._plan,
                "observations": [
                    {"tier": o.tier, "content": o.content, "timestamp": o.timestamp}
                    for o in self._observations
                ],
                "delegations": {
                    k: {
                        "id": v.id,
                        "caller_tier": v.caller_tier,
                        "callee_tier": v.callee_tier,
                        "task": v.task,
                        "status": v.status,
                        "progress": v.progress,
                    }
                    for k, v in self._delegations.items()
                },
                "dialog": self._dialog,
                "custom": self._custom,
            }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Blackboard":
        """Rebuild a blackboard from :meth:`to_dict` output (best-effort)."""
        bb = cls()
        if not isinstance(data, dict):
            return bb
        bb._goal = data.get("goal")
        bb._plan = data.get("plan")
        for o in data.get("observations") or []:
            if isinstance(o, dict):
                bb._observations.append(Observation(
                    tier=str(o.get("tier", "")),
                    content=o.get("content", ""),
                    timestamp=float(o.get("timestamp") or 0.0),
                ))
        for k, v in (data.get("delegations") or {}).items():
            if isinstance(v, dict):
                bb._delegations[k] = Delegation(
                    id=str(v.get("id", k)),
                    caller_tier=str(v.get("caller_tier", "")),
                    callee_tier=str(v.get("callee_tier", "")),
                    task=v.get("task") if isinstance(v.get("task"), dict) else {},
                    status=str(v.get("status", "pending")),
                    progress=float(v.get("progress") or 0.0),
                )
        if isinstance(data.get("dialog"), list):
            bb._dialog = data["dialog"]
        if isinstance(data.get("custom"), dict):
            bb._custom = data["custom"]
        return bb
