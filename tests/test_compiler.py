"""Tests for compiler."""


from cortexflow.compiler.compiler import Compiler
from cortexflow.dsl.schema import WorkflowDefinition


def test_compile_basic_workflow():
    """Test compiling a basic workflow."""
    workflow = WorkflowDefinition(
        id="test",
        name="Test",
        entry="start",
        nodes={
            "start": {
                "type": "model",
                "tier": "large",
                "on_success": "__end__",
            }
        },
    )
    compiler = Compiler()
    ir = compiler.compile(workflow)
    assert ir.id == "test"
    assert ir.name == "Test"
    assert ir.entry == "start"
    assert "start" in ir.nodes
    assert ir.nodes["start"].type == "model"
    assert ir.nodes["start"].resolved_tier == "large"


def test_compile_with_variables():
    """Test compiling workflow with variables."""
    workflow = WorkflowDefinition(
        id="test",
        name="Test",
        entry="start",
        variables={
            "input": {
                "type": "string",
                "required": True,
            }
        },
        nodes={
            "start": {
                "type": "model",
                "tier": "large",
                "on_success": "__end__",
            }
        },
    )
    compiler = Compiler()
    ir = compiler.compile(workflow)
    assert "input" in ir.variables
    assert ir.variables["input"].type == "string"
    assert ir.variables["input"].required is True
