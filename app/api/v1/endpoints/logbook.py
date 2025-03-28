from typing import Dict, Any
from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

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
        async with DatabaseSessionManager.get_instance().session() as db:
            orchestrator = LogbookOrchestrator(db)
            try:
                if payload.source == IngestionType.MOUNTAIN_PROJECT:
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
            except Exception as e:
                await db.rollback()
                logger.error("Background sync failed", extra={"user_id": str(current_user.id), "error": str(e)})
                raise LogbookConnectionError(str(e))

    background_tasks.add_task(run_sync)
    return {"status": "Processing initiated successfully"}

@router.post("/refresh", response_model=Dict[str, str], responses=get_error_responses("logbook_refresh"))
async def refresh_logbook(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Refresh user's logbook data from connected sources.
    
    Checks for existing Mountain Project URL and 8a.nu credentials,
    then initiates background sync tasks for each connected source.
    """
    async def run_sync():
        async with DatabaseSessionManager.get_instance().session() as db:
            orchestrator = LogbookOrchestrator(db)
            try:
                if current_user.mountain_project_url:
                    await orchestrator.process_mountain_project_ticks(
                        user_id=current_user.id,
                        profile_url=current_user.mountain_project_url
                    )

                if current_user.eight_a_nu_encrypted_username and current_user.eight_a_nu_encrypted_password:
                    # Decrypt credentials for use
                    decrypted_username = await decrypt_credential(current_user.eight_a_nu_encrypted_username)
                    decrypted_password = await decrypt_credential(current_user.eight_a_nu_encrypted_password)
                    
                    await orchestrator.process_eight_a_nu_ticks(
                        user_id=current_user.id,
                        username=decrypted_username,
                        password=decrypted_password
                    )

                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error("Background refresh failed", extra={
                    "user_id": str(current_user.id),
                    "error": str(e)
                })
                raise LogbookConnectionError(str(e))

    # Check if user has any connected sources
    if not (current_user.mountain_project_url or 
            (current_user.eight_a_nu_encrypted_username and current_user.eight_a_nu_encrypted_password)):
        raise LogbookConnectionError("No logbook sources connected. Please connect a logbook first.")

    background_tasks.add_task(run_sync)
    return {"status": "Refresh initiated successfully"}

