import os
import logging
from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

class RelevanceGrade(BaseModel):
    score: float = Field(description="Normalized relevance score between 0.0 (completely irrelevant) and 1.0 (fully sufficient)")
    reasoning: str = Field(description="Reasoning explaining the decision")

def evaluate_retrieval(state: Dict[str, Any]) -> Dict[str, Any]:
    # Mock behavior for testing / offline execution
    if os.environ.get("MOCK_LLM") == "true":
        query_lower = state.get("query", "").lower()
        chunks = state.get("retrieved_chunks", [])
        if not chunks or "irrelevant" in query_lower:
            return {
                "relevance_pass": False,
                "telemetry_log": "CRAG score: 0.1. Mocked irrelevant query."
            }
        return {
            "relevance_pass": True,
            "telemetry_log": "CRAG score: 0.9. Mocked relevant query."
        }

    try:
        from backend.config import settings
        llm = ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL, temperature=0)
        structured_llm = llm.with_structured_output(RelevanceGrade)
        
        prompt = ChatPromptTemplate.from_template(
            "You are an evaluator. Determine if the following retrieved context is sufficient and relevant "
            "to answer the user query.\n\n"
            "User Query: {query}\n\n"
            "Retrieved Context:\n{context}\n\n"
            "Assess relevance honestly. Provide a score from 0.0 to 1.0."
        )
        
        chunks = state.get("retrieved_chunks", [])
        context_str = "\n".join([c.get("text", c.get("content", "")) for c in chunks])
        if not context_str.strip():
            return {
                "relevance_pass": False,
                "telemetry_log": "CRAG score: 0.0. Reasoning: No context retrieved."
            }
            
        chain = prompt | structured_llm
        result = chain.invoke({"query": state["query"], "context": context_str})
        
        return {
            "relevance_pass": result.score >= 0.5,
            "telemetry_log": f"CRAG score: {result.score}. Reasoning: {result.reasoning}"
        }
    except Exception as e:
        logger.exception("CRAG evaluator LLM call failed. Defaulting to True.")
        return {
            "relevance_pass": True,
            "telemetry_log": f"CRAG failed with exception: {e}. Defaulting to relevance_pass=True."
        }
