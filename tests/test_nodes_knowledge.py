"""Tests for the knowledge node (write side of retrieval)."""

import pytest

from cortexflow.adapters.memory import VectorMemoryAdapter
from cortexflow.dsl.validator import ValidationError
from cortexflow.engine import Engine
from cortexflow.nodes.knowledge import KnowledgeNode
from cortexflow.nodes.retrieval import RetrievalNode
from cortexflow.runtime.context import ExecutionContext


def _ctx() -> ExecutionContext:
    return ExecutionContext(adapters={"memory": VectorMemoryAdapter()})


@pytest.mark.asyncio
async def test_ingest_text_chunks_and_stores():
    ctx = _ctx()
    node = KnowledgeNode("k", {
        "knowledge_action": "ingest_text",
        "knowledge_source": "Refund policy: refunds take 3 days.",
        "knowledge_namespace": "kb",
        "knowledge_chunk_size": 20,
    })
    result = await node.execute(ctx)
    assert result["action"] == "ingest_text"
    assert result["namespace"] == "kb"
    assert result["documents"] == 1
    assert result["chunks"] > 1

    entries = await ctx.get_adapter("memory").list_all(namespace="kb")
    assert len(entries) == result["chunks"]
    assert entries[0]["metadata"]["chunk_index"] == 0
    assert entries[0]["metadata"]["total_chunks"] == result["chunks"]


@pytest.mark.asyncio
async def test_ingested_text_is_retrievable():
    ctx = _ctx()
    await KnowledgeNode("k", {
        "knowledge_action": "ingest_text",
        "knowledge_source": "refund policy refunds take three days",
        "knowledge_namespace": "kb",
        "knowledge_chunk_size": 500,
    }).execute(ctx)

    result = await RetrievalNode("r", {
        "retrieval_query": "refund",
        "retrieval_collection": "kb",
        "retrieval_top_k": 3,
    }).execute(ctx)

    assert result["count"] == 1
    assert "refund" in result["documents"][0]


@pytest.mark.asyncio
async def test_ingest_file_and_directory(tmp_path):
    (tmp_path / "a.md").write_text("alpha document about cats", encoding="utf-8")
    (tmp_path / "b.md").write_text("beta document about dogs", encoding="utf-8")

    ctx = _ctx()
    file_result = await KnowledgeNode("k", {
        "knowledge_action": "ingest_file",
        "knowledge_source": str(tmp_path / "a.md"),
        "knowledge_namespace": "docs",
    }).execute(ctx)
    assert file_result["documents"] == 1
    assert file_result["sources"] == [str(tmp_path / "a.md")]

    dir_result = await KnowledgeNode("k", {
        "knowledge_action": "ingest_directory",
        "knowledge_source": str(tmp_path),
        "knowledge_namespace": "docs",
    }).execute(ctx)
    assert dir_result["documents"] == 2
    assert sorted(dir_result["sources"]) == [str(tmp_path / "a.md"), str(tmp_path / "b.md")]


@pytest.mark.asyncio
async def test_ingest_merges_custom_metadata():
    ctx = _ctx()
    await KnowledgeNode("k", {
        "knowledge_action": "ingest_text",
        "knowledge_source": "hello",
        "knowledge_namespace": "kb",
        "knowledge_metadata": {"lang": "en", "owner": "${owner}"},
    }).execute(ExecutionContext(
        adapters=ctx.adapters,
        variables={"owner": "alice"},
    ))

    entries = await ctx.get_adapter("memory").list_all(namespace="kb")
    assert entries[0]["metadata"]["lang"] == "en"
    assert entries[0]["metadata"]["owner"] == "alice"


@pytest.mark.asyncio
async def test_list_delete_and_clear():
    ctx = _ctx()
    await KnowledgeNode("k", {
        "knowledge_action": "ingest_text",
        "knowledge_source": "one two three",
        "knowledge_namespace": "kb",
    }).execute(ctx)

    listed = await KnowledgeNode("k", {
        "knowledge_action": "list",
        "knowledge_namespace": "kb",
    }).execute(ctx)
    assert listed["count"] == 1

    deleted = await KnowledgeNode("k", {
        "knowledge_action": "delete",
        "knowledge_namespace": "kb",
        "knowledge_entry_id": listed["entries"][0]["id"],
    }).execute(ctx)
    assert deleted["deleted"] is True

    cleared = await KnowledgeNode("k", {
        "knowledge_action": "clear",
        "knowledge_namespace": "kb",
    }).execute(ctx)
    assert cleared["action"] == "clear"
    assert await ctx.get_adapter("memory").count(namespace="kb") == 0


@pytest.mark.asyncio
async def test_missing_memory_adapter_raises():
    node = KnowledgeNode("k", {"knowledge_action": "list"})
    with pytest.raises(RuntimeError, match="Memory adapter"):
        await node.execute(ExecutionContext())


@pytest.mark.asyncio
async def test_unknown_action_raises():
    node = KnowledgeNode("k", {"knowledge_action": "explode"})
    with pytest.raises(ValueError, match="unknown action"):
        await node.execute(_ctx())


# ── validation ──────────────────────────────────────────────


def _compile(node_body: str):
    flow = f"""
id: k
name: k
entry: k
nodes:
  k:
{node_body}
"""
    engine = Engine()
    return engine.compile(engine.load_from_string(flow))


def test_validator_rejects_unknown_action():
    with pytest.raises(ValidationError, match="unknown knowledge_action"):
        _compile("    type: knowledge\n    knowledge_action: explode")


def test_validator_requires_source_for_ingest():
    with pytest.raises(ValidationError, match="needs 'knowledge_source'"):
        _compile("    type: knowledge\n    knowledge_action: ingest_file")


def test_validator_requires_entry_id_for_delete():
    with pytest.raises(ValidationError, match="needs 'knowledge_entry_id'"):
        _compile("    type: knowledge\n    knowledge_action: delete")


def test_validator_rejects_overlap_not_smaller_than_chunk_size():
    with pytest.raises(ValidationError, match="knowledge_overlap"):
        _compile(
            "    type: knowledge\n"
            "    knowledge_action: ingest_text\n"
            "    knowledge_source: hi\n"
            "    knowledge_chunk_size: 100\n"
            "    knowledge_overlap: 100"
        )
