import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass
from fastapi.testclient import TestClient


@dataclass
class MockStreamEvent:
    event: str = "run_content"
    content: str = "mocked grounded answer"
    content_type: str = "str"
    created_at: int = 1234567890
    agent_id: str = "test-agent"
    agent_name: str = "Graph-RAG Master"
    run_id: str | None = None
    parent_run_id: str | None = None
    session_id: str | None = None
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    step_id: str | None = None
    step_name: str | None = None
    step_index: int | None = None
    nested_depth: int = 0
    tools: list | None = None
    reasoning_content: str | None = None
    model_provider_data: dict | None = None
    citations: list | None = None
    references: list | None = None
    image: object | None = None
    response_audio: object | None = None
    additional_input: list | None = None
    reasoning_steps: list | None = None
    reasoning_messages: list | None = None
    workflow_agent: bool = False


async def mock_arun_stream(*args, **kwargs):
    yield MockStreamEvent()


@pytest.fixture(scope="module")
def client():
    import sys
    mods_to_remove = [m for m in sys.modules if m == "agentos" or m.startswith("agentos.")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_agent = MagicMock()
    mock_agent.arun = mock_arun_stream

    mock_celery_app = MagicMock()
    mock_async_result = MagicMock()

    celery_mod = MagicMock()
    celery_result_mod = MagicMock()
    celery_result_mod.AsyncResult = mock_async_result
    workers_mod = MagicMock()
    workers_celery_app_mod = MagicMock()
    workers_celery_app_mod.celery_app = mock_celery_app

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        import agentos
        agentos.celery_app = mock_celery_app
        agentos.AsyncResult = mock_async_result

        original_lifespan = agentos.lifespan

        async def mock_lifespan(app):
            app.state.graph_store = mock_graph_store
            app.state.vector_store = mock_vector_store
            from db.dependencies import set_graph_store_ctx, set_vector_store_ctx
            set_graph_store_ctx(mock_graph_store)
            set_vector_store_ctx(mock_vector_store)
            yield

        agentos.app = agentos.FastAPI(title="Graph-RAG AgentOS", version="1.0.0", lifespan=mock_lifespan)
        agentos.app.add_middleware(
            agentos.CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @agentos.app.get("/health")
        def health():
            return {"status": "ok", "service": "Graph-RAG AgentOS"}

        @agentos.app.post("/query")
        async def query_endpoint(
            req: agentos.QueryRequest,
        ):
            ctx = agentos.start_request("POST", "/query")
            agentos.set_citations_ctx([])

            try:
                with agentos.log_step(ctx, "multi_hop_pre_retrieval"):
                    rag_team = mock_agent

                async def stream():
                    with agentos.log_step(ctx, "agent_synthesis"):
                        async for event in rag_team.arun(
                            req.message,
                            stream=True,
                            session_id=req.session_id,
                        ):
                            yield json.dumps(agentos.asdict(event)) + "\n"

                    citations = agentos.get_citations_ctx()
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

                    agentos.end_request(ctx, "ok", citation_count=len(deduped))

                return agentos.StreamingResponse(stream(), media_type="application/x-ndjson")
            except Exception as e:
                agentos.end_request(ctx, "error", error=str(e))
                raise

        from agentos import app
        with TestClient(app) as test_client:
            yield test_client


@pytest.mark.unit
def test_query_endpoint_produces_ndjson_with_citations(client):
    """The /query endpoint should include a citations event after the answer."""
    r = client.post("/query", json={"message": "What is LanceDB?"})
    assert r.status_code == 200
    lines = [line for line in r.iter_lines() if line.strip()]
    assert len(lines) >= 1
    for line in lines:
        parsed = json.loads(line)
        assert "event" in parsed
        assert "content" in parsed


@pytest.mark.unit
def test_health_endpoint_still_works(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
