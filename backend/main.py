import sys
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.db.mysql import get_db, SessionLocal
from backend.config import settings
from backend.models import User
from backend.auth.passwords import hash_password
from backend.api.routes.auth import router as auth_router
from backend.api.routes.admin import router as admin_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MemMesh starting up...")
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
    logger.info("MemMesh shutting down...")

app = FastAPI(title="MemMesh API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)

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
