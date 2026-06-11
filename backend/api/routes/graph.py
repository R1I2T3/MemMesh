import logging
from fastapi import APIRouter, Depends, Query
from backend.auth.middleware import require_team_membership
from backend.db.neo4j import Neo4jManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/team/{team_id}/graph", tags=["graph"])


@router.get("/explore")
def explore_graph(
    team_id: str = Depends(require_team_membership()),
    query: str = Query("", max_length=200),
    limit: int = Query(50, ge=1, le=200),
):
    neo4j_mgr = Neo4jManager()
    nodes = neo4j_mgr.get_entities_for_explore(team_id, query, limit)
    edges = neo4j_mgr.get_relationships_for_explore(team_id, query, limit)
    return {"nodes": nodes, "edges": edges}
