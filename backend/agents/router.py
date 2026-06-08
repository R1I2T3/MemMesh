from typing import Literal
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

class RouteDecision(BaseModel):
    route: Literal["vector", "graph", "hybrid"] = Field(
        description="Select the routing destination. Use 'vector' for unstructured queries/text retrieval, 'graph' for relational/knowledge queries, or 'hybrid' for a mix of both."
    )
    reasoning: str = Field(description="Explanation for why this route was selected.")

def route_query(query: str, model_name: str = "gemini-1.5-flash") -> RouteDecision:
    # We use temperature 0 for deterministic routing decisions
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    structured_llm = llm.with_structured_output(RouteDecision)
    
    prompt = f"Analyze the following query and decide the best routing destination: '{query}'"
    return structured_llm.invoke(prompt)
