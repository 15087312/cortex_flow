"""HTTP Request node - Make HTTP calls to external APIs."""

from __future__ import annotations

from typing import Any

import httpx

from cortexflow.nodes.base import BaseNode
from cortexflow.nodes.registry import NodeRegistry


@NodeRegistry.register("http_request")
class HttpRequestNode(BaseNode):
    """Make HTTP requests to external APIs."""

    async def execute(self, context: Any) -> Any:
        url = self.resolve(self.config.get("url"), context)
        method = self.config.get("method", "GET").upper()
        headers = self.resolve(self.config.get("headers", {}), context)
        body = self.resolve(self.config.get("body"), context)
        timeout = self.config.get("timeout", 30)

        if not url:
            raise ValueError("HTTP request node requires 'url'")

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=body)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=body)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                elif method == "PATCH":
                    response = await client.patch(url, headers=headers, json=body)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                result = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": self._parse_response(response),
                }

                if self.config.get("fail_on_error", True) and response.status_code >= 400:
                    raise RuntimeError(
                        f"HTTP {response.status_code}: {response.text}"
                    )

                return result

            except httpx.TimeoutException:
                raise TimeoutError(f"HTTP request timed out after {timeout}s")
            except httpx.RequestError as e:
                raise RuntimeError(f"HTTP request failed: {e}")

    def _parse_response(self, response: httpx.Response) -> Any:
        """Parse response body based on content type."""
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                return response.json()
            except Exception:
                return response.text
        else:
            return response.text
