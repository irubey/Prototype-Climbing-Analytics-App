from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import stripe
import re
import time
from datetime import timedelta, datetime, timezone
from uuid import UUID
from pydantic import BaseModel

from app.core.auth import (
    get_current_active_user,
    get_current_premium_user,
    get_current_admin,
    AuthenticationError,
    verify_password,
    get_password_hash,
    get_redis,
    verify_token,
    TokenData,
    get_token_from_header
)
from app.core.logging import logger
from app.core.exceptions import DatabaseError, ValidationError, StripeError
from app.db.session import get_db
from app.models import User, RevokedToken
from app.schemas.user import (
    UserProfile,
    UserProfileUpdate,
    ClimberSummaryCreate,
    ClimberSummaryUpdate,
    ClimberSummaryResponse
)
from app.services.logbook.orchestrator import LogbookOrchestrator
from app.core.email import send_password_change_email
from app.models.enums import UserTier, PaymentStatus, LogbookType
import redis.asyncio as redis
from app.core.config import settings


router = APIRouter(tags=["users"])

class SubscriptionRequest(BaseModel):
    desired_tier: UserTier

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    redis_client: redis.Redis = Depends(get_redis)
) -> Any:
    """
    Get current user's profile information.
    
    - Returns user profile data from cache if available
    - Includes climber summary if available
    - Requires valid access token
    - Caches result for 5 minutes
    """
    start_time = time.time()
    try:
        # Try to get from cache first
        cache_key = f"user_profile:{current_user.id}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            profile = UserProfile.model_validate_json(cached)
            logger.info("Profile retrieved from cache", extra={"user_id": str(current_user.id)})
            return profile
        
        # Convert to Pydantic model for consistent serialization
        profile = UserProfile.model_validate(current_user)
        
        # Cache for 5 minutes
        await redis_client.setex(
            cache_key,
            300,  # 5 minutes TTL
            profile.model_dump_json()
        )
        
        logger.info("Profile cached", extra={"user_id": str(current_user.id)})
        return profile
        
    except AuthenticationError as e:
        logger.error(f"Authentication error in get_current_user_profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        # Return uncached profile on error
        return UserProfile.model_validate(current_user)
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path,
                "cached": bool(cached)
            }
        )

@router.patch("/me", response_model=UserProfile)
async def update_user_profile(
    request: Request,
    *,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
    profile_in: UserProfileUpdate,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Update current user's profile.
    
    - Updates basic profile information
    - Handles Mountain Project URL changes
    - Handles 8a.nu URL changes
    - Triggers background data sync if URLs change
    - Invalidates profile cache
    - Requires valid access token
    """
    start_time = time.time()
    try:
        # Check if email is being changed and is unique
        if profile_in.email and profile_in.email != current_user.email:
            existing_user = await db.scalar(
                select(User).filter(User.email == profile_in.email)
            )
            if existing_user:
                raise ValidationError("Email already registered")
        
        # Check if Mountain Project URL changed
        mp_url_changed = (
            profile_in.mountain_project_url and 
            profile_in.mountain_project_url != current_user.mountain_project_url
        )
        
        # Check if 8a.nu URL changed
        eight_a_url_changed = (
            profile_in.eight_a_nu_url and 
            profile_in.eight_a_nu_url != current_user.eight_a_nu_url
        )
        
        # If updating username, first check if it already exists
        if profile_in.username and profile_in.username != current_user.username:
            # Check if username exists
            existing_user = await db.execute(
                select(User).where(User.username == profile_in.username)
            )
            if existing_user.scalars().first():
                raise ValidationError(
                    detail="Username already taken",
                    errors={"username": "This username is already in use"}
                )
        
        # Continue with update
        for field, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(current_user, field, value)
        
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        # Invalidate cache
        await invalidate_user_cache(redis_client, str(current_user.id))
        
        # Process Mountain Project data if URL changed
        if mp_url_changed:
            orchestrator = LogbookOrchestrator(db)
            background_tasks.add_task(
                orchestrator.process_logbook_data,
                current_user.id,
                LogbookType.MOUNTAIN_PROJECT,
                profile_url=profile_in.mountain_project_url
            )
            
        # Process 8a.nu data if URL changed
        if eight_a_url_changed:
            orchestrator = LogbookOrchestrator(db)
            background_tasks.add_task(
                orchestrator.process_logbook_data,
                current_user.id,
                LogbookType.EIGHT_A_NU,
                profile_url=profile_in.eight_a_nu_url
            )
        
        return current_user
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DatabaseError as e:
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
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update profile"
        )
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path
            }
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
        # Validate UUID format
        try:
            uuid_obj = UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid UUID format"
            )
            
        user = await db.get(User, uuid_obj)
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

@router.post("/me/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    *,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
    old_password: str,
    new_password: str,
    confirmation: str,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Change user's password securely.
    
    - Validates old password
    - Checks password complexity
    - Revokes existing tokens
    - Sends email notification
    - Rate limited to 5 attempts per minute
    """
    try:
        # Rate limiting check
        rate_key = f"password_change:{current_user.id}"
        attempts = await redis_client.incr(rate_key)
        if attempts == 1:
            await redis_client.expire(rate_key, 60)  # Reset after 1 minute
        
        if attempts > 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait 60 seconds.",
                headers={"Retry-After": "60"}
            )

        # Verify old password
        if not verify_password(old_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect password"
            )
            
        # Validate new password
        if new_password != confirmation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords don't match"
            )
        
        # Check password complexity
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        if not re.search(r"[A-Z]", new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one uppercase letter"
            )
        if not re.search(r"[a-z]", new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one lowercase letter"
            )
        if not re.search(r"\d", new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one number"
            )
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain at least one special character"
            )
            
        # Update password
        current_user.hashed_password = get_password_hash(new_password)
        
        # Create token revocation record
        revoked_token = RevokedToken(
            user_id=current_user.id,
            revoked_at=func.now()
        )
        db.add(revoked_token)
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        # Send email notification
        background_tasks.add_task(
            send_password_change_email,
            email_to=current_user.email,
            username=current_user.username
        )
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error changing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not change password"
        )

