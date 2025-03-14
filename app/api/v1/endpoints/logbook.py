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
from app.db.session import DatabaseSessionManager

router = APIRouter()

@router.post("/connect", response_model=Dict[str, str], responses=get_error_responses("logbook_connect"))
async def connect_logbook(
    payload: LogbookConnectPayload,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    async def run_sync():
        # Create a new session for the background task
        async with DatabaseSessionManager.get_instance().session() as db:
            orchestrator = LogbookOrchestrator(db)
            try:
                if payload.source == IngestionType.MOUNTAIN_PROJECT:
                    await orchestrator.process_mountain_project_ticks(
                        user_id=current_user.id,
                        profile_url=payload.profile_url
                    )
                else:  # eight_a_nu
                    await orchestrator.process_eight_a_nu_ticks(
                        user_id=current_user.id,
                        username=payload.username,
                        password=payload.password
                    )
                await db.commit()  # Explicitly commit the transaction
            except Exception as e:
                await db.rollback()
                logger.error("Background sync failed", extra={"user_id": str(current_user.id), "error": str(e)})
                raise LogbookConnectionError(str(e))

    background_tasks.add_task(run_sync)
    return {"status": "Processing initiated successfully"}