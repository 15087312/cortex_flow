"""Tests for template registry."""

from cortexflow.templates.registry import TemplateRegistry


def test_builtin_templates_registered():
    reg = TemplateRegistry()
    templates = reg.list()
    assert "sequential_flow" in templates
    assert "parallel_flow" in templates
    assert "map_reduce_flow" in templates
    assert "loop_flow" in templates


def test_get_template():
    reg = TemplateRegistry()
    t = reg.get("sequential_flow")
    assert t is not None
    assert t["id"] == "sequential_flow"
    assert "definition" in t


def test_register_custom_template():
    reg = TemplateRegistry()
    reg.register("custom", {"id": "custom", "name": "Custom"})
    assert reg.get("custom") is not None
    assert "custom" in reg.list()


def test_unregister_template():
    reg = TemplateRegistry()
    reg.register("temp", {"id": "temp"})
    assert reg.get("temp") is not None
    reg.unregister("temp")
    assert reg.get("temp") is None


def test_list_all():
    reg = TemplateRegistry()
    all_templates = reg.list_all()
    assert isinstance(all_templates, dict)
    assert len(all_templates) >= 4
