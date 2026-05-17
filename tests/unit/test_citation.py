import pytest
from db.citation import CitationResult


@pytest.mark.unit
def test_citation_result_from_vector_result():
    vector_record = {
        "id": "uuid-abc-123",
        "text": "LanceDB is a vector database.",
        "source": "docs.pdf",
        "chunk_index": 2,
        "distance": 0.15,
    }
    result = CitationResult.from_vector_result(vector_record)

    assert result.id == "uuid-abc-123"
    assert result.type == "vector"
    assert result.content == "LanceDB is a vector database."
    assert result.source == "docs.pdf"
    assert result.chunk_index == 2
    assert result.relevance_score == 0.15
    assert result.entity_name is None
    assert result.relationship is None
    assert result.connected_entities == []


@pytest.mark.unit
def test_citation_result_from_graph_result():
    graph_record = {
        "source": "Alice",
        "relationship_path": ["WORKS_AT", "MANAGES"],
        "target": "Acme",
        "target_type": "ORGANIZATION",
    }
    result = CitationResult.from_graph_result(graph_record, hop=1)

    assert result.type == "graph"
    assert result.entity_name == "Alice"
    assert result.relationship == "WORKS_AT, MANAGES"
    assert result.connected_entities == ["Acme"]
    assert result.relevance_score == 0.5  # 1/(1+1)
    assert result.source == "knowledge_graph"
    assert "Alice" in result.content
    assert "Acme" in result.content


@pytest.mark.unit
def test_citation_result_to_dict():
    result = CitationResult(
        id="test-id",
        type="vector",
        content="some text",
        source="file.txt",
        chunk_index=0,
        relevance_score=0.9,
    )
    d = result.to_dict()

    assert d["id"] == "test-id"
    assert d["type"] == "vector"
    assert d["content"] == "some text"
    assert d["source"] == "file.txt"
    assert d["chunk_index"] == 0
    assert d["relevance_score"] == 0.9


@pytest.mark.unit
def test_citation_result_deduplication_by_id():
    results = [
        CitationResult(id="a", type="vector", content="first"),
        CitationResult(id="b", type="graph", content="second"),
        CitationResult(id="a", type="vector", content="duplicate"),
    ]
    seen = set()
    deduped = []
    for r in results:
        if r.id not in seen:
            seen.add(r.id)
            deduped.append(r)

    assert len(deduped) == 2
    assert [r.id for r in deduped] == ["a", "b"]
