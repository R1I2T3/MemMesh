from unittest.mock import patch
from workers.tasks import (
    trigger_memory_decay,
    trigger_graph_deduplication,
    consolidate_session_task,
)


@patch("workers.tasks.memory_manager")
def test_trigger_memory_decay_task(mock_memory_manager):
    trigger_memory_decay()
    mock_memory_manager.apply_memory_decay.assert_called_once_with(decay_days=30)


@patch("workers.tasks.memory_manager")
def test_trigger_graph_deduplication_task(mock_memory_manager):
    trigger_graph_deduplication()
    mock_memory_manager.merge_duplicate_entities.assert_called_once_with(
        similarity_threshold=0.85
    )


@patch("workers.tasks.memory_manager")
def test_consolidate_session_task(mock_memory_manager):
    test_session = "session_123"
    consolidate_session_task(test_session)
    mock_memory_manager.consolidate_session_memories.assert_called_once_with(
        test_session
    )
