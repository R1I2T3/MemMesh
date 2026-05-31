# backend/api/routes/health.py
"""Public health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Return basic health status. No auth required."""
    return {"status": "ok"}
