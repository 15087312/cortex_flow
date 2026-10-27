"""Tests for observability - tracer and metrics."""

import pytest

from cortexflow.observability.metrics import MetricsCollector
from cortexflow.observability.tracer import Tracer


@pytest.mark.asyncio
async def test_tracer_trace_and_complete():
    tracer = Tracer()
    trace = await tracer.trace_node(flow_id="f1", node_id="n1", node_type="model")
    assert trace.node_id == "n1"
    assert trace.state == "pending"
    assert trace.completed_at is None

    await tracer.complete_trace(flow_id="f1", node_id="n1", state="completed")
    assert trace.state == "completed"
    assert trace.completed_at is not None


@pytest.mark.asyncio
async def test_tracer_get_trace():
    tracer = Tracer()
    await tracer.trace_node(flow_id="f1", node_id="n1", node_type="model")
    await tracer.trace_node(flow_id="f1", node_id="n2", node_type="state")
    traces = await tracer.get_trace("f1")
    assert len(traces) == 2


@pytest.mark.asyncio
async def test_tracer_empty_flow():
    tracer = Tracer()
    traces = await tracer.get_trace("nonexistent")
    assert traces == []


@pytest.mark.asyncio
async def test_tracer_error_trace():
    tracer = Tracer()
    await tracer.trace_node(flow_id="f1", node_id="n1", node_type="model")
    await tracer.complete_trace(flow_id="f1", node_id="n1", state="failed", error="boom")
    traces = await tracer.get_trace("f1")
    assert traces[0].error == "boom"


def test_metrics_record_node_duration():
    m = MetricsCollector()
    m.record_node_duration("model", 1.5)
    m.record_node_duration("model", 2.5)
    stats = m.get_stats()
    assert stats["node_counts"]["model"] == 2
    assert stats["avg_node_durations"]["model"] == 2.0


def test_metrics_record_flow_completion():
    m = MetricsCollector()
    m.record_flow_completion(3.0)
    m.record_flow_completion(5.0)
    stats = m.get_stats()
    assert stats["flows_completed"] == 2
    assert stats["avg_flow_duration"] == 4.0


def test_metrics_record_error():
    m = MetricsCollector()
    m.record_error("model")
    m.record_error("model")
    m.record_error("tool")
    stats = m.get_stats()
    assert stats["error_counts"]["model"] == 2
    assert stats["error_counts"]["tool"] == 1


def test_metrics_empty_stats():
    m = MetricsCollector()
    stats = m.get_stats()
    assert stats["flows_completed"] == 0
    assert stats["avg_flow_duration"] == 0
    assert stats["node_counts"] == {}
