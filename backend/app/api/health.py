"""Health check endpoint."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return the health status of the application."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
    }
