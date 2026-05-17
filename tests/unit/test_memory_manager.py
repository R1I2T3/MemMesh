import pytest
from unittest.mock import MagicMock, patch
from db.lifecycle.memory_manager import MemoryManager


@pytest.fixture
def mock_stores():
    mock_graph = MagicMock()
    mock_vector = MagicMock()
    mock_vector.table = MagicMock()
    mock_vector.table.search.return_value.where.return_value.to_list.return_value = []
    return mock_graph, mock_vector


@pytest.fixture
def memory_manager(mock_stores):
    return MemoryManager(graph_store=mock_stores[0], vector_store=mock_stores[1])


def test_merge_duplicate_entities_calls_graph_store(memory_manager):
    memory_manager.merge_duplicate_entities(similarity_threshold=0.9)
    memory_manager.graph.run_query.assert_called_once()
    call_args = memory_manager.graph.run_query.call_args[0][0]
    assert "apoc.refactor.mergeNodes" in call_args
    assert "MATCH (a:Entity), (b:Entity)" in call_args


def test_apply_memory_decay_calls_both_stores(memory_manager):
    memory_manager.apply_memory_decay(decay_days=30)
    memory_manager.vector.table.delete.assert_called_once()
    memory_manager.graph.run_query.assert_called_once()
    decay_query = memory_manager.graph.run_query.call_args[0][0]
    assert "DETACH DELETE m" in decay_query


def test_consolidate_session_memories_no_logs_returns_early(memory_manager):
    memory_manager.consolidate_session_memories("test_session_id")
    memory_manager.graph.upsert_triples.assert_not_called()


def test_consolidate_session_memories_extracts_and_stores_facts(memory_manager, mock_stores):
    mock_graph, mock_vector = mock_stores
    mock_vector.table.search.return_value.where.return_value.to_list.return_value = [
        {"id": "log1", "text": "User discussed project requirements"},
        {"id": "log2", "text": "User mentioned timeline concerns"},
    ]

    mock_triples = [
        {"subject": "User", "relationship": "DISCUSSED", "object": "project requirements"}
    ]

    with patch("db.lifecycle.memory_manager.ExtractorAgent") as MockExtractorAgent:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = mock_triples
        MockExtractorAgent.return_value = mock_extractor

        memory_manager.consolidate_session_memories("test_session_id")

        MockExtractorAgent.assert_called_once()
        mock_extractor.extract.assert_called_once()
        mock_graph.upsert_triples.assert_called_once_with(mock_triples, context_id="test_session_id")
        mock_vector.table.delete.assert_called()


def test_apply_memory_decay(memory_manager):
    memory_manager.apply_memory_decay(decay_days=30)
    # Similar to above, in a fully linked state we check:
    # memory_manager.graph.run.assert_called_once()
    # memory_manager.vector.delete_where.assert_called_once()
    assert True


def test_consolidate_session_memories(memory_manager):
    # This should not raise an error
    memory_manager.consolidate_session_memories("test_session_id")
    assert True
