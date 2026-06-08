from backend.db.mysql import SessionLocal
from backend.models import ParentDocument

def retrieve_parent_documents(weaviate_mgr, tenant_id: str, query: str, current_user_id: str) -> list[dict]:
    # Query Weaviate hybrid search
    chunks = weaviate_mgr.hybrid_search(tenant_id, query, current_user_id)
    if not chunks:
        return []

    parent_ids = list(set(c["parent_id"] for c in chunks if c.get("parent_id")))
    if not parent_ids:
        return []

    # Single batch query to avoid N+1 queries
    with SessionLocal() as session:
        parents = session.query(ParentDocument).filter(ParentDocument.parent_id.in_(parent_ids)).all()
        # Create a mapping of parent_id to ParentDocument for order preservation or quick lookup
        parent_map = {p.parent_id: p for p in parents}

    # Return parent documents in the order of their best matching chunks
    seen_parents = set()
    result = []
    for chunk in chunks:
        pid = chunk.get("parent_id")
        if pid and pid in parent_map and pid not in seen_parents:
            p = parent_map[pid]
            result.append({
                "parent_id": p.parent_id,
                "text": p.content,
                "content": p.content,
            })
            seen_parents.add(pid)
            
    return result
