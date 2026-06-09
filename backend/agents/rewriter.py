import logging
import os
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

class QueryRewriterOutput(BaseModel):
    rewritten_queries: List[str] = Field(
        description="A list of 2-3 rewritten queries, including variants or step-back queries, to improve retrieval performance."
    )

def rewrite_query(query: str, model_name: str | None = None) -> List[str]:
    from backend.config import settings
    if model_name is None:
        model_name = settings.GEMINI_MODEL
    if os.environ.get("MOCK_LLM") == "true":
        return [query]
    try:
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        structured_llm = llm.with_structured_output(QueryRewriterOutput)
        
        prompt_tmpl = ChatPromptTemplate.from_messages([
            ("system", "Analyze the user's query and generate 2-3 rewritten versions (variants or step-back queries) to improve retrieval."),
            ("user", "{query}")
        ])
        chain = prompt_tmpl | structured_llm
        result = chain.invoke({"query": query})
        return result.rewritten_queries
    except Exception as e:
        logger.exception("LLM call to rewrite query failed. Falling back to original query.")
        return [query]

