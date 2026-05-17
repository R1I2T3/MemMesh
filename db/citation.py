from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CitationResult:
    id: str
    type: str  # "vector" or "graph"
    content: str
    source: str = "unknown"
    chunk_index: Optional[int] = None
    entity_name: Optional[str] = None
    relationship: Optional[str] = None
    connected_entities: List[str] = field(default_factory=list)
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "entity_name": self.entity_name,
            "relationship": self.relationship,
            "connected_entities": self.connected_entities,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_vector_result(cls, record: dict) -> "CitationResult":
        return cls(
            id=record.get("id", ""),
            type="vector",
            content=record.get("text", ""),
            source=record.get("source", "unknown"),
            chunk_index=record.get("chunk_index"),
            relevance_score=record.get("distance", 0.0),
        )

    @classmethod
    def from_graph_result(cls, record: dict, hop: int = 0) -> "CitationResult":
        src = record.get("source", "")
        tgt = record.get("target", "")
        path = record.get("relationship_path", [])
        rel_str = ", ".join(path) if path else "RELATED_TO"

        return cls(
            id=f"graph:{src}:{tgt}:{rel_str}",
            type="graph",
            content=f"{src} -[{rel_str}]-> {tgt} ({record.get('target_type', 'UNKNOWN')})",
            source="knowledge_graph",
            entity_name=src,
            relationship=rel_str,
            connected_entities=[tgt],
            relevance_score=1.0 / (hop + 1),
        )
