from agno.agent import Agent
from agno.models.google import Gemini
from tools.vector_tool import vector_search
from tools.graph_tool import graph_search


def build_rag_team() -> Agent:
    """
    Constructs an enterprise Graph-RAG Swarm Team.
    Uses context-aware tools that resolve stores from contextvars or singletons.
    For DI-based usage, prefer build_rag_team_with_stores() from db.dependencies.
    """

    agent = Agent(
        name="Graph-RAG Master",
        model=Gemini(id="gemini-3.0-flash"),
        description="""You are a senior intelligent backend researcher.
        You have access to a Hybrid Memory Engine composed of a Vector Database and a Graph Database.
        When asked a question:
        1. Use vector_search to find unstructured textual context.
        2. Use graph_search to traverse exact entity relationships.
        3. Synthesize a pristine, grounded answer strictly based on the extracted memory.""",
        tools=[vector_search, graph_search],
    )
    return agent
