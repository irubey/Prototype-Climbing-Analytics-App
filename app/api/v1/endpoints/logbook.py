from typing import Dict, Any
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from datetime import datetime
from uuid import UUID
from sqlalchemy import select

from app.core.auth import (
    get_current_user,
    encrypt_credential,
    decrypt_credential
)
from app.core.error_handlers import (
    get_error_responses,
)
from app.core.exceptions import (
    LogbookConnectionError
)
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.db.session import get_db
from app.models import User
from app.schemas.logbook_connection import LogbookConnectPayload
from app.services.logbook.orchestrator import LogbookOrchestrator
from app.models.enums import LogbookType
from app.db.session import DatabaseSessionManager
from app.services.chat.context.orchestrator import ContextOrchestrator
from app.services.logbook.recalculation_service import RecalculationService
from app.schemas.data import RefreshStatus

router = APIRouter()

@router.post("/connect", response_model=Dict[str, str], responses=get_error_responses("logbook_connect"))
async def connect_logbook(
    payload: LogbookConnectPayload,
    background_tasks: BackgroundTasks,
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    async def run_sync():
        async with DatabaseSessionManager.get_instance().session() as db:
            orchestrator = LogbookOrchestrator(db)
            context_orchestrator = ContextOrchestrator(db, redis_client)
            try:
                # Clean up existing data for this logbook type
                await orchestrator.db_service.cleanup_logbook_data(
                    user_id=current_user.id,
                    logbook_type=payload.source
                )

                if payload.source == LogbookType.MOUNTAIN_PROJECT:
                    await orchestrator.process_mountain_project_ticks(
                        user_id=current_user.id,
                        profile_url=payload.profile_url
                    )
                else:  # eight_a_nu
                    # Encrypt credentials before saving
                    encrypted_username = await encrypt_credential(payload.username)
                    encrypted_password = await encrypt_credential(payload.password)
                    
                    # Update user with encrypted credentials
                    current_user.eight_a_nu_encrypted_username = encrypted_username
                    current_user.eight_a_nu_encrypted_password = encrypted_password
                    await db.commit()
                    
                    await orchestrator.process_eight_a_nu_ticks(
                        user_id=current_user.id,
                        username=payload.username,
                        password=payload.password
                    )
                await db.commit()
                await context_orchestrator.refresh_context(
                    user_id=current_user.id
                )
            except Exception as e:
                await db.rollback()
                logger.error("Background sync failed", extra={"user_id": str(current_user.id), "error": str(e)})
                raise LogbookConnectionError(str(e))

    background_tasks.add_task(run_sync)
    return {"status": "Processing initiated successfully"}

@router.post("/refresh", response_model=RefreshStatus)
async def refresh_logbook(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger a refresh of the user's logbook data."""
    # Check if a refresh is already in progress
    if current_user.refresh_status == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A refresh is already in progress"
        )

    # Update user's refresh status
    current_user.refresh_status = "in_progress"
    current_user.refresh_started_at = datetime.utcnow()
    await db.commit()

    # Start background task
    background_tasks.add_task(
        process_logbook_refresh,
        current_user.id,
        db
    )

    return RefreshStatus(
        status="in_progress",
        message="Logbook refresh started",
        last_sync=current_user.last_sync
    )

async def process_logbook_refresh(user_id: UUID, db: AsyncSession):
    """Process the logbook refresh in the background."""
    try:
        # Initialize services
        orchestrator = LogbookOrchestrator(db)
        recalculation_service = RecalculationService(db)

        # Process logbook data
        success, errors = await orchestrator.process_logbook_data(user_id)
        if not success:
            raise Exception(f"Error processing logbook data: {errors}")

        # Recalculate fields and rebuild pyramids
        success, recalculation_errors = await recalculation_service.recalculate_fields_and_pyramids(user_id)
        if not success:
            raise Exception(f"Error recalculating fields: {recalculation_errors}")

        # Update user's refresh status
        user = await db.execute(
            select(User).filter(User.id == user_id)
        )
        user = user.scalar_one_or_none()
        if user:
            user.refresh_status = "completed"
            user.last_sync = datetime.utcnow()
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing logbook refresh: {str(e)}")
        # Update user's refresh status
        user = await db.execute(
            select(User).filter(User.id == user_id)
        )
        user = user.scalar_one_or_none()
        if user:
            user.refresh_status = "failed"
            user.refresh_error = str(e)
            await db.commit()

