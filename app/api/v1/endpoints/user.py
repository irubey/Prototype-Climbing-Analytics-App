from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    get_current_active_user,
    get_current_premium_user,
    get_current_admin,
    AuthenticationError
)
from app.core.logging import logger
from app.db.session import get_db
from app.models import User
from app.schemas.user import (
    UserProfile,
    UserProfileUpdate,
    ClimberSummaryCreate,
    ClimberSummaryUpdate,
    ClimberSummaryResponse
)
from app.services.logbook.orchestrator import LogbookOrchestrator

router = APIRouter(tags=["users"])

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get current user's profile information.
    
    - Returns user profile data
    - Includes climber summary if available
    - Requires valid access token
    """
    try:
        return current_user
    except AuthenticationError as e:
        logger.error(f"Authentication error in get_current_user_profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    profile_in: UserProfileUpdate,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Update current user's profile.
    
    - Updates basic profile information
    - Handles Mountain Project URL changes
    - Triggers background data sync if MP URL changes
    - Requires valid access token
    """
    try:
        # Check if email is being changed and is unique
        if profile_in.email and profile_in.email != current_user.email:
            existing_user = await db.scalar(
                select(User).filter(User.email == profile_in.email)
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Check if Mountain Project URL changed
        mp_url_changed = (
            profile_in.mountain_project_url and 
            profile_in.mountain_project_url != current_user.mountain_project_url
        )
        
        for field, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(current_user, field, value)
        
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        # Process Mountain Project data if URL changed
        if mp_url_changed:
            background_tasks.add_task(
                LogbookOrchestrator.process_mountain_project_data,
                current_user.id,
                profile_in.mountain_project_url
            )
        
        return current_user
    except Exception as e:
        await db.rollback()
        logger.error(f"Database error in update_user_profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update profile"
        )
    except AuthenticationError as e:
        logger.error(f"Authentication error in update_user_profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
) -> Any:
    """
    Get user profile by ID (admin only).
    
    - Returns user profile data
    - Requires admin privileges
    - Requires valid access token with admin scope
    """
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except AuthenticationError as e:
        logger.error(f"Authentication error in get_user_profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

@router.delete("/me")
async def delete_user_account(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Delete current user's account.
    
    - Removes user data
    - Cancels active subscriptions
    - Deletes associated records
    - Requires valid access token
    """
    try:
        try:
            # Cancel subscription if active
            if current_user.stripe_subscription_id:
                # TODO: Implement subscription cancellation
                pass
            
            # Delete user and related data
            await db.delete(current_user)
            await db.commit()
            
            return {"status": "success", "message": "Account deleted successfully"}
        
        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting user account: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not delete account"
            )
    except AuthenticationError as e:
        logger.error(f"Authentication error in delete_user_account: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        ) 