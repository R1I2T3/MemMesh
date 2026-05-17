from unittest.mock import patch, MagicMock
import pytest
import sys


def _make_task_decorator():
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
    mock_celery = MagicMock()
    mock_celery.Celery.return_value.task = _make_task_decorator()
    with patch.dict(sys.modules, {"celery": mock_celery}):
        yield mock_celery


@pytest.fixture
def ingestion_task(mock_celery):
    with patch.object(db.graph_store, "GraphStore") as MockGraphStore:
        with patch.object(db.vector_store, "VectorStore") as MockVectorStore:
            MockGraphStore.return_value = MagicMock()
            MockVectorStore.return_value = MagicMock()
            with patch.object(db.lifecycle.memory_manager, "ExtractorAgent"):
                # Clear workers modules to force fresh import with patches active
                for mod_name in list(sys.modules.keys()):
                    if mod_name.startswith("workers"):
                        del sys.modules[mod_name]

                from workers import tasks
                yield tasks


@pytest.mark.unit
def test_process_document_ingestion_chunks_and_embeds(ingestion_task):
    from workers.tasks import process_document_ingestion

    mock_chunks = [
        {"chunk_index": 0, "text": "chunk one", "source": "test.pdf"},
        {"chunk_index": 1, "text": "chunk two", "source": "test.pdf"},
    ]
    mock_chunks_with_embeddings = [
        {"chunk_index": 0, "text": "chunk one", "source": "test.pdf", "embedding": [0.1] * 768},
        {"chunk_index": 1, "text": "chunk two", "source": "test.pdf", "embedding": [0.2] * 768},
    ]
    mock_triples = [
        {"subject": "Alice", "relationship": "WORKS_AT", "object": "Acme"}
    ]

    with patch("workers.tasks.extract_text_from_file", return_value="chunk one\nchunk two"):
        with patch("workers.tasks.chunk_text", return_value=mock_chunks):
            with patch("workers.tasks.embed_chunks", return_value=mock_chunks_with_embeddings):
                with patch("workers.tasks.ExtractorAgent") as MockExtractor:
                    MockExtractor.return_value.extract.return_value = mock_triples
                    with patch("workers.tasks.os.remove") as mock_remove:
                        result = process_document_ingestion(None, "/tmp/test.pdf", multimodal=False)

    assert result["chunks_count"] == 2
    assert result["triples_count"] == 1
    assert result["source"] == "test.pdf"
    mock_remove.assert_called_once_with("/tmp/test.pdf")


@pytest.mark.unit
def test_process_document_ingestion_empty_text_returns_zero_chunks(ingestion_task):
    from workers.tasks import process_document_ingestion

    with patch("workers.tasks.extract_text_from_file", return_value=""):
        with patch("workers.tasks.chunk_text", return_value=[]):
            with patch("workers.tasks.os.remove") as mock_remove:
                result = process_document_ingestion(None, "/tmp/empty.pdf", multimodal=False)

    assert result["chunks_count"] == 0
    assert result["triples_count"] == 0
    mock_remove.assert_called_once_with("/tmp/empty.pdf")


@pytest.mark.unit
def test_process_document_ingestion_unsupported_file_raises(ingestion_task):
    from workers.tasks import process_document_ingestion

    def raise_exc(exc, **kw):
        raise exc

    mock_self = MagicMock()
    mock_self.retry.side_effect = raise_exc

    with patch("workers.tasks.extract_text_from_file", side_effect=ValueError("Unsupported")):
        with pytest.raises(ValueError, match="Unsupported"):
            process_document_ingestion(mock_self, "/tmp/file.xyz", multimodal=False)
