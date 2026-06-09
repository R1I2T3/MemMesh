import logging
from backend.tasks.celery_app import celery_app
from backend.db.mysql import SessionLocal
from backend.models import Team
from backend.db.weaviate import WeaviateManager
from backend.db.neo4j import Neo4jManager

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.tasks.decay_worker.decay_memory_weights")
def decay_memory_weights() -> dict:
    logger.info("Starting memory decay background task...")
    
    db = SessionLocal()
    try:
        teams = db.query(Team).all()
        team_ids = [t.team_id for t in teams]
    except Exception as e:
        logger.error("Failed to query active teams from MySQL: %s", e)
        raise
    finally:
        db.close()

    logger.info("Found %d active team(s) for decay processing.", len(team_ids))
    
    # 1. Decay Neo4j Graph
    neo4j_mgr = Neo4jManager()
    try:
        for team_id in team_ids:
            logger.info("Applying Neo4j memory decay for team: %s", team_id)
            try:
                with neo4j_mgr._get_session(team_id) as session:
                    # Decrement entity importance score
                    session.run(
                        "MATCH (e:Entity {team_id: $team_id}) SET e.importance_score = e.importance_score - 0.1",
                        team_id=team_id
                    )
                    # Prune entities with low score
                    session.run(
                        "MATCH (e:Entity {team_id: $team_id}) WHERE e.importance_score <= 0.0 DETACH DELETE e",
                        team_id=team_id
                    )
                    # Decrement relationship weights
                    session.run(
                        "MATCH ()-[r:RELATES_TO {team_id: $team_id}]->() SET r.weight = r.weight - 0.1",
                        team_id=team_id
                    )
                    # Prune low weight relationships
                    session.run(
                        "MATCH ()-[r:RELATES_TO {team_id: $team_id}]->() WHERE r.weight <= 0.0 DELETE r",
                        team_id=team_id
                    )
            except Exception as team_neo4j_exc:
                logger.error("Error decaying Neo4j entities/relationships for team %s: %s", team_id, team_neo4j_exc)
    except Exception as e:
        logger.error("Error in Neo4j decay processing: %s", e)
    finally:
        neo4j_mgr.close()

    # 2. Decay Weaviate Chunks
    weaviate_mgr = WeaviateManager()
    try:
        for team_id in team_ids:
            try:
                collection = weaviate_mgr.client.collections.get("DocumentChunk").with_tenant(team_id)
                results = collection.query.fetch_objects(limit=100)
                logger.info("Fetched %d chunk(s) from Weaviate for team '%s' for memory decay.", len(results.objects), team_id)
                
                for obj in results.objects:
                    props = obj.properties
                    if "importance_score" in props:
                        current_score = props.get("importance_score")
                        if current_score is None:
                            current_score = 1.0
                        new_score = max(0.0, float(current_score) - 0.1)
                        collection.data.update(
                            uuid=obj.uuid,
                            properties={"importance_score": new_score}
                        )
                        logger.info("Decayed Weaviate chunk %s importance_score from %s to %s", obj.uuid, current_score, new_score)
            except Exception as weaviate_exc:
                logger.info("Weaviate decay info/warning for team '%s' (tenant might not exist or be offline): %s", team_id, weaviate_exc)
    except Exception as e:
        logger.warning("Weaviate client decay iteration failed: %s", e)
    finally:
        weaviate_mgr.close()

    logger.info("Memory decay background task completed successfully.")
    return {"status": "success", "processed_teams": len(team_ids)}
