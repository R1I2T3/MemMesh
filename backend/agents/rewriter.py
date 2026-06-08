from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

class QueryRewriterOutput(BaseModel):
    rewritten_queries: List[str] = Field(
        description="A list of 2-3 rewritten queries, including variants or step-back queries, to improve retrieval performance."
    )

def rewrite_query(query: str, model_name: str = "gemini-1.5-flash") -> List[str]:
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    structured_llm = llm.with_structured_output(QueryRewriterOutput)
    
    prompt = f"Analyze the user's query and generate 2-3 rewritten versions (variants or step-back queries) to improve retrieval: '{query}'"
    result = structured_llm.invoke(prompt)
    return result.rewritten_queries
