from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def mock_stores():
    """Patch store initialization so tests don't require live Neo4j/LanceDB."""
    with patch("tools.graph_tool.init_graph_store", return_value=MagicMock()) as mock_gs:
        with patch("tools.vector_tool.init_vector_store", return_value=MagicMock()) as mock_vs:
            yield mock_gs, mock_vs


@pytest.fixture
def tasks_module(mock_stores):
    """Import workers.tasks after stores are patched."""
    with patch("workers.tasks.memory_manager") as mock_mm:
        from workers import tasks
        tasks.memory_manager = mock_mm
        yield tasks


@pytest.mark.unit
def test_trigger_memory_decay_task(tasks_module):
    from workers.tasks import trigger_memory_decay
    trigger_memory_decay()
    tasks_module.memory_manager.apply_memory_decay.assert_called_once_with(decay_days=30)


@pytest.mark.unit
def test_trigger_graph_deduplication_task(tasks_module):
    from workers.tasks import trigger_graph_deduplication
    trigger_graph_deduplication()
    tasks_module.memory_manager.merge_duplicate_entities.assert_called_once_with(
        similarity_threshold=0.85
    )


@pytest.mark.unit
def test_consolidate_session_task(tasks_module):
    from workers.tasks import consolidate_session_task
    test_session = "session_123"
    consolidate_session_task(test_session)
    tasks_module.memory_manager.consolidate_session_memories.assert_called_once_with(
        test_session
    )
