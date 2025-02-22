"""Health check endpoints for monitoring application status."""
from typing import Dict
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.session import get_db
from app.core.logging import logger

router = APIRouter()

@router.get("/", response_model=Dict[str, str])
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy"}

@router.get("/db", response_model=Dict[str, str])
async def db_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Check database connection health."""
    try:
        # Try to execute a simple query
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(
            "Database health check failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        return {"status": "unhealthy", "database": "disconnected"} 