@router.get("/me/message-count")
async def get_message_count(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get user's message count and limits.
    
    - Returns daily message count
    - Shows tier-specific limits
    - Calculates remaining messages
    - Uses rolling 24-hour window
    """
    start_time = time.time()
    try:
        # Check if we need to reset the counter (24 hours passed)
        now = datetime.now(timezone.utc)
        if (current_user.last_message_date and 
            (now - current_user.last_message_date) > timedelta(hours=24)):
            current_user.daily_message_count = 0
            current_user.last_message_date = now
            db.add(current_user)
            await db.commit()
        
        # Get tier-specific message limit
        tier_permissions = UserTier.get_permissions()[current_user.tier]
        max_daily_messages = tier_permissions["daily_messages"]
        
        # Calculate remaining messages
        remaining_messages = (
            max_daily_messages - current_user.daily_message_count
            if max_daily_messages != float('inf')
            else None
        )
        
        return {
            "daily_message_count": current_user.daily_message_count,
            "last_message_date": current_user.last_message_date,
            "max_daily_messages": max_daily_messages,
            "remaining_messages": remaining_messages,
            "reset_time": (
                current_user.last_message_date + timedelta(hours=24)
                if current_user.last_message_date
                else None
            )
        }
        
    except Exception as e:
        logger.error(f"Error getting message count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not get message count"
        )
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path
            }
        )

@router.post("/me/deactivate")
async def deactivate_account(
    request: Request,
    *,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_active_user),
    token: str = Depends(get_token_from_header)
) -> Any:
    """
    Deactivate user's account (soft delete).
    
    - Sets account as inactive
    - Cancels active subscriptions
    - Revokes active tokens
    - Invalidates profile cache
    - Preserves data for reactivation via login
    """
    start_time = time.time()
    try:
        # Cancel subscription if active
        if current_user.stripe_subscription_id:
            try:
                # Cancel subscription in Stripe
                stripe.Subscription.delete(current_user.stripe_subscription_id)
                
                # Update subscription data
                current_user.stripe_subscription_id = None
                current_user.payment_status = PaymentStatus.CANCELLED
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error during deactivation: {e}")
                raise StripeError("Could not cancel subscription")
        
        # Soft delete and revoke tokens
        current_user.is_active = False
        current_user.tier = UserTier.FREE
        
        # Create token revocation record
        token_data = await verify_token(token, db)
        revoked_token = RevokedToken(jti=token_data.jti)
        db.add(revoked_token)
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        
        # Invalidate cache
        await invalidate_user_cache(redis_client, str(current_user.id))
        
        return {"message": "Account deactivated successfully"}
        
    except StripeError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deactivating account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not deactivate account"
        )
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path
            }
        )

@router.get("/me/subscription")
async def get_subscription(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Retrieve subscription details with Stripe sync.
    
    - Returns current tier and status
    - Syncs with Stripe for latest data
    - Shows renewal and billing dates
    """
    start_time = time.time()
    try:
        # Fetch real-time Stripe data if subscription exists
        if current_user.stripe_subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(
                    current_user.stripe_subscription_id
                )
                
                # Update local subscription data if needed
                if subscription.status == "active" and current_user.payment_status != PaymentStatus.ACTIVE:
                    current_user.payment_status = PaymentStatus.ACTIVE
                    db.add(current_user)
                    await db.commit()
                elif subscription.status != "active" and current_user.payment_status == PaymentStatus.ACTIVE:
                    current_user.payment_status = PaymentStatus.INACTIVE
                    current_user.tier = UserTier.FREE
                    db.add(current_user)
                    await db.commit()
                
                return {
                    "tier": current_user.tier,
                    "payment_status": current_user.payment_status,
                    "stripe_subscription_id": current_user.stripe_subscription_id,
                    "renewal_date": datetime.fromtimestamp(subscription.current_period_end, timezone.utc),
                    "next_billing_date": datetime.fromtimestamp(subscription.current_period_end, timezone.utc)
                }
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error in get_subscription: {e}")
                raise StripeError("Could not fetch subscription details")
        
        # Return basic info if no subscription
        return {
            "tier": current_user.tier,
            "payment_status": current_user.payment_status,
            "stripe_subscription_id": None,
            "renewal_date": None,
            "next_billing_date": None
        }
        
    except StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not get subscription details"
        )
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path
            }
        )

