"""
Authentication and authorization fixtures for testing.

This module provides fixtures for user authentication, token generation,
and related functionality needed for testing authentication and authorization.
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Optional
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from fastapi import FastAPI

from app.core.auth import create_access_token, get_password_hash
from app.models import User
from app.models.enums import UserTier, PaymentStatus
from app.tests.config import test_settings


@pytest.fixture
def test_password() -> str:
    """Return a consistent test password."""
    return "TestPassword123!"


@pytest.fixture
def test_user_data(test_password: str) -> Dict:
    """
    Generate data for a standard test user.
    
    This fixture provides consistent user data for test cases,
    ensuring reproducible test scenarios.
    """
    return {
        "email": "testuser@example.com",
        "username": "testuser",
        "password": test_password,
        "is_active": True,
        "tier": UserTier.FREE,
        "payment_status": PaymentStatus.INACTIVE
    }


@pytest.fixture
def test_premium_user_data(test_password: str) -> Dict:
    """Generate data for a premium test user."""
    return {
        "email": "premium@example.com",
        "username": "premiumuser",
        "password": test_password,
        "is_active": True,
        "tier": UserTier.PREMIUM,
        "payment_status": PaymentStatus.ACTIVE
    }


@pytest.fixture
def test_superuser_data(test_password: str) -> Dict:
    """Generate data for a superuser test user."""
    return {
        "email": "admin@example.com",
        "username": "admin",
        "password": test_password,
        "is_active": True,
        "is_superuser": True,
        "tier": UserTier.PREMIUM,
        "payment_status": PaymentStatus.ACTIVE
    }


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_user_data: Dict) -> AsyncGenerator[User, None]:
    """
    Create and return a standard test user.
    
    This fixture creates a user in the database for testing,
    using the data from test_user_data.
    """
    user = User(
        id=uuid4(),
        email=test_user_data["email"],
        username=test_user_data["username"],
        hashed_password=get_password_hash(test_user_data["password"]),
        is_active=test_user_data["is_active"],
        tier=test_user_data["tier"],
        payment_status=test_user_data["payment_status"],
        created_at=datetime.utcnow()
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    yield user


@pytest_asyncio.fixture
async def test_premium_user(db_session: AsyncSession, test_premium_user_data: Dict) -> AsyncGenerator[User, None]:
    """Create and return a premium test user."""
    user = User(
        id=uuid4(),
        email=test_premium_user_data["email"],
        username=test_premium_user_data["username"],
        hashed_password=get_password_hash(test_premium_user_data["password"]),
        is_active=test_premium_user_data["is_active"],
        tier=test_premium_user_data["tier"],
        payment_status=test_premium_user_data["payment_status"],
        created_at=datetime.utcnow()
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    yield user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession, test_superuser_data: Dict) -> AsyncGenerator[User, None]:
    """Create and return a superuser test user."""
    user = User(
        id=uuid4(),
        email=test_superuser_data["email"],
        username=test_superuser_data["username"],
        hashed_password=get_password_hash(test_superuser_data["password"]),
        is_active=test_superuser_data["is_active"],
        is_superuser=test_superuser_data["is_superuser"],
        tier=test_superuser_data["tier"],
        payment_status=test_superuser_data["payment_status"],
        created_at=datetime.utcnow()
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    yield user


@pytest_asyncio.fixture
async def auth_headers(test_user: User, db_session: AsyncSession) -> Dict:
    """
    Generate authentication headers for the test user.
    
    This fixture creates a valid JWT token and returns
    the headers needed for authenticated requests.
    """
    access_token = await create_access_token(
        subject=str(test_user.id),
        scopes=["user"],
        jti=str(uuid4()),
        db=db_session
    )
    
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def premium_auth_headers(test_premium_user: User, db_session: AsyncSession) -> Dict:
    """Generate authentication headers for the premium test user."""
    access_token = await create_access_token(
        subject=str(test_premium_user.id),
        scopes=["user", "premium"],
        jti=str(uuid4()),
        db=db_session
    )
    
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def admin_auth_headers(test_superuser: User, db_session: AsyncSession) -> Dict:
    """Generate authentication headers for the admin test user."""
    access_token = await create_access_token(
        subject=str(test_superuser.id),
        scopes=["user", "premium", "admin"],
        jti=str(uuid4()),
        db=db_session
    )
    
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, auth_headers: Dict) -> AsyncClient:
    """
    Create an authenticated API client for a regular user.
    
    This fixture returns an HTTP client preconfigured with
    authentication headers for a regular user.
    """
    client.headers.update(auth_headers)
    return client


@pytest_asyncio.fixture
async def premium_client(client: AsyncClient, premium_auth_headers: Dict) -> AsyncClient:
    """Create an authenticated API client for a premium user."""
    client.headers.update(premium_auth_headers)
    return client


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_auth_headers: Dict) -> AsyncClient:
    """Create an authenticated API client for an admin user."""
    client.headers.update(admin_auth_headers)
    return client 