from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

from app.core.auth import (
    get_current_user,
)
from app.core.error_handlers import (
    get_error_responses,
)
from app.core.exceptions import (
    ValidationError,
    ResourceNotFound
)
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.db.session import get_db
from app.models import User, UserTicks, ClimberContext
from app.models.enums import ClimbingDiscipline
from app.schemas.context import ContextResponse, ContextUpdatePayload, ContextQueryParams
from app.services.chat.context.orchestrator import ContextOrchestrator

router = APIRouter()

def _resolve_user_id(user_id: str, current_user: User) -> str:
    """Helper to resolve 'me' to current user ID."""
    return str(current_user.id) if user_id.lower() == 'me' else user_id

@router.get(
    "/{user_id}",
    response_model=ContextResponse,
    responses=get_error_responses("get_context")
)
async def get_context(
    user_id: str,
    query_params: ContextQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieve context for a user with optional query parameters.
    
    Args:
        user_id: Target user ID
        query_params: Optional query parameters for context customization
        db: Async database session
        redis_client: Redis client dependency
        current_user: Authenticated user from dependency
        
    Returns:
        Dict containing context data
        
    Raises:
        ResourceNotFound: If user context doesn't exist
        ValidationError: If query parameters are invalid
    """
    target_user_id = _resolve_user_id(user_id, current_user)
    
    logger.info(
        "Retrieving user context",
        extra={
            "user_id": target_user_id,
            "current_user_id": str(current_user.id),
            "query": query_params.model_dump()
        }
    )
    
    orchestrator = ContextOrchestrator(db, redis_client)
    context = await orchestrator.get_context(
        user_id=target_user_id,
        query=query_params.query,
        force_refresh=query_params.force_refresh
    )

    # Log the response data
    logger.info("Context endpoint response", extra={
        "response_data": {
            "context_version": context.get("context_version"),
            "summary": context.get("summary"),
            "profile_summary": {
                "years_climbing": context.get("profile", {}).get("years_climbing"),
                "total_climbs": context.get("profile", {}).get("total_climbs"),
                "favorite_discipline": context.get("profile", {}).get("favorite_discipline")
            },
            "performance_summary": {
                "highest_grades": {
                    "sport": context.get("performance", {}).get("highest_sport_grade"),
                    "boulder": context.get("performance", {}).get("highest_boulder_grade"),
                    "trad": context.get("performance", {}).get("highest_trad_grade")
                },
                "recent_sends": len(context.get("performance", {}).get("recent_sends", [])),
                "projects": len(context.get("performance", {}).get("current_projects", []))
            },
            "trends_summary": context.get("trends"),
            "goals_summary": context.get("goals"),
            "has_uploads": bool(context.get("uploads")),
            "is_new_user": context.get("is_new_user", False)
        }
    })

    return context

@router.post(
    "/{user_id}/refresh",
    response_model=Dict[str, str],
    responses=get_error_responses("refresh_context")
)
async def refresh_context(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Initiate asynchronous context refresh.
    
    Args:
        user_id: Target user ID
        background_tasks: FastAPI background tasks handler
        db: Async database session
        redis_client: Redis client dependency
        current_user: Authenticated user from dependency
        
    Returns:
        Dict containing status message
    """
    target_user_id = _resolve_user_id(user_id, current_user)
    
    logger.info(
        "Initiating context refresh",
        extra={
            "user_id": target_user_id,
            "current_user_id": str(current_user.id)
        }
    )
    
    orchestrator = ContextOrchestrator(db, redis_client)
    background_tasks.add_task(
        orchestrator.refresh_context,
        user_id=target_user_id
    )
    
    return {
        "status": "Context refresh initiated successfully"
    }

@router.post(
    "/{user_id}/update",
    response_model=Dict[str, Any],
    responses=get_error_responses("update_context")
)
async def update_context(
    user_id: str,
    payload: ContextUpdatePayload,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    target_user_id = _resolve_user_id(user_id, current_user)
    logger.info("Updating user context", extra={"user_id": target_user_id, "update_sections": list(payload.updates.keys())})

    # Update SQL
    stmt = select(ClimberContext).where(ClimberContext.user_id == target_user_id)
    result = await db.execute(stmt)
    context = result.scalar_one_or_none()
    if not context:
        context = ClimberContext(user_id=target_user_id)
        db.add(context)
    for key, value in payload.updates.items():
        if payload.replace or value is not None:
            setattr(context, key, value)
    await db.commit()

    # Refresh context in cache
    orchestrator = ContextOrchestrator(db, redis_client)
    updated_context = await orchestrator.handle_data_update(
        user_id=target_user_id,
        update_type="climber_context",
        update_data=payload.updates,
        replace=payload.replace
    )
    if not updated_context:
        raise ResourceNotFound(f"Context not found for user {target_user_id}")
    return updated_context

@router.post(
    "/bulk-refresh",
    response_model=Dict[str, str],
    responses=get_error_responses("bulk_refresh_contexts")
)
async def bulk_refresh_contexts(
    background_tasks: BackgroundTasks,
    user_ids: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Initiate bulk context refresh for multiple users.
    
    Args:
        background_tasks: FastAPI background tasks handler
        user_ids: Optional list of user IDs to refresh
        db: Async database session
        redis_client: Redis client dependency
        current_user: Authenticated user from dependency
        
    Returns:
        Dict containing status message
    """
    # Handle potential 'me' in the user_ids list
    target_user_ids = [_resolve_user_id(uid, current_user) for uid in user_ids] if user_ids else None
    
    logger.info(
        "Initiating bulk context refresh",
        extra={
            "current_user_id": str(current_user.id),
            "target_user_count": len(target_user_ids) if target_user_ids else "all"
        }
    )
    
    orchestrator = ContextOrchestrator(db, redis_client)
    background_tasks.add_task(
        orchestrator.bulk_refresh_contexts,
        user_ids=target_user_ids
    )
    
    return {
        "status": "Bulk context refresh initiated successfully"
    } 