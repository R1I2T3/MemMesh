import logging
import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

class RouteDecision(BaseModel):
    route: Literal["vector", "graph", "hybrid"] = Field(
        description="Select the routing destination. Use 'vector' for unstructured queries/text retrieval, 'graph' for relational/knowledge queries, or 'hybrid' for a mix of both."
    )
    reasoning: str = Field(description="Explanation for why this route was selected.")

def route_query(query: str, model_name: str | None = None) -> RouteDecision:
    from backend.config import settings
    if model_name is None:
        model_name = settings.GEMINI_MODEL
    if os.environ.get("MOCK_LLM") == "true":
        return RouteDecision(route="hybrid", reasoning="Mock route decision for E2E testing")
    try:
        # We use temperature 0 for deterministic routing decisions
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=settings.GEMINI_API_KEY)
        structured_llm = llm.with_structured_output(RouteDecision)
        
        prompt_tmpl = ChatPromptTemplate.from_messages([
            ("system", "Analyze the user's query and decide the best routing destination: 'vector', 'graph', or 'hybrid'."),
            ("user", "{query}")
        ])
        chain = prompt_tmpl | structured_llm
        return chain.invoke({"query": query})
    except Exception as e:
        logger.exception("LLM call to route query failed. Falling back to hybrid.")
        return RouteDecision(route="hybrid", reasoning="Fallback due to LLM error")

