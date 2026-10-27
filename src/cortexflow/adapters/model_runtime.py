"""Model runtime adapter - Real LLM integration via httpx."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from cortexflow.adapters.base import ModelRuntimeAdapter
from cortexflow.config import config

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0


class RealModelRuntimeAdapter(ModelRuntimeAdapter):
    """LLM adapter supporting OpenAI-compatible and Anthropic APIs."""

    def __init__(self, default_provider: str | None = None) -> None:
        self._default_provider = default_provider
        self._client: httpx.AsyncClient | None = None
        self._tier_cache: dict[str, dict[str, Any]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        return self._client

    def set_tier_cache(self, tiers: dict[str, Any]) -> None:
        self._tier_cache = {
            name: {
                "model": t.model,
                "provider": t.provider,
                "metadata": t.metadata if hasattr(t, "metadata") else {},
            }
            for name, t in tiers.items()
        }

    def _resolve_tier(self, tier: str) -> dict[str, Any]:
        if tier in self._tier_cache:
            return self._tier_cache[tier]
        return {"model": None, "provider": None, "metadata": {}}

    def _get_model_and_provider(self, tier: str, identity: str) -> tuple[str, str]:
        tier_info = self._resolve_tier(tier)
        provider = tier_info.get("provider") or self._default_provider or "openai"
        model = tier_info.get("model") or identity or "gpt-4o"

        provider_meta = tier_info.get("metadata", {})
        if "model" in provider_meta:
            model = provider_meta["model"]
        if "provider" in provider_meta:
            provider = provider_meta["provider"]

        return model, provider

    async def invoke(
        self,
        tier: str,
        identity: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        model, provider = self._get_model_and_provider(tier, identity)
        output_format = kwargs.get("output_format", "text")

        if provider == "anthropic":
            return await self._call_anthropic(model, messages, **kwargs)
        return await self._call_openai_compatible(model, provider, messages, **kwargs)

    async def _call_openai_compatible(
        self,
        model: str,
        provider: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        base_url = config.get_base_url(provider)
        api_key = config.get_api_key(provider)

        if not base_url:
            from cortexflow.config import PROVIDER_DEFAULTS
            if provider in PROVIDER_DEFAULTS:
                base_url = PROVIDER_DEFAULTS[provider]["base_url"]

        url = f"{base_url.rstrip('/')}/chat/completions"

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        temperature = kwargs.get("temperature")
        if temperature is not None:
            body["temperature"] = temperature

        max_tokens = kwargs.get("max_tokens")
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        output_format = kwargs.get("output_format", "text")
        if output_format == "json":
            body["response_format"] = {"type": "json_object"}

        client = await self._get_client()
        try:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("LLM API error %d: %s", e.response.status_code, e.response.text)
            raise RuntimeError(
                f"LLM API error {e.response.status_code}: {e.response.text[:500]}"
            ) from e
        except httpx.RequestError as e:
            logger.error("LLM request failed: %s", e)
            raise RuntimeError(f"LLM request failed: {e}") from e

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        content = message.get("content", "")
        if output_format == "json" and isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass

        return {
            "output": content,
            "model": model,
            "provider": provider,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "finish_reason": choice.get("finish_reason"),
        }

    async def _call_anthropic(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        base_url = config.get_base_url("anthropic")
        api_key = config.get_api_key("anthropic")

        if not base_url:
            base_url = "https://api.anthropic.com/v1"

        url = f"{base_url.rstrip('/')}/messages"

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]

        body: dict[str, Any] = {
            "model": model,
            "messages": user_msgs,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system_msgs:
            body["system"] = "\n\n".join(system_msgs)

        temperature = kwargs.get("temperature")
        if temperature is not None:
            body["temperature"] = temperature

        client = await self._get_client()
        try:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Anthropic API error %d: %s", e.response.status_code, e.response.text)
            raise RuntimeError(
                f"Anthropic API error {e.response.status_code}: {e.response.text[:500]}"
            ) from e
        except httpx.RequestError as e:
            logger.error("Anthropic request failed: %s", e)
            raise RuntimeError(f"Anthropic request failed: {e}") from e

        content_blocks = data.get("content", [])
        text = "".join(
            b.get("text", "") for b in content_blocks if b.get("type") == "text"
        )
        usage = data.get("usage", {})

        return {
            "output": text,
            "model": model,
            "provider": "anthropic",
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
            "finish_reason": data.get("stop_reason"),
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
