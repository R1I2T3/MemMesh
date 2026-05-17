import json
import uuid
from dataclasses import asdict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agents.rag_team import build_rag_team
from tools.vector_tool import vector_search
from tools.graph_tool import graph_search

app = FastAPI(title="Graph-RAG AgentOS", version="1.0.0")

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# Initialize the RAG Team singleton
rag_team = build_rag_team()

class QueryRequest(BaseModel):
    message: str
    session_id: str | None = None

@app.get("/health")
def health():
    return {"status": "ok", "service": "Graph-RAG AgentOS"}

@app.post("/query")
async def query(req: QueryRequest):
    """
    Streaming endpoint to interact with the Graph-RAG Agent.
    Emits NDJSON events as the agent processes the request.
    """
    async def stream():
        async for event in rag_team.arun(
            req.message,
            stream=True,
            session_id=req.session_id,
        ):
            yield json.dumps(asdict(event)) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")

@app.get("/memory/search")
def memory_search(query: str):
    """Direct HTTP bridge to the Vector Engine"""
    return {"results": vector_search(query)}

@app.get("/memory/graph")
def memory_graph(entity: str):
    """Direct HTTP bridge to the Graph Engine"""
    return {"results": graph_search(entity)}

@app.post("/session/new")
def new_session():
    """Generates a novel session ID for conversational state routing"""
    return {"session_id": str(uuid.uuid4())}
