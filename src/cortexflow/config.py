"""CortexFlow configuration - API keys and provider settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderConfig:
    """Provider configuration."""

    name: str
    base_url: str
    api_key: str
    model: str
    api_version: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
        "env_key": "",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o",
        "env_key": "OPENROUTER_API_KEY",
    },
    "dashscope": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "env_key": "DASHSCOPE_API_KEY",
    },
}


class CortexConfig:
    """Global configuration loaded from environment."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._load_from_env()

    def _load_from_env(self) -> None:
        for name, defaults in PROVIDER_DEFAULTS.items():
            api_key = os.environ.get(defaults["env_key"], "")
            base_url = os.environ.get(
                f"{name.upper()}_BASE_URL", defaults["base_url"]
            )
            model = os.environ.get(f"{name.upper()}_MODEL", defaults["model"])
            self._providers[name] = ProviderConfig(
                name=name,
                base_url=base_url,
                api_key=api_key,
                model=model,
            )

        custom = os.environ.get("CORTEX_PROVIDER_JSON")
        if custom:
            import json
            for pdef in json.loads(custom):
                self._providers[pdef["name"]] = ProviderConfig(**pdef)

    def get_provider(self, name: str | None = None) -> ProviderConfig | None:
        if name and name in self._providers:
            return self._providers[name]
        for p in self._providers.values():
            if p.api_key:
                return p
        return self._providers.get("openai")

    def get_api_key(self, provider: str | None = None) -> str:
        p = self.get_provider(provider)
        return p.api_key if p else ""

    def get_base_url(self, provider: str | None = None) -> str:
        p = self.get_provider(provider)
        return p.base_url if p else ""


config = CortexConfig()
