import json
import redis
from backend.config import settings

_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=5,
            health_check_interval=30,
        )
    return _redis_client

class RedisMemory:
    SESSION_TTL = 7 * 24 * 3600  # 7 days
    MAX_LENGTH = 20

    def __init__(self):
        self.client = get_redis_client()

    def get_history(self, session_id: str, limit: int = 10) -> list[dict]:
        key = f"chat_history:{session_id}"
        messages = self.client.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]

    def save_message(self, session_id: str, role: str, content: str):
        key = f"chat_history:{session_id}"
        pipe = self.client.pipeline()
        pipe.rpush(key, json.dumps({"role": role, "content": content}))
        pipe.ltrim(key, -self.MAX_LENGTH, -1)
        pipe.expire(key, self.SESSION_TTL)
        pipe.execute()
