"""Tests for Coze-style code / database / text nodes."""

import pytest

from cortexflow.dsl.validator import ValidationError
from cortexflow.engine import Engine
from cortexflow.nodes.code import CodeNode
from cortexflow.nodes.database import DatabaseNode
from cortexflow.nodes.text import TextNode
from cortexflow.runtime.context import ExecutionContext

# ── code node ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_code_node_uses_declared_inputs_as_variables():
    node = CodeNode("c", {
        "code": "output = sum(numbers) * factor",
        "inputs": {"numbers": "${numbers}", "factor": 2},
    })
    ctx = ExecutionContext(variables={"numbers": [1, 2, 3]})
    assert await node.execute(ctx) == 12


@pytest.mark.asyncio
async def test_code_node_exposes_inputs_mapping():
    node = CodeNode("c", {
        "code": 'output = {"keys": sorted(inputs), "first": inputs["a"]}',
        "inputs": {"a": 1, "b": 2},
    })
    result = await node.execute(ExecutionContext())
    assert result == {"keys": ["a", "b"], "first": 1}


@pytest.mark.asyncio
async def test_code_node_without_output_returns_none():
    node = CodeNode("c", {"code": "x = 1"})
    assert await node.execute(ExecutionContext()) is None


@pytest.mark.asyncio
async def test_code_node_missing_code_raises():
    with pytest.raises(ValueError, match="requires 'code'"):
        await CodeNode("c", {}).execute(ExecutionContext())


@pytest.mark.asyncio
async def test_code_node_blocks_unsafe_builtins():
    node = CodeNode("c", {"code": "output = open('/etc/passwd').read()"})
    with pytest.raises(NameError):
        await node.execute(ExecutionContext())


@pytest.mark.asyncio
async def test_code_node_propagates_snippet_errors():
    node = CodeNode("c", {"code": "output = 1 / 0"})
    with pytest.raises(ZeroDivisionError):
        await node.execute(ExecutionContext())


@pytest.mark.asyncio
async def test_code_node_rejects_other_languages():
    node = CodeNode("c", {"code": "output = 1", "language": "javascript"})
    with pytest.raises(ValueError, match="only supports 'python'"):
        await node.execute(ExecutionContext())


# ── database node ───────────────────────────────────────────


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("CORTEXFLOW_DB_PATH", str(path))
    return path


async def _seed(db_path):
    await DatabaseNode("d", {
        "db_action": "execute",
        "sql": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, score INTEGER)",
    }).execute(ExecutionContext())
    return db_path


@pytest.mark.asyncio
async def test_database_crud_roundtrip(db):
    await _seed(db)

    inserted = await DatabaseNode("d", {
        "db_action": "insert",
        "table": "users",
        "values": {"name": "alice", "score": 10},
    }).execute(ExecutionContext())
    assert inserted["rowcount"] == 1
    assert inserted["lastrowid"] == 1

    rows = await DatabaseNode("d", {
        "db_action": "query",
        "table": "users",
        "where": {"name": "alice"},
    }).execute(ExecutionContext())
    assert rows == [{"id": 1, "name": "alice", "score": 10}]

    updated = await DatabaseNode("d", {
        "db_action": "update",
        "table": "users",
        "values": {"score": 99},
        "where": {"id": 1},
    }).execute(ExecutionContext())
    assert updated["rowcount"] == 1

    rows = await DatabaseNode("d", {
        "db_action": "query",
        "table": "users",
        "limit": 5,
    }).execute(ExecutionContext())
    assert rows[0]["score"] == 99

    deleted = await DatabaseNode("d", {
        "db_action": "delete",
        "table": "users",
        "where": {"id": 1},
    }).execute(ExecutionContext())
    assert deleted["rowcount"] == 1

    assert await DatabaseNode("d", {
        "db_action": "query", "table": "users",
    }).execute(ExecutionContext()) == []


@pytest.mark.asyncio
async def test_database_raw_sql_with_params(db):
    await _seed(db)
    await DatabaseNode("d", {
        "db_action": "insert",
        "table": "users",
        "values": {"name": "${name}", "score": 7},
    }).execute(ExecutionContext(variables={"name": "bob"}))

    rows = await DatabaseNode("d", {
        "db_action": "query",
        "sql": "SELECT name, score FROM users WHERE name = ?",
        "db_params": ["${name}"],
    }).execute(ExecutionContext(variables={"name": "bob"}))
    assert rows == [{"name": "bob", "score": 7}]


@pytest.mark.asyncio
async def test_database_rejects_injected_identifier(db):
    await _seed(db)
    with pytest.raises(ValueError, match="Invalid SQL table"):
        await DatabaseNode("d", {
            "db_action": "query",
            "table": "users; DROP TABLE users",
        }).execute(ExecutionContext())


@pytest.mark.asyncio
async def test_database_requires_where_for_bulk_writes(db):
    await _seed(db)
    with pytest.raises(ValueError, match="affect every row"):
        await DatabaseNode("d", {
            "db_action": "delete",
            "table": "users",
        }).execute(ExecutionContext())


@pytest.mark.asyncio
async def test_database_allow_all_opts_into_bulk_write(db):
    await _seed(db)
    await DatabaseNode("d", {
        "db_action": "insert", "table": "users", "values": {"name": "x"},
    }).execute(ExecutionContext())
    result = await DatabaseNode("d", {
        "db_action": "delete", "table": "users", "allow_all": True,
    }).execute(ExecutionContext())
    assert result["rowcount"] == 1


