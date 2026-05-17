import os
import logging
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.google import Gemini

logger = logging.getLogger(__name__)


class RoutingDecision(BaseModel):
    route: str = Field(
        description="The recommended route: 'graph', 'vector', or 'hybrid'"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0"
    )
    reasoning: str = Field(
        description="Brief explanation of why this route was chosen"
    )


class QueryRouter:
    """
    Dynamic Query Routing using an LLM to decide whether to hit Vector, Graph, or Both.
    """

    def __init__(self):
        self._agent = Agent(
            model=Gemini(id="gemini-3.0-flash"),
            output_schema=RoutingDecision,
            description=(
                "You are a query routing expert for a Graph-RAG memory system. "
                "Classify each query into one of three routes:\n"
                "- 'graph': Queries about specific entity relationships, connections, "
                "dependencies, or who-knows-who type questions.\n"
                "- 'vector': Queries asking for summaries, semantic search, "
                "conceptual explanations, or open-ended recall.\n"
                "- 'hybrid': Queries that need both structured relationship lookup "
                "and semantic context, or when you're unsure.\n"
                "Default to 'hybrid' when in doubt."
            ),
        )

    def classify_query(self, query: str) -> str:
        """
        Classifies the query using LLM-based reasoning.
        Returns: 'graph', 'vector', or 'hybrid'
        """
        try:
            decision = self._agent.run(
                f"Route this query: {query}"
            )
            if decision and decision.content:
                route = decision.content.route.lower()
                if route in ("graph", "vector", "hybrid"):
                    return route
        except Exception as e:
            logger.warning(f"LLM routing failed ({e}), falling back to keyword heuristic")

        return self._fallback_classify(query)

    @staticmethod
    def _fallback_classify(query: str) -> str:
        """Keyword-based fallback when LLM routing is unavailable."""
        lower_query = query.lower()

        graph_keywords = [
            "relationship", "connect", "who is", "related to",
            "network", "depends on", "linked", "between",
        ]
        vector_keywords = [
            "summarize", "explain", "concept", "what did we talk about",
            "details about", "tell me about", "describe",
        ]

        graph_score = sum(1 for kw in graph_keywords if kw in lower_query)
        vector_score = sum(1 for kw in vector_keywords if kw in lower_query)

        if graph_score > vector_score and graph_score > 0:
            return "graph"
        elif vector_score > graph_score and vector_score > 0:
            return "vector"
        return "hybrid"
