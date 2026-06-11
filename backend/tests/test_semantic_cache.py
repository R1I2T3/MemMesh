import pytest
import json
from unittest.mock import patch, MagicMock
from backend.cache.semantic_cache import SemanticCache


@pytest.fixture
def mock_redis():
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_embeddings():
    mock = MagicMock()
    mock.embed_query.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
    return mock


@pytest.fixture
def cache(mock_redis, mock_embeddings):
    with patch("backend.cache.semantic_cache.get_redis_client", return_value=mock_redis):
        with patch("backend.cache.semantic_cache.GoogleGenerativeAIEmbeddings", return_value=mock_embeddings):
            c = SemanticCache()
            c.threshold = 0.9
            return c


def test_cosine_similarity_identical(cache):
    vec = [1.0, 2.0, 3.0]
    sim = cache._cosine_similarity(vec, vec)
    assert abs(sim - 1.0) < 1e-6


def test_cosine_similarity_orthogonal(cache):
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    sim = cache._cosine_similarity(a, b)
    assert abs(sim - 0.0) < 1e-6


def test_cosine_similarity_zero_vectors(cache):
    sim = cache._cosine_similarity([0.0, 0.0], [1.0, 1.0])
    assert sim == 0.0


def test_hash_key_consistency(cache):
    emb = [0.1, 0.2, 0.3, 0.4]
    h1 = cache._hash_key(emb)
    h2 = cache._hash_key(emb)
    assert h1 == h2


def test_hash_key_shorter_embedding(cache):
    emb = [0.1, 0.2]
    h = cache._hash_key(emb)
    assert isinstance(h, str)
    assert len(h) == 32


def test_cache_miss(cache, mock_redis):
    mock_redis.get.return_value = None
    result = cache.get("some query")
    assert result is None
    mock_redis.get.assert_called_once()


def test_cache_hit(cache, mock_redis):
    query_emb = [0.1, 0.2, 0.3, 0.4, 0.5]
    stored_entry = json.dumps({
        "embedding": [0.099, 0.199, 0.301, 0.401, 0.502],
        "result": {"response": "cached answer", "citations": []}
    })
    cache._embed = MagicMock(return_value=query_emb)
    mock_redis.get.return_value = stored_entry
    result = cache.get("similar query")
    assert result == {"response": "cached answer", "citations": []}


def test_cache_below_threshold(cache, mock_redis):
    query_emb = [1.0, 0.0, 0.0, 0.0, 0.0]
    stored_entry = json.dumps({
        "embedding": [0.0, 1.0, 0.0, 0.0, 0.0],
        "result": {"response": "should not return"}
    })
    cache._embed = MagicMock(return_value=query_emb)
    mock_redis.get.return_value = stored_entry
    result = cache.get("very different query")
    assert result is None


def test_set_cache(cache, mock_redis):
    query_emb = [0.1, 0.2, 0.3, 0.4, 0.5]
    cache._embed = MagicMock(return_value=query_emb)
    cache.set("test query", {"response": "test", "citations": []})
    mock_redis.set.assert_called_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0].startswith("semantic_cache:")
    assert kwargs.get("ex") == cache.ttl
    stored = json.loads(args[1])
    assert stored["result"] == {"response": "test", "citations": []}
    assert stored["embedding"] == query_emb


def test_flush_cache(cache, mock_redis):
    mock_redis.keys.return_value = ["semantic_cache:abc", "semantic_cache:def"]
    cache.flush()
    mock_redis.delete.assert_called_once_with("semantic_cache:abc", "semantic_cache:def")


def test_flush_cache_empty(cache, mock_redis):
    mock_redis.keys.return_value = []
    cache.flush()
    mock_redis.delete.assert_not_called()
