"""Every shipped example workflow must parse and compile."""

from pathlib import Path

import pytest

from cortexflow.engine import Engine

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.rglob("*.yaml"))


def test_examples_directory_is_not_empty():
    assert EXAMPLES, "expected example workflows in examples/"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.relative_to(EXAMPLES_DIR).as_posix())
def test_example_compiles(path: Path):
    engine = Engine()
    workflow = engine.load(path)
    ir = engine.compile(workflow)
    assert ir.entry in ir.nodes