@pytest.mark.asyncio
async def test_database_unknown_action_raises(db):
    with pytest.raises(ValueError, match="unknown db_action"):
        await DatabaseNode("d", {"db_action": "truncate"}).execute(ExecutionContext())


# ── text node ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_text_simple_ops():
    async def run(action, text, **args):
        return await TextNode("t", {
            "text_action": action, "input": "${text}", "text_args": args,
        }).execute(ExecutionContext(variables={"text": text}))

    assert await run("trim", "  hi  ") == "hi"
    assert await run("upper", "hi") == "HI"
    assert await run("length", "hello") == 5
    assert await run("replace", "a-b-a", old="a", new="x") == "x-b-x"
    assert await run("substring", "abcdef", start=1, end=4) == "bcd"
    assert await run("contains", "hello", value="ell") is True
    assert await run("concat", None, items=["a", "b"], separator="-") == "a-b"


@pytest.mark.asyncio
async def test_text_split_and_join():
    split = await TextNode("t", {
        "text_action": "split", "input": "${csv}", "text_args": {"separator": ","},
    }).execute(ExecutionContext(variables={"csv": "a,b,c"}))
    assert split == ["a", "b", "c"]

    joined = await TextNode("t", {
        "text_action": "join", "input": "${items}", "text_args": {"separator": "|"},
    }).execute(ExecutionContext(variables={"items": ["a", "b"]}))
    assert joined == "a|b"


@pytest.mark.asyncio
async def test_text_regex_extract_and_replace():
    node = TextNode("t", {
        "text_action": "regex_extract",
        "input": "${text}",
        "text_args": {"pattern": r"\d+", "all": True},
    })
    assert await node.execute(ExecutionContext(variables={"text": "a1 b22"})) == ["1", "22"]

    replace = TextNode("t", {
        "text_action": "regex_replace",
        "input": "${text}",
        "text_args": {"pattern": r"\s+", "replacement": " "},
    })
    assert await replace.execute(ExecutionContext(variables={"text": "a   b"})) == "a b"


@pytest.mark.asyncio
async def test_text_template_uses_input_and_context():
    node = TextNode("t", {
        "text_action": "template",
        "input": "${user}",
        "text_args": {"template": "{{name}} from {{city}}"},
    })
    ctx = ExecutionContext(variables={"user": {"name": "alice"}, "city": "SZ"})
    assert await node.execute(ctx) == "alice from SZ"


@pytest.mark.asyncio
async def test_text_json_helpers():
    parsed = await TextNode("t", {
        "text_action": "json_parse", "input": "${raw}",
    }).execute(ExecutionContext(variables={"raw": '{"a": 1}'}))
    assert parsed == {"a": 1}

    dumped = await TextNode("t", {
        "text_action": "to_json", "input": "${data}", "text_args": {"indent": None},
    }).execute(ExecutionContext(variables={"data": {"a": 1}}))
    assert dumped == '{"a": 1}'


@pytest.mark.asyncio
async def test_text_rejects_unknown_or_missing_action():
    with pytest.raises(ValueError, match="requires 'text_action'"):
        await TextNode("t", {"input": "x"}).execute(ExecutionContext())
    with pytest.raises(ValueError, match="unknown text_action"):
        await TextNode("t", {"text_action": "shout", "input": "x"}).execute(
            ExecutionContext()
        )


# ── validation ──────────────────────────────────────────────


def _workflow(nodes_yaml: str) -> str:
    return f"""
id: t
name: t
entry: n
nodes:
{nodes_yaml}
"""


def test_validator_requires_code_and_text_action():
    engine = Engine()
    with pytest.raises(ValidationError, match="missing 'code'"):
        engine.compile(engine.load_from_string(_workflow("  n:\n    type: code\n")))
    with pytest.raises(ValidationError, match="missing 'text_action'"):
        engine.compile(engine.load_from_string(_workflow("  n:\n    type: text\n")))


def test_validator_checks_database_fields():
    engine = Engine()
    with pytest.raises(ValidationError, match="needs 'sql' or 'table'"):
        engine.compile(
            engine.load_from_string(_workflow("  n:\n    type: database\n"))
        )
    with pytest.raises(ValidationError, match="needs 'where'"):
        engine.compile(engine.load_from_string(_workflow(
            "  n:\n    type: database\n    db_action: delete\n    table: users\n"
        )))
    with pytest.raises(ValidationError, match="needs 'values'"):
        engine.compile(engine.load_from_string(_workflow(
            "  n:\n    type: database\n    db_action: insert\n    table: users\n"
        )))


# ── end to end ──────────────────────────────────────────────


async def test_code_and_text_nodes_in_a_workflow():
    flow = """
id: code_text
name: code + text
entry: calc
nodes:
  calc:
    type: code
    inputs:
      numbers: ${numbers}
    code: |
      total = sum(numbers)
      output = {"total": total, "label": "sum"}
    output: stats
    on_success: fmt
  fmt:
    type: text
    text_action: template
    input: ${stats}
    text_args:
      template: "{{label}}: {{total}}"
    output: message
    on_success: done
  done:
    type: end
    end_mode: variable
    return_value: ${message}
"""
    result = await Engine().run_string(flow, {"numbers": [1, 2, 3]})
    assert result == "sum: 6"
