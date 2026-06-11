def retrieve_parent_documents(weaviate_mgr, tenant_id: str, query: str, current_user_id: str) -> list[dict]:
    chunks = weaviate_mgr.hybrid_search(tenant_id, query, current_user_id)
    if not chunks:
        return []

    seen = set()
    result = []
    for chunk in chunks:
        pid = chunk.get("parent_id")
        if pid and pid not in seen:
            seen.add(pid)
            result.append({
                "parent_id": pid,
                "text": chunk.get("text", ""),
                "content": chunk.get("text", ""),
                "page_number": chunk.get("page_number", 1),
                "bbox": chunk.get("bbox", []),
            })
    return result
