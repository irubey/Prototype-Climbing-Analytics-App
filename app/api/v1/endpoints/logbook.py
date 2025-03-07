from typing import Dict, Any
from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    get_current_user,
)
from app.core.error_handlers import (
    get_error_responses,
)
from app.core.exceptions import (
    LogbookConnectionError
)
from app.core.logging import logger
from app.db.session import get_db
from app.models import User
from app.schemas.logbook_connection import LogbookConnectPayload, IngestionType
from app.services.logbook.orchestrator import LogbookOrchestrator
from app.models.enums import LogbookType

router = APIRouter()

@router.post(
    "/connect",
    response_model=Dict[str, str],
    responses=get_error_responses("logbook_connect")
)
async def connect_logbook( 
    payload: LogbookConnectPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Initiate asynchronous logbook ingestion and processing.
    
    Args:
        payload: Validated connection payload containing source and credentials
        background_tasks: FastAPI background tasks handler
        db: Async database session
        current_user: Authenticated user from dependency
        
    Returns:
        Dict containing status message
        
    Raises:
        LogbookConnectionError: If connection to logbook service fails
    """
    logger.info(
        "Initiating logbook connection",
        extra={
            "user_id": str(current_user.id),
            "source": payload.source,
            "has_profile_url": bool(payload.profile_url),
            "has_credentials": bool(payload.username and payload.password)
        }
    )
    
    try:
        # Initialize orchestrator
        orchestrator = LogbookOrchestrator(db)
        
        # Configure processing based on source
        if payload.source == IngestionType.MOUNTAIN_PROJECT:
            background_tasks.add_task(
                orchestrator.process_mountain_project_ticks,
                user_id=current_user.id,
                profile_url=payload.profile_url
            )
            logger.debug(
                "Scheduled Mountain Project processing",
                extra={
                    "user_id": str(current_user.id),
                    "profile_url": payload.profile_url
                }
            )
        else:  # eight_a_nu
            background_tasks.add_task(
                orchestrator.process_eight_a_nu_ticks,
                user_id=current_user.id,
                username=payload.username,
                password=payload.password
            )
            logger.debug(
                "Scheduled 8a.nu processing",
                extra={
                    "user_id": str(current_user.id),
                    "username": payload.username
                }
            )
        
        return {
            "status": "Processing initiated successfully"
        }
        
    except Exception as e:
        logger.error(
            "Failed to initiate logbook processing",
            extra={
                "user_id": str(current_user.id),
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise LogbookConnectionError(str(e))
