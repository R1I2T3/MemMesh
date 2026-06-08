import uuid
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.db.mysql import get_db
from backend.models import Message
from backend.auth.middleware import get_current_user
from backend.agents.memory import RedisMemory
from backend.agents.graph_orchestrator import get_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["query"])

@router.get("/query")
def run_query(
    q: str = Query(..., min_length=3, max_length=2000),
    session_id: str = "default-session",
    parent_msg_id: str | None = Query(None),
    team_id: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.debug(f"Query request: {q}, session_id: {session_id}, parent_msg_id: {parent_msg_id}")
    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

    # 1. Safety validation
    from backend.agents.safety import validate_query, validate_output, SafetyValidationError
    try:
        validated_q = validate_query(q)
    except SafetyValidationError as se:
        raise HTTPException(status_code=400, detail=str(se))

    # 2. Context history reconstruction
    history = []
    if parent_msg_id:
        curr_id = parent_msg_id
        visited = set()
        while curr_id is not None:
            if curr_id in visited:
                logger.warning(f"Circular reference detected in parent message chain for message: {curr_id}")
                break
            visited.add(curr_id)
            msg = db.query(Message).filter(Message.message_id == curr_id).first()
            if not msg:
                logger.warning(f"Parent message ID {curr_id} not found in database. Ending history traversal.")
                break
            history.append({"role": msg.role, "content": msg.content})
            curr_id = msg.parent_message_id
        history.reverse()
    else:
        try:
            memory = RedisMemory()
            history = memory.get_history(session_id)
        except Exception as e:
            logger.warning(f"Failed to fetch history from Redis memory: {e}")
            history = []

    # 3. Invoke LangGraph orchestrator
    graph = get_graph()
    try:
        result = graph.invoke({
            "query": validated_q,
            "history": history,
            "session_id": session_id,
            "active_team_id": team_id or "default-team",
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
        content=validated_response
    )
    db.add(assistant_msg)
    
    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.error(f"Database save message failed: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to persist conversation history")

    # 5. Update Redis memory if not branched (parent_msg_id is None)
    if not parent_msg_id:
        try:
            memory = RedisMemory()
            memory.save_message(session_id, "user", validated_q)
            memory.save_message(session_id, "assistant", validated_response)
        except Exception as redis_err:
            logger.warning(f"Failed to save messages to Redis memory: {redis_err}")

    return {
        "response": validated_response,
        "message_id": assistant_msg_id,
        "user_message_id": user_msg_id,
        "session_id": session_id,
        "parent_message_id": user_msg_id
    }

@router.get("/query/stream")
async def run_query_stream(
    q: str = Query(..., min_length=3, max_length=2000),
    session_id: str = "default-session",
    parent_msg_id: str | None = Query(None),
    team_id: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import re
    import json
    import asyncio
    from fastapi.responses import StreamingResponse
    from starlette.concurrency import run_in_threadpool
    from backend.agents.safety import validate_query, validate_output, SafetyValidationError

    logger.debug(f"Query stream request: {q}, session_id: {session_id}, parent_msg_id: {parent_msg_id}")
    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

    # 1. Safety validation
    try:
        validated_q = await run_in_threadpool(validate_query, q)
    except SafetyValidationError as se:
        raise HTTPException(status_code=400, detail=str(se))

    # 2. Context history reconstruction
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

    # 3. Invoke LangGraph orchestrator
    graph = get_graph()
    try:
        state = {
            "query": validated_q,
            "history": history,
            "session_id": session_id,
            "active_team_id": team_id or "default-team",
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
        result = await run_in_threadpool(graph.invoke, state)
    except Exception as e:
        logger.error(f"LangGraph execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

    raw_response = result.get("raw_response", "")

    # Output safety validation
    try:
        validated_response = await run_in_threadpool(validate_output, raw_response)
    except SafetyValidationError as se:
        raise HTTPException(status_code=400, detail=str(se))

    # 4. Save to database
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

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
        content=validated_response
    )
    db.add(assistant_msg)
    
    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.error(f"Database save message failed: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to persist conversation history")

    # 5. Update Redis memory if not branched (parent_msg_id is None)
    if not parent_msg_id:
        try:
            memory = RedisMemory()
            memory.save_message(session_id, "user", validated_q)
            memory.save_message(session_id, "assistant", validated_response)
        except Exception:
            pass

    # 6. Stream generator
    async def event_generator():
        # First send metadata (IDs) so frontend knows message structure
        yield f"data: {json.dumps({'message_id': assistant_msg_id, 'user_message_id': user_msg_id})}\n\n"
        await asyncio.sleep(0.01)

        # Split response into tokens/words (preserving whitespace)
        tokens = re.findall(r"\S+|\s+", validated_response)
        for token in tokens:
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0.01)
            
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_id = current_user.get("user_id") or current_user.get("sub")
        results = (
            db.query(Message.session_id)
            .filter(Message.user_id == user_id)
            .distinct()
            .all()
        )
        return {"sessions": [r[0] for r in results if r[0]]}
    except Exception as e:
        logger.error(f"Failed to fetch chat sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session list")
