import json
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI
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
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared connection-pooled stores
    graph_store = GraphStore(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )
    vector_store = VectorStore(path=os.getenv("LANCEDB_PATH", "./data/lancedb"))

    # Store in app.state for DI access
    app.state.graph_store = graph_store
    app.state.vector_store = vector_store

    # Set contextvars so legacy tools work during requests
    set_graph_store_ctx(graph_store)
    set_vector_store_ctx(vector_store)

    yield

    # Shutdown: close connections
    graph_store.close()


app = FastAPI(title="Graph-RAG AgentOS", version="1.0.0", lifespan=lifespan)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "Graph-RAG AgentOS"}


@app.post("/query")
async def query(
    req: QueryRequest,
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
):
    """
    Streaming endpoint to interact with the Graph-RAG Agent.
    Emits NDJSON events as the agent processes the request.
    """
    rag_team = build_rag_team_with_stores(graph_store, vector_store)

    async def stream():
        async for event in rag_team.arun(
            req.message,
            stream=True,
            session_id=req.session_id,
        ):
            yield json.dumps(asdict(event)) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/memory/search")
def memory_search(
    query: str,
    vector_store: VectorStore = Depends(get_vector_store),
):
    """Direct HTTP bridge to the Vector Engine using DI."""
    from utils.embedder import embed_chunks

    embedded = embed_chunks([{"text": query}])
    if not embedded or "embedding" not in embedded[0]:
        return {"results": "Vector search failed: Could not generate embedding."}

    results = vector_store.search(query_vector=embedded[0]["embedding"])
    return {"results": results}


@app.get("/memory/graph")
def memory_graph(
    entity: str,
    graph_store: GraphStore = Depends(get_graph_store),
):
    """Direct HTTP bridge to the Graph Engine using DI."""
    results = graph_store.fetch_subgraph(entity)
    return {"results": results}


@app.post("/session/new")
def new_session():
    """Generates a novel session ID for conversational state routing."""
    return {"session_id": str(uuid.uuid4())}
