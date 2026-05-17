from unittest.mock import patch, MagicMock
import pytest
import sys


def _make_task_decorator():
    """Create a mock Celery task decorator that returns the function unchanged."""
    def task_decorator(*args, **kwargs):
        def wrapper(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return wrapper
    return task_decorator


# Import db modules once at module load time (C-extension deps can't be reloaded)
import db.graph_store
import db.vector_store
import db.lifecycle.memory_manager


@pytest.fixture
def mock_celery():
    """Mock celery module to avoid import errors."""
    mock_celery = MagicMock()
    mock_celery.Celery.return_value.task = _make_task_decorator()
    with patch.dict(sys.modules, {"celery": mock_celery}):
        yield mock_celery


@pytest.fixture
def tasks_module(mock_celery):
    """Import workers.tasks after celery is patched, then replace memory_manager."""
    with patch.object(db.graph_store, "GraphStore", return_value=MagicMock()):
        with patch.object(db.vector_store, "VectorStore", return_value=MagicMock()):
            with patch.object(db.lifecycle.memory_manager, "ExtractorAgent"):
                from workers import tasks
                tasks.memory_manager = MagicMock()
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
