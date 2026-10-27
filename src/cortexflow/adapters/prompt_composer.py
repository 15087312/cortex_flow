"""Prompt composer adapter - Interface with PromptComposer."""

from __future__ import annotations

from typing import Any

from cortexflow.adapters.base import PromptComposerAdapter


class DefaultPromptComposerAdapter(PromptComposerAdapter):
    """Default prompt composer adapter (mock implementation)."""

    def build_system(self, context: dict[str, Any]) -> str:
        """Build system prompt."""
        # TODO: Integrate with actual PromptComposer
        identity = context.get("identity", "default")
        role = context.get("role", "assistant")
        return f"You are {identity}, a {role}."
