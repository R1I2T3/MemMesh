from backend.middleware.logging_config import setup_logging
# Initialize logging as early as possible
setup_logging()

import sys
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.db.mysql import get_db, SessionLocal
from backend.config import settings
from backend.models import User
from backend.auth.passwords import hash_password
from backend.api.routes.auth import router as auth_router
from backend.api.routes.admin import admin_router, user_router
from backend.api.routes.upload import router as upload_router
from backend.api.routes.query import router as query_router
from backend.api.routes.feedback import router as feedback_router
from backend.api.routes.eval import router as eval_router
from backend.api.routes.decay import router as decay_router
from backend.api.routes.analytics import router as analytics_router
from backend.db.weaviate import WeaviateManager

logger = logging.getLogger(__name__)

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
    LangChainInstrumentor().instrument()
except ImportError:
    logger.warning("Phoenix tracing not available")



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MemMesh starting up...")
    
    # Initialize Weaviate schema
    weaviate_mgr = None
    try:
        weaviate_mgr = WeaviateManager()
        weaviate_mgr.ensure_schema()
        logger.info("Weaviate schema initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Weaviate schema (Weaviate might be offline): {e}")

    if "pytest" not in sys.modules:
        # Seed superadmin safely; startup should continue if the database is offline.
        db: Session | None = None
        try:
            with SessionLocal() as db:
                admin = db.query(User).filter_by(email=settings.SUPERADMIN_EMAIL).first()
                if not admin:
                    logger.info("Seeding superadmin user...")
                    admin_id = str(uuid.uuid4())
                    admin = User(
                        user_id=admin_id,
                        email=settings.SUPERADMIN_EMAIL,
                        password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                        global_role="superadmin",
                    )
                    db.add(admin)
                    db.commit()
                    logger.info(f"Superadmin user seeded with ID: {admin_id}")
                else:
                    logger.info("Superadmin user already exists.")
        except Exception as e:
            logger.error(f"Error seeding superadmin user (database might be offline): {e}")
            if db is not None:
                db.rollback()
    else:
        logger.info("Skipping superadmin seeding in test mode.")
    yield
    
    # Close Weaviate client on shutdown
    try:
        if weaviate_mgr is not None:
            logger.info("Closing Weaviate client...")
            weaviate_mgr.close()
    except Exception as e:
        logger.error(f"Error closing Weaviate client: {e}")

    # Close Redis client on shutdown
    try:
        from backend.agents.memory import _redis_client
        if _redis_client is not None:
            logger.info("Closing Redis client...")
            _redis_client.close()
    except Exception as e:
        logger.error(f"Error closing Redis client: {e}")
        
    logger.info("MemMesh shutting down...")

app = FastAPI(title="MemMesh API", version="0.1.0", lifespan=lifespan)

from backend.middleware.error_handler import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler
)
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.rate_limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(feedback_router)
app.include_router(eval_router)
app.include_router(decay_router)
app.include_router(analytics_router)

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    statuses = {}
    
    # 1. MySQL check
    try:
        db.execute(text("SELECT 1"))
        statuses["mysql"] = "ok"
    except Exception as e:
        logger.error(f"MySQL health check failed: {e}")
        statuses["mysql"] = "error"
        
    # 2. Redis check
    try:
        from backend.agents.memory import get_redis_client
        redis_client = get_redis_client()
        if redis_client.ping():
            statuses["redis"] = "ok"
        else:
            statuses["redis"] = "error"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        statuses["redis"] = "error"
        
    # 3. Weaviate check
    try:
        from backend.db.weaviate import WeaviateManager
        weaviate_mgr = WeaviateManager()
        try:
            if weaviate_mgr.client.is_live():
                statuses["weaviate"] = "ok"
            else:
                statuses["weaviate"] = "error"
        finally:
            weaviate_mgr.close()
    except Exception as e:
        logger.error(f"Weaviate health check failed: {e}")
        statuses["weaviate"] = "error"
        
    # 4. Neo4j check
    try:
        from backend.db.neo4j import Neo4jManager
        neo4j_mgr = Neo4jManager()
        try:
            neo4j_mgr.driver.verify_connectivity()
            statuses["neo4j"] = "ok"
        finally:
            neo4j_mgr.close()
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        statuses["neo4j"] = "error"
        
    overall = "ok" if all(v == "ok" for v in statuses.values()) else "degraded"
    return {"status": overall, "services": statuses}
