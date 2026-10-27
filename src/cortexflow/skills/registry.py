"""Skill registry with progressive loading."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from cortexflow.skills.definition import SkillDefinition, SkillHandler


class SkillRegistry:
    """Registry that supports lazy/progressive skill loading."""

    def __init__(self) -> None:
        self._definitions: dict[str, SkillDefinition] = {}
        self._lock = asyncio.Lock()

    def register(
        self,
        skill_id: str,
        name: str,
        description: str,
        handler: SkillHandler | None = None,
        loader: Callable[[], Awaitable[SkillHandler]] | None = None,
        category: str = "general",
        tags: list[str] | None = None,
        triggers: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillDefinition:
        defn = SkillDefinition(
            id=skill_id,
            name=name,
            description=description,
            category=category,
            tags=tags or [],
            triggers=triggers or [],
            parameters=parameters or {},
            metadata=metadata or {},
            _handler=handler,
            _loader=loader,
            _loaded=handler is not None,
        )
        self._definitions[skill_id] = defn
        return defn

    def register_definition(self, defn: SkillDefinition) -> None:
        self._definitions[defn.id] = defn

    def unregister(self, skill_id: str) -> bool:
        if skill_id in self._definitions:
            del self._definitions[skill_id]
            return True
        return False

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._definitions.get(skill_id)

    async def invoke(self, skill_id: str, **kwargs: Any) -> Any:
        defn = self._definitions.get(skill_id)
        if not defn:
            raise KeyError(f"Skill '{skill_id}' not found")

        async with self._lock:
            handler = await defn.load()

        return await handler(**kwargs)

    def list_skills(self, category: str | None = None) -> list[dict[str, Any]]:
        skills = list(self._definitions.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return [s.to_dict() for s in skills]

    def list_categories(self) -> list[str]:
        return sorted({s.category for s in self._definitions.values()})

    def find_by_trigger(self, text: str) -> list[SkillDefinition]:
        text_lower = text.lower()
        results = []
        for skill in self._definitions.values():
            for trigger in skill.triggers:
                if trigger.lower() in text_lower:
                    results.append(skill)
                    break
        return results

    def find_by_tag(self, tag: str) -> list[SkillDefinition]:
        return [s for s in self._definitions.values() if tag in s.tags]

    def unload_all(self) -> None:
        for skill in self._definitions.values():
            skill.unload()

    def get_loaded_count(self) -> int:
        return sum(1 for s in self._definitions.values() if s.is_loaded)

    def get_total_count(self) -> int:
        return len(self._definitions)
