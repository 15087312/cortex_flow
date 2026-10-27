"""Tests for integration nodes - http_request and transform."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortexflow.nodes.http_request import HttpRequestNode
from cortexflow.nodes.transform import TransformNode
from cortexflow.nodes.registry import NodeRegistry
from cortexflow.runtime.context import ExecutionContext


# --- Registry tests ---

def test_http_request_registered():
    assert "http_request" in NodeRegistry.list_types()


def test_transform_registered():
    assert "transform" in NodeRegistry.list_types()


# --- HttpRequestNode tests ---

@pytest.mark.asyncio
async def test_http_get_request():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"data": "test"}
    mock_response.text = '{"data": "test"}'

    node = HttpRequestNode(
        node_id="http1",
        config={"url": "https://api.example.com/data", "method": "GET"},
    )
    context = ExecutionContext()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await node.execute(context)

    assert result["status_code"] == 200
    assert result["body"] == {"data": "test"}
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_http_post_request_with_body():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"id": 1}
    mock_response.text = '{"id": 1}'

    node = HttpRequestNode(
        node_id="http2",
        config={
            "url": "https://api.example.com/items",
            "method": "POST",
            "body": {"name": "test"},
        },
    )
    context = ExecutionContext()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await node.execute(context)

    assert result["status_code"] == 201
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_http_request_variable_resolution():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.text = "ok"

    node = HttpRequestNode(
        node_id="http3",
        config={
            "url": "${api_url}/endpoint",
            "method": "GET",
            "headers": {"Authorization": "Bearer ${token}"},
        },
    )
    context = ExecutionContext(variables={
        "api_url": "https://api.example.com",
        "token": "my-secret-token",
    })

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await node.execute(context)

    assert result["status_code"] == 200
    call_kwargs = mock_client.get.call_args
    assert "Bearer my-secret-token" in str(call_kwargs)


@pytest.mark.asyncio
async def test_http_request_no_url_raises():
    node = HttpRequestNode(node_id="http4", config={})
    context = ExecutionContext()

    with pytest.raises(ValueError, match="url"):
        await node.execute(context)


@pytest.mark.asyncio
async def test_http_request_fail_on_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.text = "Internal Server Error"

    node = HttpRequestNode(
        node_id="http5",
        config={"url": "https://api.example.com/fail", "fail_on_error": True},
    )
    context = ExecutionContext()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="HTTP 500"):
            await node.execute(context)


@pytest.mark.asyncio
async def test_http_request_fail_on_error_disabled():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.text = "Not Found"

    node = HttpRequestNode(
        node_id="http6",
        config={
            "url": "https://api.example.com/missing",
            "fail_on_error": False,
        },
    )
    context = ExecutionContext()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await node.execute(context)

    assert result["status_code"] == 404


@pytest.mark.asyncio
async def test_http_request_unsupported_method():
    node = HttpRequestNode(
        node_id="http7",
        config={"url": "https://example.com", "method": "INVALID"},
    )
    context = ExecutionContext()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            await node.execute(context)


# --- TransformNode tests ---

@pytest.mark.asyncio
async def test_transform_jsonpath_extract():
    node = TransformNode(
        node_id="t1",
        config={
            "input": "${data}",
            "mapping": {
                "user_name": "$.user.name",
                "user_email": "$.user.email",
            },
        },
    )
    context = ExecutionContext(variables={
        "data": {"user": {"name": "Alice", "email": "alice@example.com"}},
    })

    result = await node.execute(context)

    assert result["user_name"] == "Alice"
    assert result["user_email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_transform_variable_reference():
    node = TransformNode(
        node_id="t2",
        config={
            "mapping": {
                "name": "${user_name}",
                "role": "${user_role}",
            },
        },
    )
    context = ExecutionContext(variables={
        "user_name": "Bob",
        "user_role": "admin",
    })

    result = await node.execute(context)

    assert result["name"] == "Bob"
    assert result["role"] == "admin"


@pytest.mark.asyncio
async def test_transform_template_eval():
    node = TransformNode(
        node_id="t3",
        config={
            "input": "${data}",
            "mapping": {
                "greeting": "{{user.name}} ({{user.role}})",
            },
        },
    )
    context = ExecutionContext(variables={
        "data": {"user": {"name": "Charlie", "role": "editor"}},
    })

    result = await node.execute(context)

    assert result["greeting"] == "Charlie (editor)"


@pytest.mark.asyncio
async def test_transform_nested_output():
    node = TransformNode(
        node_id="t4",
        config={
            "input": "${data}",
            "mapping": {
                "profile.name": "$.name",
                "profile.age": "$.age",
                "meta.source": "api",
            },
        },
    )
    context = ExecutionContext(variables={
        "data": {"name": "Dave", "age": 30},
    })

    result = await node.execute(context)

    assert result["profile"]["name"] == "Dave"
    assert result["profile"]["age"] == 30
    assert result["meta"]["source"] == "api"


@pytest.mark.asyncio
async def test_transform_json_output():
    node = TransformNode(
        node_id="t5",
        config={
            "mapping": {"key": "value"},
            "output_format": "json",
        },
    )
    context = ExecutionContext()

    result = await node.execute(context)

    parsed = json.loads(result)
    assert parsed["key"] == "value"


@pytest.mark.asyncio
async def test_transform_no_mapping_passthrough():
    node = TransformNode(
        node_id="t6",
        config={"input": "${data}"},
    )
    context = ExecutionContext(variables={"data": {"a": 1}})

    result = await node.execute(context)

    assert result == {"a": 1}


@pytest.mark.asyncio
async def test_transform_literal_values():
    node = TransformNode(
        node_id="t7",
        config={
            "mapping": {
                "static_str": "hello",
                "static_num": 42,
                "static_bool": True,
            },
        },
    )
    context = ExecutionContext()

    result = await node.execute(context)

    assert result["static_str"] == "hello"
    assert result["static_num"] == 42
    assert result["static_bool"] is True


@pytest.mark.asyncio
async def test_transform_list_mapping():
    node = TransformNode(
        node_id="t8",
        config={
            "input": "${data}",
            "mapping": {
                "tags": ["$.tag1", "$.tag2"],
            },
        },
    )
    context = ExecutionContext(variables={
        "data": {"tag1": "python", "tag2": "workflow"},
    })

    result = await node.execute(context)

    assert result["tags"] == ["python", "workflow"]


@pytest.mark.asyncio
async def test_transform_missing_jsonpath_returns_none():
    node = TransformNode(
        node_id="t9",
        config={
            "input": "${data}",
            "mapping": {
                "missing": "$.nonexistent.path",
            },
        },
    )
    context = ExecutionContext(variables={"data": {"a": 1}})

    result = await node.execute(context)

    assert result["missing"] is None
