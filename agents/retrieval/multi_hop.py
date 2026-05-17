import logging
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, Field

from db.citation import CitationResult
from db.graph_store import GraphStore

logger = logging.getLogger(__name__)


class EntityExtractionResult(BaseModel):
    entities: List[str] = Field(description="List of entity names extracted from the query")


class EntitySelectionResult(BaseModel):
    entities: List[str] = Field(description="List of entity names to expand in the next hop")


class TerminationResult(BaseModel):
    should_stop: bool = Field(description="True if the accumulated context is sufficient to answer the query")


@dataclass
class MultiHopResult:
    results: List[CitationResult] = field(default_factory=list)
    hops_taken: int = 0
    entities_expanded: List[str] = field(default_factory=list)


class MultiHopRetriever:
    def __init__(self, graph_store: GraphStore, model, max_hops: int = 5):
        self.graph_store = graph_store
        self.model = model
        self.max_hops = max_hops

    def run(self, query: str) -> MultiHopResult:
        accumulated: List[CitationResult] = []
        seen_keys = set()
        entities_expanded: List[str] = []

        try:
            seed_entities = self._extract_entities(query)
        except Exception as e:
            logger.warning(f"Multi-hop entity extraction failed: {e}")
            return MultiHopResult(results=[], hops_taken=0, entities_expanded=[])

        current_entities = seed_entities

        for hop in range(self.max_hops):
            if not current_entities:
                break

            hop_results = []
            for entity in current_entities:
                try:
                    subgraph = self.graph_store.fetch_subgraph(entity, depth=1)
                    for record in subgraph:
                        citation = CitationResult.from_graph_result(record, hop=hop)
                        dedup_key = (citation.entity_name, citation.relationship, tuple(citation.connected_entities))
                        if dedup_key not in seen_keys:
                            seen_keys.add(dedup_key)
                            hop_results.append(citation)
                    if entity not in entities_expanded:
                        entities_expanded.append(entity)
                except Exception as e:
                    logger.warning(f"Multi-hop fetch failed for '{entity}' at hop {hop}: {e}")

            accumulated.extend(hop_results)

            try:
                should_stop = self._should_terminate(query, accumulated)
            except Exception as e:
                logger.warning(f"Multi-hop termination check failed: {e}")
                should_stop = False

            if should_stop:
                return MultiHopResult(
                    results=accumulated,
                    hops_taken=hop + 1,
                    entities_expanded=entities_expanded,
                )

            try:
                current_entities = self._select_entities(query, accumulated)
            except Exception as e:
                logger.warning(f"Multi-hop entity selection failed: {e}")
                break

        return MultiHopResult(
            results=accumulated,
            hops_taken=self.max_hops,
            entities_expanded=entities_expanded,
        )

    def _extract_entities(self, query: str) -> List[str]:
        from agno.agent import Agent
        agent = Agent(model=self.model, output_schema=EntityExtractionResult)
        response = agent.run(f"Extract all entity names (people, organizations, concepts, technologies) from this query: {query}")
        if response and response.content and response.content.entities:
            return response.content.entities
        raise ValueError("No entities extracted")

    def _select_entities(self, query: str, accumulated: List[CitationResult]) -> List[str]:
        from agno.agent import Agent
        context_summary = "\n".join(r.content for r in accumulated[:20])
        agent = Agent(model=self.model, output_schema=EntitySelectionResult)
        response = agent.run(
            f"Query: {query}\n\n"
            f"Current context:\n{context_summary}\n\n"
            f"Which entity names from the context should be expanded next to better answer the query? "
            f"Return only entities that would reveal new, relevant information."
        )
        if response and response.content and response.content.entities:
            return response.content.entities
        raise ValueError("No entities selected")

    def _should_terminate(self, query: str, accumulated: List[CitationResult]) -> bool:
        from agno.agent import Agent
        context_summary = "\n".join(r.content for r in accumulated[:20])
        agent = Agent(model=self.model, output_schema=TerminationResult)
        response = agent.run(
            f"Query: {query}\n\n"
            f"Accumulated graph context:\n{context_summary}\n\n"
            f"Is this context sufficient to answer the query? Answer true if yes, false if more graph traversal is needed."
        )
        if response and response.content:
            return response.content.should_stop
        raise ValueError("Termination check failed")
