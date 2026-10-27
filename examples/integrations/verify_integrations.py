"""Verify integration workflows compile and execute correctly with mocked HTTP."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortexflow.compiler.compiler import Compiler
from cortexflow.dsl.parser import Parser
from cortexflow.runtime.executor import Executor
from cortexflow.runtime.context import ExecutionContext
from cortexflow.runtime.states import FlowState


def _mock_httpx_response(status_code=200, body=None, content_type="application/json"):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.headers = {"content-type": content_type}
    mock_resp.text = str(body) if body else ""
    if content_type == "application/json" and isinstance(body, dict):
        mock_resp.json.return_value = body
        mock_resp.text = str(body).replace("'", '"')
    else:
        mock_resp.json.side_effect = Exception("not json")
    return mock_resp


def _make_mock_client(responses: list):
    call_idx = {"i": 0}
    mock_client = AsyncMock()

    async def handle_request(*args, **kwargs):
        idx = call_idx["i"]
        call_idx["i"] += 1
        return responses[idx] if idx < len(responses) else responses[-1]

    mock_client.get = handle_request
    mock_client.post = handle_request
    mock_client.put = handle_request
    mock_client.delete = handle_request
    mock_client.patch = handle_request
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_slack_notification():
    print("=== Slack Notification Pipeline ===")
    yaml_path = Path(__file__).parent / "slack_notification.yaml"
    parser = Parser()
    workflow = parser.parse_file(str(yaml_path))
    compiler = Compiler()
    flow = compiler.compile(workflow)

    print(f"  Nodes: {list(flow.nodes.keys())}")
    assert "fetch_user" in flow.nodes
    assert "format_message" in flow.nodes
    assert "send_slack" in flow.nodes

    fetch_resp = _mock_httpx_response(200, {
        "name": "Alice", "email": "alice@test.com", "role": "engineer"
    })
    slack_resp = _mock_httpx_response(200, "ok", "text/plain")
    mock_client = _make_mock_client([fetch_resp, slack_resp])

    ctx = ExecutionContext(variables={
        "api_base_url": "https://api.example.com",
        "slack_webhook_url": "https://hooks.slack.com/test",
        "user_id": "u123",
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        executor = Executor()
        await executor.execute(flow, ctx)

    assert ctx.state == FlowState.COMPLETED
    assert ctx.variables.get("notification_status") == "sent"
    assert ctx.variables.get("notified_user") == "Alice"
    print("  PASSED - notification sent for Alice")


async def test_github_issue():
    print("\n=== GitHub Issue Creator ===")
    yaml_path = Path(__file__).parent / "github_issue.yaml"
    parser = Parser()
    workflow = parser.parse_file(str(yaml_path))
    compiler = Compiler()
    flow = compiler.compile(workflow)

    print(f"  Nodes: {list(flow.nodes.keys())}")

    create_resp = _mock_httpx_response(201, {
        "number": 42,
        "html_url": "https://github.com/test/repo/issues/42",
        "state": "open",
    })
    mock_client = _make_mock_client([create_resp])

    ctx = ExecutionContext(variables={
        "github_token": "ghp_test",
        "repo_owner": "test",
        "repo_name": "repo",
        "issue_title": "Bug report",
        "issue_body": "Something is broken",
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        executor = Executor()
        await executor.execute(flow, ctx)

    assert ctx.state == FlowState.COMPLETED
    result = ctx.variables.get("created_issue")
    assert result is not None
    assert result["issue_number"] == 42
    assert result["issue_url"] == "https://github.com/test/repo/issues/42"
    print(f"  PASSED - issue #{result['issue_number']} created")


async def test_webhook_relay():
    print("\n=== Webhook Relay & Fan-out ===")
    yaml_path = Path(__file__).parent / "webhook_relay.yaml"
    parser = Parser()
    workflow = parser.parse_file(str(yaml_path))
    compiler = Compiler()
    flow = compiler.compile(workflow)

    print(f"  Nodes: {list(flow.nodes.keys())}")

    resp_a = _mock_httpx_response(200, "ok", "text/plain")
    resp_b = _mock_httpx_response(200, "ok", "text/plain")
    mock_client = _make_mock_client([resp_a, resp_b])

    ctx = ExecutionContext(variables={
        "webhook_payload": {
            "type": "order.created",
            "data": {"order_id": "ORD-001", "amount": 99.99},
            "timestamp": "2026-09-07T10:00:00Z",
        },
        "endpoint_a": "https://service-a.example.com/webhook",
        "endpoint_b": "https://service-b.example.com/events",
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        executor = Executor()
        await executor.execute(flow, ctx)

    assert ctx.state == FlowState.COMPLETED
    assert ctx.variables.get("relay_status") == "completed"
    targets = ctx.variables.get("relay_targets")
    assert len(targets) == 2
    print(f"  PASSED - relayed to {len(targets)} endpoints")


async def main():
    print("Integration Workflow Verification\n")
    results = []

    for name, test_fn in [
        ("Slack Notification", test_slack_notification),
        ("GitHub Issue Creator", test_github_issue),
        ("Webhook Relay", test_webhook_relay),
    ]:
        try:
            await test_fn()
            results.append((name, "PASSED"))
        except Exception as e:
            results.append((name, f"FAILED: {e}"))
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print("Summary:")
    for name, status in results:
        print(f"  {name}: {status}")

    all_passed = all(s == "PASSED" for _, s in results)
    print(f"\n{'All tests passed!' if all_passed else 'Some tests failed!'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
