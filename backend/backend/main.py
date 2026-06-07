import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.db.mysql import get_db
from backend.config import settings

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MemMesh starting up...")
    yield
    logger.info("MemMesh shutting down...")

app = FastAPI(title="MemMesh API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    statuses = {}
    try:
        db.execute(text("SELECT 1"))
        statuses["mysql"] = "ok"
    except Exception as e:
        logger.error(f"MySQL health check failed: {e}")
        statuses["mysql"] = "error"
    # For Task 2, we just check mysql; we will add other checks in Task 18.
    return {"status": "ok" if all(v == "ok" for v in statuses.values()) else "degraded", "services": statuses}
