"""Low-level fallback and single-collection contracts for embedded memory."""

from unittest.mock import Mock

import pytest

from praval.memory.embedded_store import EmbeddedVectorStore
from praval.memory.memory_types import MemoryQuery, MemoryType


def _bare_store(*, separated: bool = True) -> EmbeddedVectorStore:
    store = object.__new__(EmbeddedVectorStore)
    store.enable_collection_separation = separated
    store.embedding_size = 4
    store.embedding_model = None
    store.embedding_runtime = None
    store.knowledge_collection = Mock(name="knowledge")
    store.memory_collection = Mock(name="memory")
    store.collection = Mock(name="collection")
    return store


def test_embedded_store_migration_skips_legacy_and_moves_missing_embeddings():
    store = _bare_store()
    store.legacy_collection_name = None
    store._migrate_legacy_collection_if_needed()

    legacy = Mock()
    legacy.get.return_value = {
        "ids": ["semantic-1", "memory-1"],
        "metadatas": [
            {"memory_type": "semantic"},
            {"memory_type": "episodic"},
        ],
        "documents": ["knowledge", "memory"],
        "embeddings": None,
    }
    store.legacy_collection_name = "legacy"
    store.client = Mock()
    store.client.get_collection.return_value = legacy
    store._migrate_legacy_collection_if_needed()

    store.knowledge_collection.upsert.assert_called_once_with(
        ids=["semantic-1"],
        metadatas=[{"memory_type": "semantic"}],
        documents=["knowledge"],
    )
    store.memory_collection.upsert.assert_called_once_with(
        ids=["memory-1"],
        metadatas=[{"memory_type": "episodic"}],
        documents=["memory"],
    )
    store.client.delete_collection.assert_called_once_with(name="legacy")


def test_embedded_store_single_collection_retrieve_and_health_paths():
    store = _bare_store(separated=False)
    store._result_to_memory_entry = Mock(return_value="entry")
    store.collection.get.return_value = {"ids": ["memory-1"]}
    assert store.retrieve("memory-1") == "entry"

    store.collection.get.return_value = {"ids": []}
    assert store.retrieve("missing") is None
    store.collection.get.side_effect = RuntimeError("read failed")
    assert store.retrieve("failure") is None

    store.collection.count.return_value = 1
    assert store.health_check() is True
    store.collection.count.side_effect = RuntimeError("count failed")
    assert store.health_check() is False


def test_embedded_store_collection_selection_for_single_and_mixed_queries():
    single = _bare_store(separated=False)
    query = MemoryQuery(query_text="query", memory_types=[])
    assert single._get_collections_for_search(query) == [single.collection]

    separated = _bare_store()
    assert separated._get_collections_for_search(query) == [
        separated.knowledge_collection,
        separated.memory_collection,
    ]
    mixed = MemoryQuery(
        query_text="query",
        memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC],
    )
    assert separated._get_collections_for_search(mixed) == [
        separated.knowledge_collection,
        separated.memory_collection,
    ]


def test_embedded_store_delete_and_clear_single_collection_paths():
    single = _bare_store(separated=False)
    assert single.delete("memory-1") is True
    single.collection.delete.assert_called_once_with(ids=["memory-1"])
    single.collection.delete.side_effect = RuntimeError("delete failed")
    assert single.delete("memory-2") is False

    single.collection.delete.reset_mock(side_effect=True)
    single.clear_agent_memories("agent-a")
    single.collection.delete.assert_called_once_with(where={"agent_id": "agent-a"})

    separated = _bare_store()
    separated.memory_collection.get.return_value = {"ids": []}
    separated.knowledge_collection.get.return_value = {"ids": []}
    assert separated.delete("missing") is False
    separated.memory_collection.get.side_effect = RuntimeError("lookup failed")
    assert separated.delete("failure") is False


def test_embedded_store_embedding_and_similarity_fallback_edges():
    store = _bare_store()
    store.embedding_runtime = Mock()
    store.embedding_runtime.embed_text.return_value = [1.0, 2.0]
    assert store._generate_embedding("hello") == [1.0, 2.0]

    store.embedding_runtime.embed_text.side_effect = RuntimeError("embed failed")
    fallback = store._generate_embedding("hello world")
    assert len(fallback) == 4
    assert sum(value * value for value in fallback) == pytest.approx(1.0)
    assert store._fallback_embedding("!!!") == [0.0] * 4
    assert store._fallback_similarity("", "content") == 0.0
    assert store._fallback_similarity("query", "") == 0.0


def test_embedded_store_result_conversion_failure_is_nonfatal():
    store = _bare_store()
    assert store._result_to_memory_entry({"ids": []}, 0) is None


def test_embedded_store_get_target_collection_in_legacy_mode():
    store = _bare_store(separated=False)
    assert store._get_target_collection(MemoryType.SEMANTIC) is store.collection
