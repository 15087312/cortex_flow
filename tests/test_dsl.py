"""Tests for DSL layer."""

import pytest

from cortexflow.dsl.parser import Parser
from cortexflow.dsl.schema import NodeType, WorkflowDefinition
from cortexflow.dsl.validator import ValidationError, Validator


def test_parse_basic_workflow():
    """Test parsing a basic workflow."""
    yaml_content = """
id: "test_flow"
name: "Test Flow"
entry: "start"
nodes:
  start:
    type: "model"
    tier: "large"
    on_success: "__end__"
"""
    parser = Parser()
    workflow = parser.parse_string(yaml_content)
    assert workflow.id == "test_flow"
    assert workflow.name == "Test Flow"
    assert workflow.entry == "start"
    assert "start" in workflow.nodes
    assert workflow.nodes["start"].type == NodeType.MODEL


def test_validate_entry_exists():
    """Test validation of entry node."""
    workflow = WorkflowDefinition(
        id="test",
        name="Test",
        entry="nonexistent",
        nodes={
            "start": {
                "type": "model",
                "tier": "large",
            }
        },
    )
    validator = Validator()
    with pytest.raises(ValidationError, match="Entry node"):
        validator.validate(workflow)


def test_validate_unreachable_nodes():
    """Test validation of unreachable nodes."""
    workflow = WorkflowDefinition(
        id="test",
        name="Test",
        entry="start",
        nodes={
            "start": {
                "type": "model",
                "tier": "large",
                "on_success": "__end__",
            },
            "orphan": {
                "type": "model",
                "tier": "large",
            },
        },
    )
    validator = Validator()
    with pytest.raises(ValidationError, match="Unreachable"):
        validator.validate(workflow)


def test_validate_valid_workflow():
    """Test validation of valid workflow."""
    workflow = WorkflowDefinition(
        id="test",
        name="Test",
        entry="start",
        nodes={
            "start": {
                "type": "model",
                "tier": "large",
                "on_success": "end",
            },
            "end": {
                "type": "state",
                "on_success": "__end__",
            },
        },
    )
    validator = Validator()
    validator.validate(workflow)  # Should not raise
