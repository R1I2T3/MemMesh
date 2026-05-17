import json
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from db.dependencies import (
    get_graph_store,
    get_vector_store,
    build_rag_team_with_stores,
    set_graph_store_ctx,
    set_vector_store_ctx,
    set_citations_ctx,
    get_citations_ctx,
)
from db.session_store import SessionStore
from workers.celery_app import celery_app
from utils.observability import start_request, log_step, end_request, _configure_json_logging
from utils.input_validator import validate_query
from auth.middleware import require_auth
from auth.routes import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_json_logging()

    graph_store = GraphStore(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )
    vector_store = VectorStore(path=os.getenv("LANCEDB_PATH", "./data/lancedb"))
    session_store = SessionStore()

    app.state.graph_store = graph_store
    app.state.vector_store = vector_store
    app.state.session_store = session_store

    set_graph_store_ctx(graph_store)
    set_vector_store_ctx(vector_store)

    yield

    graph_store.close()
    session_store.close()


app = FastAPI(title="Graph-RAG AgentOS", version="1.0.0", lifespan=lifespan)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


class QueryRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "Graph-RAG AgentOS"}


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


@app.post("/query")
async def query(
    req: QueryRequest,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
    session_store: SessionStore = Depends(get_session_store),
):
    """
    Streaming endpoint to interact with the Graph-RAG Agent.
    Emits NDJSON events as the agent processes the request.
    """
    req.message = validate_query(req.message)
    ctx = start_request("POST", "/query")
    set_citations_ctx([])

    try:
        with log_step(ctx, "multi_hop_pre_retrieval"):
            rag_team = build_rag_team_with_stores(graph_store, vector_store)

        history = []
        if req.session_id and user.get("team_id"):
            limit = int(os.getenv("SESSION_HISTORY_LIMIT", "10"))
            messages = session_store.get_session_history(req.session_id, user["team_id"], limit=limit)
            history = [{"role": m["role"], "content": m["content"]} for m in messages]

        async def stream():
            with log_step(ctx, "agent_synthesis"):
                full_response = []
                async for event in rag_team.arun(
                    req.message,
                    stream=True,
                    session_id=req.session_id,
                    history=history if history else None,
                ):
                    full_response.append(event)
                    yield json.dumps(asdict(event)) + "\n"

                if req.session_id and user.get("team_id"):
                    session_store.save_message(req.session_id, user["id"], user.get("team_id"), "user", req.message)
                    response_text = "".join(
                        [e.content for e in full_response if hasattr(e, "content") and e.content]
                    )
                    if response_text:
                        session_store.save_message(
                            req.session_id, user["id"], user.get("team_id"), "assistant", response_text
                        )

            citations = get_citations_ctx()
            seen_ids = set()
            deduped = []
            for c in citations:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    deduped.append(c)

            if deduped:
                citation_event = {
                    "event": "citations",
                    "content": [c.to_dict() for c in deduped],
                }
                yield json.dumps(citation_event) + "\n"

            end_request(ctx, "ok", citation_count=len(deduped))

        return StreamingResponse(stream(), media_type="application/x-ndjson")
    except Exception as e:
        end_request(ctx, "error", error=str(e))
        raise


@app.get("/memory/search")
def memory_search(
    query: str,
    user: dict = Depends(require_auth),
    vector_store: VectorStore = Depends(get_vector_store),
):
    """Direct HTTP bridge to the Vector Engine using DI."""
    query = validate_query(query)
    from utils.embedder import embed_chunks

    embedded = embed_chunks([{"text": query}])
    if not embedded or "embedding" not in embedded[0]:
        return {"results": "Vector search failed: Could not generate embedding."}

    results = vector_store.search(query_vector=embedded[0]["embedding"])
    return {"results": results}


@app.get("/memory/graph")
def memory_graph(
    entity: str,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
):
    """Direct HTTP bridge to the Graph Engine using DI."""
    entity = validate_query(entity)
    results = graph_store.fetch_subgraph(entity)
    return {"results": results}


STAGING_DIR = Path("./data/staging")
STAGING_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xml", ".eml", ".txt", ".md", ".csv", ".xlsx", ".json",
}


@app.post("/session/new")
def new_session():
    """Generates a novel session ID for conversational state routing."""
    return {"session_id": str(uuid.uuid4())}


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    multimodal: bool = Query(False),
    user: dict = Depends(require_auth),
):
    """
    Accepts a document file, stages it, and queues async ingestion via Celery.
    Returns a task_id for status polling.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read file content")

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    unique_name = f"{uuid.uuid4()}_{file.filename}"
    staging_path = STAGING_DIR / unique_name

    try:
        with open(staging_path, "wb") as f:
            f.write(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save file to staging")

    try:
        task = celery_app.send_task(
            "workers.tasks.process_document_ingestion",
            args=[str(staging_path), multimodal],
        )
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Celery broker unavailable")

    return {"task_id": task.id, "status": "pending"}


@app.get("/ingest/{task_id}")
def ingest_status(task_id: str, user: dict = Depends(require_auth)):
    """
    Polls the Celery result backend for the status of an ingestion task.
    """
    result = AsyncResult(task_id, app=celery_app)

    state_map = {
        "PENDING": "pending",
        "RECEIVED": "pending",
        "STARTED": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "running",
        "REVOKED": "failed",
    }

    status = state_map.get(result.state, "pending")

    response = {"task_id": task_id, "status": status}

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.result)

    return response
