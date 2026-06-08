import json
import pytest
from unittest.mock import patch, MagicMock
from backend.agents.memory import RedisMemory
import backend.agents.memory

@pytest.fixture(autouse=True)
def reset_redis_client():
    backend.agents.memory._redis_client = None
    yield
    backend.agents.memory._redis_client = None

def test_chat_history_ordering():
    """Verify messages are returned in chronological order (oldest first)."""
    with patch("backend.agents.memory.redis.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        
        # Simulate oldest-first order (e.g. from RPUSH + LRANGE -N -1)
        mock_client.lrange.return_value = [
            json.dumps({"role": "user", "content": "first"}),
            json.dumps({"role": "assistant", "content": "second"}),
            json.dumps({"role": "user", "content": "third"}),
        ]
        
        mem = RedisMemory()
        history = mem.get_history("session-123", limit=3)
        
        assert len(history) == 3
        assert history[0]["content"] == "first"
        assert history[1]["content"] == "second"
        assert history[2]["content"] == "third"
        mock_client.lrange.assert_called_with("chat_history:session-123", -3, -1)

def test_save_message_uses_rpush():
    """Verify RPUSH is used (not LPUSH) to maintain chronological order."""
    with patch("backend.agents.memory.redis.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        
        mem = RedisMemory()
        mem.save_message("session-123", "user", "hello")
        
        mock_pipe.rpush.assert_called_once_with(
            "chat_history:session-123",
            json.dumps({"role": "user", "content": "hello"})
        )
        mock_pipe.lpush.assert_not_called()

def test_ttl_is_set_on_save():
    """Verify session keys get a TTL to prevent unbounded Redis memory."""
    with patch("backend.agents.memory.redis.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        
        mem = RedisMemory()
        mem.save_message("session-123", "user", "hello")
        
        mock_pipe.expire.assert_called_once_with(
            "chat_history:session-123",
            RedisMemory.SESSION_TTL
        )
        mock_pipe.ltrim.assert_called_once_with(
            "chat_history:session-123",
            -RedisMemory.MAX_LENGTH,
            -1
        )
        mock_pipe.execute.assert_called_once()

