"""
Authentication endpoints for Send Sage application.

This module provides endpoints for:
- User authentication and token issuance
- Token refresh and revocation
- Token introspection and validation
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import asyncio

from app.core import (
    settings,
)
from app.core.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_redis,
    get_current_user,
    get_password_hash,
    create_user,
    authenticate_user,
)
from app.core.email import (
    send_password_reset_email,
)
from app.core.logging import logger
from app.core.exceptions import AuthenticationError, ValidationError
from app.db.session import get_db
from app.models import User
from app.models.auth import RevokedToken
from app.schemas.auth import (
    Token,
    TokenData,
    TokenRefreshRequest,
    TokenRevokeRequest,
    TokenIntrospectRequest,
    TokenIntrospectResponse,
    UserCreate,
    UserResponse,
    PasswordReset,
    PasswordUpdate,
)
from app.services.logbook.orchestrator import LogbookOrchestrator
from jose import jwt, JWTError
from app.models.user import UserTier


router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
) -> User:
    """Register a new user."""
    # Check if user exists
    existing_user = await db.scalar(
        select(User).where(
            or_(User.email == user_in.email, User.username == user_in.username)
        )
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create user
    user = await create_user(db, user_in)
    
    # Process Mountain Project data if URL provided
    if user_in.mountain_project_url:
        try:
            orchestrator = await LogbookOrchestrator.create()
            await orchestrator.process_mountain_project_ticks(
                user_id=user.id,
                profile_url=user_in.mountain_project_url
            )
            await orchestrator.cleanup()
        except Exception as e:
            logger.error(f"Error processing Mountain Project data: {e}")
            # Continue registration even if MP processing fails
    
    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Implements rate limiting and refresh token rotation.
    Also handles account reactivation for deactivated accounts.
    """
    # Rate limiting check
    ip_address = form_data.client_id or "127.0.0.1"  # Use client_id if available
    failed_attempts = await redis_client.incr(f"failed_logins:{ip_address}")
    await redis_client.expire(f"failed_logins:{ip_address}", 60)  # Reset after 1 minute

    if failed_attempts > 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts",
            headers={"Retry-After": "60"}
        )

    # First check if user exists and credentials are valid, regardless of active status
    result = await db.execute(
        select(User).filter(
            or_(User.email == form_data.username, User.username == form_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(
            "Failed login attempt",
            extra={
                "email": form_data.username,
                "ip_address": ip_address,
                "failed_attempts": failed_attempts
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # If user exists but is inactive, reactivate the account
    if not user.is_active:
        user.is_active = True
        user.tier = UserTier.FREE
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Reactivated account for user {user.id}")

    # Reset failed attempts on successful login
    await redis_client.delete(f"failed_logins:{ip_address}")

    # Determine user scopes based on subscription status
    scopes = ["user"]
    if user.tier == "basic":
        scopes.append("basic_user")
    elif user.tier == "premium":
        scopes.append("premium_user")
    if user.is_superuser:
        scopes.append("admin")

    # Generate tokens with unique JTIs
    access_jti = str(uuid4())
    refresh_jti = str(uuid4())

    access_token = await create_access_token(
        subject=str(user.id),
        scopes=scopes,
        jti=access_jti,
        db=db
    )

    refresh_token = await create_refresh_token(
        subject=str(user.id),
        scopes=scopes,
        jti=refresh_jti,
        db=db
    )

    # Set refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,  # 30 days
        path="/api/v1/auth/refresh-token"
    )

    # Update user's last login
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=60 * 60 * 24 * 8,  # 8 days
        refresh_token=refresh_token
    )

@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using a valid refresh token from HttpOnly cookie.
    Implements refresh token rotation with single-use tokens.
    """
    # Extract refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Verify refresh token and get token data
        token_data = await verify_token(
            token=refresh_token,
            db=db,
            expected_type="refresh"
        )

        # Revoke used refresh token immediately to prevent reuse
        revoked_token = RevokedToken(
            jti=token_data.jti,
            revoked_at=datetime.now(timezone.utc)
        )
        db.add(revoked_token)
        await db.commit()

        # Generate new tokens with new JTIs
        access_jti = str(uuid4())
        refresh_jti = str(uuid4())

        new_access_token = await create_access_token(
            subject=token_data.user_id,
            scopes=token_data.scopes,
            jti=access_jti,
            db=db
        )

        new_refresh_token = await create_refresh_token(
            subject=token_data.user_id,
            scopes=token_data.scopes,
            jti=refresh_jti,
            db=db
        )

        # Set new refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/api/v1/auth/refresh-token"
        )

        return Token(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=60 * 60 * 24 * 8,  # 8 days
            refresh_token=new_refresh_token
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not refresh token"
        )

@router.post("/revoke")
async def revoke_token(
    request: TokenRevokeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke an access or refresh token.
    The token will be added to the revoked tokens list.
    """
    try:
        # Verify token without checking type
        token_data = await verify_token(
            request.token,
            db,
            expected_type=request.token_type_hint or "access"
        )

        # Add token to revoked list
        db.add(RevokedToken(jti=token_data.jti))
        await db.commit()

        return {"message": "Token revoked successfully"}

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post("/introspect", response_model=TokenIntrospectResponse)
async def introspect_token(
    request: TokenIntrospectRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 token introspection endpoint.
    Returns information about the token's validity and claims.
    """
    try:
        # Verify token without checking type
        token_data = await verify_token(
            request.token,
            db,
            expected_type=request.token_type_hint or "access"
        )

        # Get user information
        user = await db.get(User, token_data.user_id)
        if not user:
            raise AuthenticationError(detail="User not found")

        return TokenIntrospectResponse(
            active=True,
            scope=" ".join(token_data.scopes),
            username=user.email,
            token_type=token_data.type,
            sub=str(token_data.user_id),
            jti=token_data.jti
        )

    except AuthenticationError:
        # Return inactive token response instead of error
        return TokenIntrospectResponse(active=False)

@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Logout the current user. Revokes access and refresh tokens, clears cookies.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
            token_data = await verify_token(access_token, db)
            db.add(RevokedToken(jti=token_data.jti))

        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            token_data = await verify_token(refresh_token, db, expected_type="refresh")
            db.add(RevokedToken(jti=token_data.jti))

        await db.commit()

        response.delete_cookie(
            key="refresh_token",
            path="/api/v1/auth/refresh-token",
            secure=True,
            httponly=True,
            samesite="strict"
        )

        return {"message": "Successfully logged out"}

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    email_in: PasswordReset,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Request a password reset token.
    
    - Generates reset token if user exists
    - Sends reset email in background
    - Returns 202 regardless of email existence for security
    """
    user = await db.scalar(
        select(User).filter(User.email == email_in.email)
    )

    if user:
        token = await create_access_token(
            subject=str(user.id),
            scopes=["password-reset"],
            expires_delta=timedelta(hours=1),
            jti=str(uuid4()),
            db=db
        )
        background_tasks.add_task(
            send_password_reset_email,
            email_to=user.email,
            token=token,
            username=user.username
        )

    return {"message": "If the email exists, a password reset link will be sent"}

@router.post("/reset-password")
async def reset_password(
    *,
    db: AsyncSession = Depends(get_db),
    password_update: PasswordUpdate
) -> Any:
    """
    Reset password using reset token.
    
    - Validates reset token
    - Updates password if token valid
    - Invalidates all existing sessions
    """
    try:
        # Verify token and get user
        try:
            token_data = await verify_token(
                token=password_update.token,
                db=db,
                expected_type="access"
            )
        except (JWTError, AuthenticationError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )
        
        if "password-reset" not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )
        
        result = await db.execute(
            select(User).filter(User.id == token_data.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password - ensure we get the secret value from the SecretStr field
        user.hashed_password = get_password_hash(password_update.new_password.get_secret_value())
        
        # Revoke the used token
        revoked_token = RevokedToken(jti=token_data.jti)
        db.add(revoked_token)
        
        # Save both the password update and token revocation
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reset password"
        )

@router.post("/test_test")
async def test_test(
    db: AsyncSession = Depends(get_db)
):
    """
    Test endpoint to check test client.
    """
    return {"message": "Test client is working"}


