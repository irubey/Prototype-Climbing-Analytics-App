"""
Authentication endpoint tests.

Tests cover:
- User registration and validation
- Token issuance and validation
- Token refresh and rotation
- Token revocation
- Rate limiting
- Key rotation
"""

import pytest
from httpx import AsyncClient
from fastapi import status, HTTPException
from fastapi.security import SecurityScopes
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
import jwt
import asyncio

from app.core.logging import logger

# Core imports
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    generate_key_pair,
    encrypt_private_key,
    decrypt_private_key,
    get_current_user,
    AuthenticationError,
    encode_jwt
)
from app.core.key_rotation import rotate_keys
from app.core.config import settings

# Model imports
from app.models.auth import RevokedToken, KeyHistory
from app.models.user import User

# Schema imports
from app.schemas.auth import (
    Token,
    TokenData,
    TokenRefreshRequest,
    TokenRevokeRequest,
    TokenIntrospectRequest
)

# Database imports
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import sessionmanager
from passlib.context import CryptContext

pytestmark = pytest.mark.asyncio

@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword123!"
    }

async def test_register_user(client: AsyncClient, test_user_data):
    """Test user registration."""
    response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]
    assert "id" in data
    assert "is_active" in data
    assert data["is_active"] is True

async def test_register_existing_email(client: AsyncClient, test_user_data):
    """Test registering with an existing email."""
    # First registration (should succeed)
    response1 = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response1.status_code == status.HTTP_201_CREATED

    # Second registration with the same email (should fail)
    response2 = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response2.json()
    assert "Email or username already registered" in response2.json()["detail"]

async def test_login_success(client: AsyncClient, test_user_data):
    """Test successful login and token issuance."""
    # Register a user
    register_response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert register_response.status_code == status.HTTP_201_CREATED

    # Login - Use the CORRECT email
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],  # Use email here
            "password": test_user_data["password"],
        }
    )
    assert login_response.status_code == status.HTTP_200_OK
    data = login_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Check for refresh token cookie
    assert "refresh_token" in login_response.cookies

async def test_login_rate_limiting(client: AsyncClient, test_user_data):
    """Test login rate limiting."""
    responses = []
    
    # Make multiple failed login attempts
    for _ in range(12):  # Exceed the limit (10)
        try:
            response = await client.post(
                "/api/v1/auth/token",
                data={
                    "username": "wronguser@example.com",
                    "password": "wrongpassword",
                }
            )
            responses.append(response)
            # Small delay to prevent overwhelming the server
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error during rate limit testing: {str(e)}")
            raise

    # Get the last response
    response = responses[-1]
    
    # Check for rate limit response
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS, \
        f"Expected status code 429, got {response.status_code}. Response: {response.text}"
    assert "detail" in response.json()
    assert "Too many failed attempts" in response.json()["detail"]
    assert "Retry-After" in response.headers

