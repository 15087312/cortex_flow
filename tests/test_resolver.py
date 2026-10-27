"""Tests for variable resolver."""

import pytest

from cortexflow.utils.resolver import evaluate_condition, resolve_value


def _make_getter(variables):
    def get(path, default=None):
        parts = path.split(".")
        val = variables
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return default
            if val is None:
                return default
        return val
    return get


def test_resolve_simple_string():
    v = {"name": "Alice"}
    assert resolve_value("${name}", _make_getter(v)) == "Alice"


def test_resolve_nested_path():
    v = {"user": {"name": "Bob"}}
    assert resolve_value("${user.name}", _make_getter(v)) == "Bob"


def test_resolve_dict():
    v = {"x": 1}
    result = resolve_value({"key": "${x}"}, _make_getter(v))
    assert result == {"key": 1}


def test_resolve_list():
    v = {"items": [1, 2]}
    result = resolve_value(["${items}", "literal"], _make_getter(v))
    assert result == [[1, 2], "literal"]


def test_resolve_literal():
    v = {}
    assert resolve_value(42, _make_getter(v)) == 42
    assert resolve_value("plain text", _make_getter(v)) == "plain text"


def test_resolve_none():
    v = {}
    assert resolve_value(None, _make_getter(v)) is None


def test_evaluate_truthy():
    v = {"flag": True}
    assert evaluate_condition("${flag}", _make_getter(v)) is True
    v2 = {"flag": False}
    assert evaluate_condition("${flag}", _make_getter(v2)) is False


def test_evaluate_equals():
    v = {"x": 1}
    assert evaluate_condition("${x} == 1", _make_getter(v)) is True
    assert evaluate_condition("${x} == 2", _make_getter(v)) is False


def test_evaluate_not_equals():
    v = {"x": 1}
    assert evaluate_condition("${x} != 2", _make_getter(v)) is True


def test_evaluate_greater():
    v = {"x": 5}
    assert evaluate_condition("${x} > 3", _make_getter(v)) is True
    assert evaluate_condition("${x} > 10", _make_getter(v)) is False


def test_evaluate_less():
    v = {"x": 2}
    assert evaluate_condition("${x} < 5", _make_getter(v)) is True


def test_evaluate_gte():
    v = {"x": 5}
    assert evaluate_condition("${x} >= 5", _make_getter(v)) is True
    assert evaluate_condition("${x} >= 6", _make_getter(v)) is False


def test_evaluate_lte():
    v = {"x": 5}
    assert evaluate_condition("${x} <= 5", _make_getter(v)) is True
    assert evaluate_condition("${x} <= 4", _make_getter(v)) is False


def test_evaluate_bool_literal():
    v = {"x": True}
    assert evaluate_condition("${x} == true", _make_getter(v)) is True


def test_evaluate_string_comparison():
    v = {"status": "active"}
    assert evaluate_condition("${status} == active", _make_getter(v)) is True


def test_evaluate_empty():
    v = {}
    assert evaluate_condition("", _make_getter(v)) is False
    assert evaluate_condition(None, _make_getter(v)) is False
