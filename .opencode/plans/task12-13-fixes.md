# Task 12 & 13 Fix Implementation Plan

## Fix 1: Team selection pipeline (frontend → backend)

**File: `frontend/src/routes/_dashboard.chat.tsx`**
- In `handleSendQuery`, after line 188, add: `if (activeTeamId) queryParams.append('team_id', activeTeamId);`

**File: `backend/api/routes/query.py`**
- Line 21: Add `team_id: str | None = Query(None)` parameter after `parent_msg_id`
- Line 63: Replace `"active_team_id": "default-team"` with `"active_team_id": team_id or "default-team"`

## Fix 2+9: Redis singleton + connection timeout

**File: `backend/agents/memory.py`**

Replace entire file with:
```python
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
    SESSION_TTL = 7 * 24 * 3600
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
```

## Fix 3: Remove debug print / fix log level

**File: `backend/api/routes/query.py`**
- Delete line 25 (`print("DEBUG: ...")`)
- Line 26: Change `logger.info(` to `logger.debug(`

## Fix 4+5+6: Session isolation + indexes + optimization

**File: `backend/models.py`**
- Add `user_id` column to `Message`:
  ```python
  user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
  ```
- Add `index=True` to `created_at`:
  ```python
  created_at = Column(DateTime, server_default=func.now(), index=True)
  ```
- Update `__table_args__`:
  ```python
  __table_args__ = (
      Index('ix_messages_session_parent', 'session_id', 'parent_message_id'),
      Index('ix_messages_user_session', 'user_id', 'session_id'),
  )
  ```

**Commands:**
```bash
cd backend && uv run alembic revision --autogenerate -m "add user_id, index created_at, composite index"
cd backend && uv run alembic upgrade head
```

**File: `backend/api/routes/query.py`**
- In `run_query` (lines 85-101): Store `user_id=user_id` when creating Message objects
- In `get_chat_messages` (line 134): Add `.filter(Message.user_id == current_user["sub"])`
- In `get_chat_sessions` (line 158): Add `.filter(Message.user_id == current_user["sub"])`

## Fix 7: history consumed by synthesize_node

**File: `backend/agents/graph_orchestrator.py`**

Replace `synthesize_node` with:
```python
def synthesize_node(state: AgentState) -> Dict[str, Any]:
    history_context = ""
    if state.get("history"):
        history_context = "\n".join(
            f"{m['role']}: {m['content']}" for m in state["history"]
        )
    return {
        "raw_response": f"Mock response for query: {state['query']}\n\n{history_context}",
        "citations": [{"source": "mock_source"}]
    }
```

## Fix 8: rewritten queries used for routing

**File: `backend/agents/graph_orchestrator.py`**

Replace `route_node` with:
```python
def route_node(state: AgentState) -> Dict[str, Any]:
    from backend.agents.router import route_query
    query_to_route = state["query"]
    if state.get("rewritten_queries") and len(state["rewritten_queries"]) > 0:
        query_to_route = state["rewritten_queries"][0]
    decision = route_query(query_to_route)
    return {"route": decision.route}
```