async def test_refresh_token_success(client: AsyncClient, test_user_data):
    """Test successful token refresh."""
    # Register and login to get a refresh token
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    refresh_token = login_response.cookies["refresh_token"]

    # Refresh the token
    refresh_response = await client.post(
        "/api/v1/auth/refresh-token",
        cookies={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == status.HTTP_200_OK
    data = refresh_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Check that a new refresh token is set
    assert "refresh_token" in refresh_response.cookies
    assert refresh_response.cookies["refresh_token"] != refresh_token

async def test_refresh_token_reuse(client: AsyncClient, test_user_data):
    """Test prevention of refresh token reuse."""
    # Register and login to get a refresh token
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    refresh_token = login_response.cookies["refresh_token"]

    # Refresh the token once (should succeed)
    refresh_response1 = await client.post(
        "/api/v1/auth/refresh-token",
        cookies={"refresh_token": refresh_token}
    )
    assert refresh_response1.status_code == status.HTTP_200_OK

    # Attempt to refresh again with the *same* token (should fail)
    refresh_response2 = await client.post(
        "/api/v1/auth/refresh-token",
        cookies={"refresh_token": refresh_token}  # Reusing the old token
    )
    assert refresh_response2.status_code == status.HTTP_401_UNAUTHORIZED

async def test_token_revocation(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test token revocation."""
    # Register and login to get an access token
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    access_token = login_response.json()["access_token"]

    # Revoke the token
    revoke_response = await client.post(
        "/api/v1/auth/revoke",
        json={"token": access_token, "token_type_hint": "access"}
    )
    assert revoke_response.status_code == status.HTTP_200_OK

    # Verify that the token is revoked by trying to access a protected endpoint
    me_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_token_introspection(client: AsyncClient, test_user_data):
    """Test token introspection."""
    # Register and login to get an access token
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    access_token = login_response.json()["access_token"]

    # Introspect the token
    introspect_response = await client.post(
        "/api/v1/auth/introspect",
        json={"token": access_token, "token_type_hint": "access"}
    )
    assert introspect_response.status_code == status.HTTP_200_OK
    data = introspect_response.json()
    assert data["active"] is True
    assert "scope" in data
    assert "username" in data
    assert "token_type" in data
    assert "sub" in data
    assert "jti" in data

    # Introspect an invalid token
    introspect_response = await client.post(
        "/api/v1/auth/introspect",
        json={"token": "invalid.token.here", "token_type_hint": "access"}
    )
    assert introspect_response.status_code == status.HTTP_200_OK  # Still 200 OK
    data = introspect_response.json()
    assert data["active"] is False  # Should be inactive

async def test_logout(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test user logout."""
    # Register and login to get a refresh token
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.cookies["refresh_token"]

    # Logout with both access token and refresh token
    logout_response = await client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_response.status_code == status.HTTP_200_OK

    # Verify refresh token cookie is cleared
    set_cookie_header = logout_response.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert "refresh_token" in set_cookie_header
    assert "max-age=0" in set_cookie_header.lower()

    # Verify tokens are revoked by trying to use them
    me_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == status.HTTP_401_UNAUTHORIZED

    refresh_response = await client.post(
        "/api/v1/auth/refresh-token",
        cookies={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test logout when not logged in
    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == status.HTTP_200_OK  # Should still succeed

async def test_key_rotation(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test key rotation and authentication with rotated keys."""
    # 1. Register and login to get a valid token with the *current* key
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    tokens = login_response.json()
    access_token = tokens["access_token"]
    original_kid = jwt.get_unverified_header(access_token)["kid"]

    # 2. Manually add an "old" key to the KeyHistory table (simulating key rotation)
    old_private_key, old_public_key, old_kid = await generate_key_pair()
    encrypted_old_private_key = await encrypt_private_key(old_private_key)
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    
    # Log the key details before adding to history
    logger.debug(
        "Generated key pair",
        extra={
            "kid": old_kid,
            "expires_at": expires_at.isoformat()
        }
    )

    # Create and add the key history entry
    key_history_entry = KeyHistory(
        id=old_kid,
        private_key=encrypted_old_private_key,
        public_key=old_public_key,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at
    )
    
    # Add and flush to get the database-assigned values
    db_session.add(key_history_entry)
    await db_session.flush()

    # Verify the key exists in the database before proceeding
    result = await db_session.execute(
        select(KeyHistory).filter(KeyHistory.id == old_kid)
    )
    stored_key = result.scalar_one_or_none()
    assert stored_key is not None, f"Key with KID {old_kid} not found in database after flush"
    
    # Now commit the transaction
    await db_session.commit()

    # Log the stored key details
    logger.debug(
        "Stored key in database",
        extra={
            "stored_kid": stored_key.id,
            "original_kid": old_kid,
            "expires_at": stored_key.expires_at.isoformat()
        }
    )

    # 3. Create a new token with the old key
    decoded_token = jwt.decode(access_token, options={"verify_signature": False, "verify_exp": False})
    current_time = datetime.now(timezone.utc)
    token_payload = {
        **decoded_token,
        'iat': current_time,
        'exp': current_time + timedelta(minutes=30),
        'jti': str(uuid4()),
        'type': 'access'
    }

    # Create the token with the stored key
    old_token = encode_jwt(
        payload=token_payload,
        key=old_private_key,
        algorithm=settings.ALGORITHM,
        headers={"kid": stored_key.id}  # Use the stored key's ID
    )

    # Verify the token header contains the correct KID
    old_token_header = jwt.get_unverified_header(old_token)
    assert old_token_header["kid"] == stored_key.id, f"Token KID mismatch. Expected {stored_key.id}, got {old_token_header['kid']}"

    # Log the token details
    logger.debug(
        "Created token with stored key",
        extra={
            "token_kid": old_token_header["kid"],
            "stored_kid": stored_key.id
        }
    )

    # 4. Verify that the modified token (with the old kid) is valid (within grace period)
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {old_token}"}
    )
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"

    # 5. Set expires_at to the past (outside grace period)
    key_history_entry.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(key_history_entry)
    await db_session.commit()

    # 6. Verify that the modified token is now invalid (outside grace period)
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {old_token}"}
    )
    assert response.status_code == 401

    # 7. Verify that a token with a non-existent KID is invalid
    non_existent_kid_token = encode_jwt(
        payload=token_payload,
        key=old_private_key,
        algorithm=settings.ALGORITHM,
        headers={"kid": "non-existent-kid"}
    )
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {non_existent_kid_token}"}
    )
    assert response.status_code == 401

async def test_expired_access_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test accessing a protected route with an expired access token."""
    # Register a user
    await client.post("/api/v1/auth/register", json=test_user_data)

    # Create an expired access token
    expired_token = await create_access_token(
        subject=str(uuid4()),  # Use a valid UUID string
        scopes=["user"],
        expires_delta=timedelta(seconds=-1),
        jti=str(uuid4()),
        db=db_session # Pass the db session
    )

    # Attempt to access a protected route
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_expired_refresh_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test refreshing with an expired refresh token."""
    # Register a user
    await client.post("/api/v1/auth/register", json=test_user_data)

    # Create a refresh token (NOT expired initially)
    valid_token = await create_refresh_token(
        subject=str(uuid4()),
        scopes=["user"],
        jti=str(uuid4()),
        db=db_session
    )

    # Decode the token (without verifying the signature, as we're modifying it)
    payload = jwt.decode(valid_token, options={"verify_signature": False})

    # Set the expiration time to the past
    payload['exp'] = int((datetime.now(timezone.utc) - timedelta(seconds=60)).timestamp())

    # Re-encode the token with the modified expiration time
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    # Attempt to refresh the token
    response = await client.post(
        "/api/v1/auth/refresh-token",
        cookies={"refresh_token": expired_token}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_insufficient_scopes(client: AsyncClient, test_user_data):
    """Test accessing a protected route with insufficient scopes."""
    # Register a user (default scopes)
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    access_token = login_response.json()["access_token"]
    # Attempt to access a route requiring admin scope
    response = await client.get(
        "/api/v1/admin/test",  # Assuming you have an admin-only route
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_password_reset_request(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test requesting a password reset."""
    # Register a user
    await client.post("/api/v1/auth/register", json=test_user_data)

    # Request password reset
    response = await client.post(
        "/api/v1/auth/password-reset",
        json={"email": test_user_data["email"]}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["message"] == "If the email exists, a password reset link will be sent"

    # Request with a non-existent email (should still return 202)
    response = await client.post(
        "/api/v1/auth/password-reset",
        json={"email": "nonexistent@example.com"}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["message"] == "If the email exists, a password reset link will be sent"

async def test_password_reset_success(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test successful password reset."""
    # Register a user
    register_response = await client.post("/api/v1/auth/register", json=test_user_data)
    user_id = register_response.json()["id"] # Get the user ID

    # Request password reset and get the token (simulated)
    reset_token = await create_access_token(subject=user_id, scopes=["password-reset"], jti=str(uuid4()), db=db_session)

    # Reset the password
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": reset_token,
            "new_password": "NewTestPassword123!",
            "confirm_password": "NewTestPassword123!"
        }
    )
    assert response.status_code == status.HTTP_200_OK

    # Verify that the password has been changed (try to login with the old password)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],  # Old password
        }
    )
    assert login_response.status_code == status.HTTP_401_UNAUTHORIZED

    # Login with the new password (should succeed)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": "NewTestPassword123!",  # New password
        }
    )
    assert login_response.status_code == status.HTTP_200_OK

async def test_password_reset_invalid_token(client: AsyncClient, test_user_data):
    """Test password reset with an invalid token."""
    # Attempt to reset password with an invalid token
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "invalid.token.here",
            "new_password": "NewTestPassword123!",
            "confirm_password": "NewTestPassword123!"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

async def test_password_reset_expired_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test password reset with an expired token."""
    # Register a user
    register_response = await client.post("/api/v1/auth/register", json=test_user_data)
    user_id = register_response.json()["id"] # Get user ID

    # Create an expired reset token
    expired_token = await create_access_token(subject=user_id, scopes=["password-reset"], expires_delta=timedelta(seconds=-1), jti=str(uuid4()), db=db_session)

    # Attempt to reset password with the expired token
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": expired_token,
            "new_password": "NewTestPassword123!",
            "confirm_password": "NewTestPassword123!"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

async def test_password_reset_reuse_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test password reset with token reuse."""
    # Register a user
    register_response = await client.post("/api/v1/auth/register", json=test_user_data)
    user_id = register_response.json()["id"] # Get user ID

    # Request password reset and get the token (simulated)
    reset_token = await create_access_token(subject=user_id, scopes=["password-reset"], jti=str(uuid4()), db=db_session)

    # Reset the password (first time - should succeed)
    response1 = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": reset_token,
            "new_password": "NewTestPassword123!",
            "confirm_password": "NewTestPassword123!"
        }
    )
    assert response1.status_code == status.HTTP_200_OK

    # Attempt to reset again with the *same* token (should fail)
    response2 = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": reset_token,  # Reusing the token
            "new_password": "AnotherNewPassword123!",
            "confirm_password": "AnotherNewPassword123!"
        }
    )
    assert response2.status_code == status.HTTP_400_BAD_REQUEST

async def test_get_current_user_valid(client: AsyncClient, test_user_data):
    """Test get_current_user with a valid token."""
    # Register and log in the user to get a token
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={"username": test_user_data["username"], "password": test_user_data["password"]},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # Now make the request with the token
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200  # This should now pass
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]

async def test_get_current_user_invalid_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test get_current_user with an invalid token."""
    # Create an invalid but properly formatted JWT token
    invalid_token = jwt.encode(
        {"sub": "123", "exp": datetime.now(timezone.utc), "scopes": ["user"]},
        "wrong_secret",
        algorithm="HS256",
        headers={"kid": "invalid_kid"}
    )
    
    # Attempt to get the current user with an invalid token
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            security_scopes=SecurityScopes(scopes=["user"]),
            token=invalid_token,
            db=db_session
        )
    assert exc_info.value.status_code == 401
    assert "Invalid token: Key not found" in str(exc_info.value.detail)

async def test_get_current_user_revoked_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test get_current_user with a revoked token."""
    # Register a user
    register_response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert register_response.status_code == 201
    
    # Login to get a token
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    access_token = login_response.json()["access_token"]

    # Revoke the token
    revoke_response = await client.post(
        "/api/v1/auth/revoke",
        json={"token": access_token, "token_type_hint": "access"}
    )
    assert revoke_response.status_code == status.HTTP_200_OK

    # Verify token is revoked by trying to access a protected endpoint
    me_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_get_current_user_expired_token(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test get_current_user with an expired token."""
    # Register a user
    await client.post("/api/v1/auth/register", json=test_user_data)

    # Create an expired token
    expired_token = await create_access_token(
        subject=str(uuid4()),  # Use a valid UUID
        scopes=["user"],
        expires_delta=timedelta(seconds=-1),
        jti=str(uuid4()),
        db=db_session
    )

    # Attempt to get the current user
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            security_scopes=SecurityScopes(scopes=["user"]),
            token=expired_token,
            db=db_session
        )
    assert exc_info.value.status_code == 401
    assert "Token has expired" in str(exc_info.value.detail)

async def test_get_current_user_insufficient_scope(client: AsyncClient, test_user_data, db_session: AsyncSession):
    """Test get_current_user with insufficient scope."""
    # Register a user with only "user" scope
    await client.post("/api/v1/auth/register", json=test_user_data)
    login_response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
    )
    access_token = login_response.json()["access_token"]

    # Attempt to get current user requiring "admin" scope
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            security_scopes=SecurityScopes(scopes=["admin"]),  # Requires "admin"
            token=access_token,
            db=db_session  # Add the db session here
        )
    assert exc_info.value.status_code == 403
    assert "Not enough permissions" in str(exc_info.value.detail)

async def test_verify_token_missing_kid(client: AsyncClient):
    """Test verify_token with a missing kid."""
    # Create a token without a kid
    token = jwt.encode({"sub": "123"}, "secret", algorithm="HS256")
    
    # Try to use the token
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token format" in response.json()["detail"]

async def test_verify_token_invalid_signature(client: AsyncClient):
    """Test verify_token with an invalid signature."""
    # Create a token with wrong signature
    token = jwt.encode(
        {"sub": "123", "kid": settings.CURRENT_KID}, 
        "wrong_secret", 
        algorithm="HS256"
    )
    
    # Try to use the token
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid token format" in response.json()["detail"]

async def test_create_user_duplicate_email(client: AsyncClient, test_user_data):
    """Test create_user with a duplicate email."""
    # First registration (should succeed)
    response1 = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response1.status_code == 201  # This should now pass

    # Second registration with the same email (should fail)
    response2 = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response2.status_code == 400
    assert "Email or username already registered" in response2.json()["detail"]

async def test_test_client(client: AsyncClient):
    """Test the test client."""
    response = await client.post("/api/v1/auth/test_test")
    assert response.status_code == 200
    assert response.json() == {"message": "Test client is working"}