@router.post("/me/subscribe")
async def create_subscription(
    request: Request,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    subscription_request: SubscriptionRequest,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Initiate a new subscription.
    
    - Creates Stripe checkout session
    - Updates user tier immediately (pending webhook confirmation)
    - Handles existing subscription
    - Webhook will finalize or revert tier change
    """
    start_time = time.time()
    try:
        # Check if user already has an active subscription
        if current_user.stripe_subscription_id and current_user.payment_status == PaymentStatus.ACTIVE:
            raise ValidationError("Active subscription exists")
        
        # Create Stripe checkout session
        try:
            session = stripe.checkout.Session.create(
                customer=current_user.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": settings.STRIPE_PRICE_IDS[subscription_request.desired_tier],
                    "quantity": 1
                }],
                mode="subscription",
                success_url=settings.FRONTEND_URL + "/subscription/success",
                cancel_url=settings.FRONTEND_URL + "/subscription/cancel",
                metadata={
                    "user_id": str(current_user.id),
                    "desired_tier": subscription_request.desired_tier,
                    "previous_tier": current_user.tier
                }
            )
            
            # Update tier immediately (will be confirmed or reverted by webhook)
            current_user.tier = subscription_request.desired_tier
            current_user.payment_status = PaymentStatus.PENDING
            current_user.last_payment_check = datetime.now(timezone.utc)
            
            db.add(current_user)
            await db.commit()
            
            # TODO:Schedule a cleanup task to revert if webhook doesn't confirm
            def check_subscription_confirmation(user_id: str, session_id: str, timeout: int = 3600):
                pass

            def check_subscription_confirmation_task():
                check_subscription_confirmation(
                    user_id=current_user.id,
                    session_id=session.id,
                    timeout=3600  # 1 hour timeout
                )
            background_tasks.add_task(
                check_subscription_confirmation_task,
            )
            
            return {
                "checkout_session_id": session.id,
                "tier": subscription_request.desired_tier,
                "status": "pending_confirmation"
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error in create_subscription: {e}")
            raise StripeError("Could not create subscription")
            
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create subscription"
        )
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path,
                "desired_tier": subscription_request.desired_tier
            }
        )

@router.post("/me/cancel-subscription")
async def cancel_subscription(
    request: Request,
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Cancel active subscription.
    
    - Cancels Stripe subscription
    - Updates user tier to free
    - Sets payment status to cancelled
    """
    start_time = time.time()
    try:
        if not current_user.stripe_subscription_id:
            raise ValidationError("No active subscription")
        
        try:
            # Cancel subscription in Stripe
            stripe.Subscription.delete(current_user.stripe_subscription_id)
            
            # Update user record
            current_user.stripe_subscription_id = None
            current_user.tier = UserTier.FREE
            current_user.payment_status = PaymentStatus.CANCELLED
            
            db.add(current_user)
            await db.commit()
            
            return {"message": "Subscription cancelled successfully"}
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error in cancel_subscription: {e}")
            raise StripeError("Could not cancel subscription")
            
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not cancel subscription"
        )
    finally:
        duration = time.time() - start_time
        logger.info(
            f"Endpoint {request.url.path} completed",
            extra={
                "duration": f"{duration:.3f}s",
                "user_id": str(current_user.id),
                "path": request.url.path
            }
        )

async def invalidate_user_cache(
    redis_client: redis.Redis,
    user_id: str
) -> None:
    """Invalidate user-related cache entries."""
    cache_key = f"user_profile:{user_id}"
    await redis_client.delete(cache_key)
    logger.info("User cache invalidated", extra={"user_id": user_id}) 