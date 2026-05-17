import logging
from typing import List
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.google import Gemini

logger = logging.getLogger(__name__)


class RewritingResult(BaseModel):
    step_back_query: str = Field(
        description="A broader, more general version of the query"
    )
    alternative_queries: List[str] = Field(
        description="2-3 rephrased variants of the original query"
    )


class QueryRewriter:
    """
    Pre-retrieval query rewriting for improved RAG recall.
    Generates a step-back query (broader concept) and alternative phrasings.
    """

    def __init__(self):
        self._agent = Agent(
            model=Gemini(id="gemini-3.0-flash"),
            output_schema=RewritingResult,
            description=(
                "You are a query rewriting expert for RAG systems. "
                "Given a user query, produce:\n"
                "1. A 'step-back' query: a broader, more general version that captures "
                "the underlying concept.\n"
                "2. Two to three alternative phrasings: different ways to ask the same "
                "question, using different vocabulary or sentence structure.\n"
                "Keep all queries concise and focused on information retrieval."
            ),
        )

    def rewrite(self, query: str) -> RewritingResult:
        """
        Rewrites the query into a step-back version and alternative phrasings.
        Falls back to the original query if the LLM is unavailable.
        """
        try:
            response = self._agent.run(f"Rewrite this query: {query}")
            if response and response.content:
                content = response.content
                step_back = getattr(content, "step_back_query", query)
                alternatives = getattr(content, "alternative_queries", [])
                if not step_back or step_back.strip() == "":
                    step_back = query
                if not isinstance(alternatives, list):
                    alternatives = []
                return RewritingResult(
                    step_back_query=step_back,
                    alternative_queries=alternatives,
                )
        except Exception as e:
            logger.warning(f"Query rewriting failed ({e}), using original query")

        return RewritingResult(
            step_back_query=query,
            alternative_queries=[],
        )
