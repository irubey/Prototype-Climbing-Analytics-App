from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from datetime import datetime

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
from app.models import User
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
    
    if not context:
        # Return default context for new users
        logger.info(
            "No context found, returning default context",
            extra={"user_id": target_user_id}
        )
        return {
            "context_version": "1.0",
            "summary": "New climber with no recorded history yet. Ready to start tracking your climbing journey!",
            "profile": {
                "user_id": target_user_id,
                "created_at": datetime.utcnow().isoformat(),
                "years_climbing": 0,
                "preferred_styles": [],
                "current_grade": None,
                "goal_grade": None,
                "training_frequency": "unknown",
                "injury_status": None
            },
            "performance": {
                "highest_boulder_grade": None,
                "highest_route_grade": None,
                "total_climbs": 0,
                "recent_activity": 0
            },
            "trends": {
                "grade_progression": {
                    "all_time": 0.0,
                    "recent": 0.0
                },
                "training_consistency": 0.0,
                "activity_levels": {
                    "weekly": 0,
                    "monthly": 0
                }
            },
            "relevance": {
                "training": 0.0,
                "performance": 0.0,
                "technique": 0.0,
                "goals": 0.0,
                "health": 0.0
            },
            "goals": {
                "current_goals": [],
                "progress": {}
            },
            "uploads": [],
            "is_new_user": True  # Flag to help frontend show onboarding
        }
        
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

@router.patch(
    "/{user_id}",
    response_model=ContextResponse,
    responses=get_error_responses("update_context")
)
async def update_context(
    user_id: str,
    payload: ContextUpdatePayload,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update specific sections of a user's context.
    
    Args:
        user_id: Target user ID
        payload: Context update data
        db: Async database session
        redis_client: Redis client dependency
        current_user: Authenticated user from dependency
        
    Returns:
        Dict containing updated context
        
    Raises:
        ResourceNotFound: If user context doesn't exist
        ValidationError: If update payload is invalid
    """
    target_user_id = _resolve_user_id(user_id, current_user)
    
    logger.info(
        "Updating user context",
        extra={
            "user_id": target_user_id,
            "current_user_id": str(current_user.id),
            "update_sections": list(payload.updates.keys())
        }
    )
    
    orchestrator = ContextOrchestrator(db, redis_client)
    updated_context = await orchestrator.handle_data_update(
        user_id=target_user_id,
        updates=payload.updates,
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