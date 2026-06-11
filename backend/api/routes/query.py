import uuid
import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, Header, Request
from backend.config import settings
from backend.rate_limiter import limiter
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from backend.db.mysql import get_db
from backend.models import Message
from backend.auth.middleware import get_current_user
from backend.agents.memory import RedisMemory
from backend.agents.graph_orchestrator import get_graph, ainvoke_with_events

logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    session_id: str = "default-session"
    parent_msg_id: str | None = None

router = APIRouter(prefix="/api", tags=["query"])

@router.post("/query", status_code=200)
@limiter.limit(settings.RATE_LIMIT_QUERY)
def run_query(
    request: Request,
    payload: QueryRequest,
    x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

    # 1. Safety validation
    from backend.agents.safety import validate_query, validate_output, SafetyValidationError
    try:
        validated_q = validate_query(payload.query)
    except SafetyValidationError as se:
        raise HTTPException(status_code=400, detail=str(se))

    # 2. Context history reconstruction
    history = _load_history(db, payload.session_id, payload.parent_msg_id, user_id)

    # 2b. Semantic cache check (skip graph invoke, output validation, DB persist, Redis save on hit)
    from backend.cache.semantic_cache import get_cache
    cache = get_cache()
    cached_result = cache.get(validated_q)
    if cached_result:
        logger.info(f"Cache HIT for query: {validated_q[:50]}...")
        # Generate fresh message IDs for the current session
        hit_user_msg_id = str(uuid.uuid4())
        hit_assistant_msg_id = str(uuid.uuid4())
        return {
            "response": cached_result["response"],
            "message_id": hit_assistant_msg_id,
            "user_message_id": hit_user_msg_id,
            "session_id": payload.session_id,
            "parent_message_id": hit_user_msg_id,
            "citations": cached_result.get("citations", [])
        }

    # 3. Invoke LangGraph orchestrator
    graph = get_graph()
    try:
        result = graph.invoke({
            "query": validated_q,
            "history": history,
            "session_id": payload.session_id,
            "active_team_id": x_active_team_id or "default-team",
            "user_id": user_id,
            "rewritten_queries": [],
            "route": "",
            "retrieved_chunks": [],
            "retrieved_triples": [],
            "web_search_results": [],
            "final_context": [],
            "raw_response": "",
            "citations": [],
            "relevance_pass": True
        })
    except Exception as e:
        logger.error(f"LangGraph execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

    raw_response = result.get("raw_response", "")

    # Output safety validation
    try:
        validated_response = validate_output(raw_response)
    except SafetyValidationError as se:
        raise HTTPException(status_code=400, detail=str(se))

    # 4. Save to database
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

    user_msg = Message(
        message_id=user_msg_id,
        session_id=payload.session_id,
        parent_message_id=payload.parent_msg_id,
        user_id=user_id,
        role="user",
        content=validated_q
    )
    db.add(user_msg)

    assistant_msg = Message(
        message_id=assistant_msg_id,
        session_id=payload.session_id,
        parent_message_id=user_msg_id,
        user_id=user_id,
        role="assistant",
        content=validated_response,
        citations=result.get("citations", [])
    )
    db.add(assistant_msg)
    
    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.error(f"Database save message failed: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to persist conversation history")

    # 5. Update Redis memory if not branched (parent_msg_id is None)
    if not payload.parent_msg_id:
        try:
            memory = RedisMemory()
            memory.save_message(payload.session_id, "user", validated_q)
            memory.save_message(payload.session_id, "assistant", validated_response)
        except Exception as redis_err:
            logger.warning(f"Failed to save messages to Redis memory: {redis_err}")

    # Cache the result for future semantic matches (non-blocking — fire and forget)
    try:
        cache.set(validated_q, {
            "response": validated_response,
            "message_id": assistant_msg_id,
            "user_message_id": user_msg_id,
            "session_id": payload.session_id,
            "parent_message_id": user_msg_id,
            "citations": result.get("citations", [])
        })
    except Exception as cache_err:
        logger.warning(f"Failed to cache result: {cache_err}")

    return {
        "response": validated_response,
        "message_id": assistant_msg_id,
        "user_message_id": user_msg_id,
        "session_id": payload.session_id,
        "parent_message_id": user_msg_id,
        "citations": result.get("citations", [])
    }

def _load_history(db: Session, session_id: str, parent_msg_id: str | None, user_id: str) -> list:
    history = []
    if parent_msg_id:
        curr_id = parent_msg_id
        visited = set()
        while curr_id is not None:
            if curr_id in visited:
                break
            visited.add(curr_id)
            msg = db.query(Message).filter(Message.message_id == curr_id).first()
            if not msg:
                break
            history.append({"role": msg.role, "content": msg.content})
            curr_id = msg.parent_message_id
        history.reverse()
    else:
        try:
            memory = RedisMemory()
            history = memory.get_history(session_id)
        except Exception:
            history = []
    return history

@router.post("/query/stream")
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def run_query_stream(
    request: Request,
    payload: QueryRequest,
    x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from fastapi.responses import StreamingResponse
    from backend.agents.safety import validate_query, validate_output, SafetyValidationError
    from backend.agents.telemetry import ErrorEvent

    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        validated_q = await run_in_threadpool(validate_query, payload.query)
    except SafetyValidationError as se:
        raise HTTPException(status_code=400, detail=str(se))

    history = _load_history(db, payload.session_id, payload.parent_msg_id, user_id)

    state = {
        "query": validated_q,
        "history": history,
        "session_id": payload.session_id,
        "active_team_id": x_active_team_id or "default-team",
        "user_id": user_id,
        "rewritten_queries": [],
        "route": "",
        "retrieved_chunks": [],
        "retrieved_triples": [],
        "web_search_results": [],
        "final_context": [],
        "raw_response": "",
        "citations": [],
        "relevance_pass": True
    }

    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

    async def event_stream():
        full_response = ""
        citations_list = []
        persisted = False

        yield f"data: {json.dumps({'type': 'session', 'session_id': payload.session_id, 'user_message_id': user_msg_id, 'message_id': assistant_msg_id})}\n\n"

        try:
            async for event in ainvoke_with_events(state):
                if event.startswith("data: "):
                    try:
                        parsed = json.loads(event[6:].strip())
                        t = parsed.get("type")
                        if t == "text_chunk":
                            full_response += parsed.get("content", "")
                        elif t == "citation":
                            citations_list.append(parsed)
                        elif t == "done" and not persisted:
                            if full_response:
                                try:
                                    validated_response = validate_output(full_response)
                                except SafetyValidationError:
                                    yield f"data: {json.dumps({'type': 'error', 'detail': 'Output contains toxic language and is blocked.'})}\n\n"
                                    yield "data: [DONE]\n\n"
                                    return
                            else:
                                validated_response = full_response
                            await run_in_threadpool(
                                _persist_stream_messages,
                                db, validated_q, validated_response, citations_list,
                                user_msg_id, assistant_msg_id, payload.session_id,
                                payload.parent_msg_id, user_id
                            )
                            persisted = True
                    except json.JSONDecodeError:
                        pass
                yield event
        except Exception as e:
            logger.exception("Stream error")
            yield ErrorEvent("Internal error during response generation").to_sse()
        finally:
            if not persisted:
                if full_response:
                    try:
                        validated_response = validate_output(full_response)
                    except SafetyValidationError:
                        validated_response = full_response
                else:
                    validated_response = full_response

                await run_in_threadpool(
                    _persist_stream_messages,
                    db, validated_q, validated_response, citations_list,
                    user_msg_id, assistant_msg_id, payload.session_id,
                    payload.parent_msg_id, user_id
                )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _persist_stream_messages(
    db: Session, validated_q: str, validated_response: str,
    citations_list: list, user_msg_id: str, assistant_msg_id: str,
    session_id: str, parent_msg_id: str | None, user_id: str
):
    user_msg = Message(
        message_id=user_msg_id,
        session_id=session_id,
        parent_message_id=parent_msg_id,
        user_id=user_id,
        role="user",
        content=validated_q
    )
    db.add(user_msg)

    assistant_msg = Message(
        message_id=assistant_msg_id,
        session_id=session_id,
        parent_message_id=user_msg_id,
        user_id=user_id,
        role="assistant",
        content=validated_response,
        citations=citations_list
    )
    db.add(assistant_msg)

    try:
        db.commit()
    except Exception as persist_err:
        db.rollback()
        logger.error(f"Failed to persist stream messages: {persist_err}")

    if not parent_msg_id:
        try:
            memory = RedisMemory()
            memory.save_message(session_id, "user", validated_q)
            memory.save_message(session_id, "assistant", validated_response)
        except Exception as redis_err:
            logger.warning(f"Failed to save stream messages to Redis: {redis_err}")


@router.get("/chat/messages")
def get_chat_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_id = current_user.get("user_id") or current_user.get("sub")
        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id, Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        return {
            "messages": [
                {
                    "message_id": m.message_id,
                    "session_id": m.session_id,
                    "parent_message_id": m.parent_message_id,
                    "role": m.role,
                    "content": m.content,
                    "citations": m.citations,
                    "created_at": m.created_at.isoformat() if m.created_at else None
                }
                for m in messages
            ]
        }
    except Exception as e:
        logger.error(f"Failed to fetch messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve message history")

@router.get("/chat/sessions")
def get_chat_sessions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id") or current_user.get("sub")
    total_query = db.query(Message.session_id).filter(Message.user_id == user_id).distinct()
    total = total_query.count()
    results = total_query.order_by(Message.session_id).offset(offset).limit(limit).all()
    return {"sessions": [r[0] for r in results if r[0]], "total": total}
