import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.google import Gemini

logger = logging.getLogger(__name__)

# Enterprise Pydantic schema enforcing strict ontology constraints for the GraphStore
class Triple(BaseModel):
    subject: str = Field(description="The source entity. Should be a clean, canonical noun.")
    subject_type: str = Field(default="UNKNOWN", description="Type/Label of the subject entity (e.g., PERSON, ORGANIZATION, TECHNOLOGY).")
    relationship: str = Field(description="The directional relationship or action verb linking subject and object. Must be UPPERCASE_SNAKE_CASE.")
    object: str = Field(description="The target entity. Should be a clean, canonical noun.")
    object_type: str = Field(default="UNKNOWN", description="Type/Label of the target entity.")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional contextual properties like confidence score, timeframe, etc.")

class ExtractionResult(BaseModel):
    triples: List[Triple]

class ExtractorAgent:
    def __init__(self):
        """
        Initializes the Subgraph Extraction Agent utilizing Agno's native structured outputs.
        """
        # We inject the gemini-3.0-flash model configured originally
        self._agent = Agent(
            model=Gemini(id="gemini-3.0-flash"),
            description="You are a pristine knowledge graph extraction expert. You aggressively analyze text chunks and extract discrete factual relational triples.",
            response_model=ExtractionResult,
            # Structured output natively avoids json parsing issues downstream
        )

    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Runs the extraction prompt against the provided text and maps it to dicts compatible
        with the db.graph_store.upsert_triples() architecture.
        """
        if not text or not text.strip():
            logger.warning("Empty text passed to ExtractorAgent.")
            return []

        try:
            prompt = f"Analyze the following text and extract all factual relational triples.\n\nText: {text}"
            response = self._agent.run(prompt)
            
            if response and response.content and hasattr(response.content, 'triples'):
                # model_dump ensures we get native Python dicts that PyArrow/Neo4j can safely process
                return [t.model_dump(exclude_none=True) for t in response.content.triples]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to extract triples: {e}")
            raise ValueError(f"Failed to parse triples from LLM response: {e}") from e
