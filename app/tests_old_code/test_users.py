"""
Tests for user service endpoints.

This module provides comprehensive testing for:
- Profile management (GET, PUT)
- Message counting and limits
- Account deactivation/reactivation
- Admin access controls
- Authentication and authorization
- Input validation
- Error handling
"""

import pytest
from datetime import datetime, timedelta, timezone
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from app.core.auth import create_access_token, get_password_hash
from app.models import User
from app.models.enums import UserTier, PaymentStatus
from uuid import uuid4
from fastapi import FastAPI
import pandas as pd
from unittest.mock import AsyncMock, patch, MagicMock
from pytest_mock import MockerFixture
from datetime import date
from app.models.enums import ClimbingDiscipline, LogbookType
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.exceptions import DatabaseError
from contextlib import asynccontextmanager
from app.db.session import get_db
from typing import AsyncGenerator
from app.core.auth import TokenData

pytestmark = pytest.mark.asyncio

# Helper Functions
async def create_test_user(db: AsyncSession, user_data: dict) -> User:
    """Helper to create a test user."""
    user = User(
        id=uuid4(),
        email=user_data["email"],
        username=user_data["username"],
        hashed_password=get_password_hash(user_data["password"]),
        is_active=True,
        tier=UserTier.FREE,
        payment_status=PaymentStatus.INACTIVE
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_token_headers(user: User, db: AsyncSession) -> dict:
    """Helper to get authorization headers."""
    access_token = await create_access_token(
        subject=str(user.id),
        scopes=["user"],
        jti=str(uuid4()),
        db=db
    )
    return {"Authorization": f"Bearer {access_token}"}

@pytest.mark.asyncio
class TestUserProfile:
    """Test user profile management endpoints."""
    
    async def test_get_own_profile(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        app: FastAPI
    ):
        """Test GET /users/me endpoint."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        response = await client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == test_user_data["email"]
        assert data["username"] == test_user_data["username"]
        assert data["is_active"] is True
        assert data["tier"] == UserTier.FREE.value
        
    async def test_update_profile(
        self,
        client: AsyncClient,
        mocker: MockerFixture,
        db_session: AsyncSession
    ):
        """Test PATCH /users/me endpoint."""
        # Create test user and get auth headers
        test_user = await create_test_user(db_session, {
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpass123"
        })
        headers = await get_token_headers(test_user, db_session)

        # Mock the Mountain Project client
        mock_df = pd.DataFrame({
            'Date': ['2024-02-23'],
            'Route': ['Test Route'],
            'Rating': ['5.10a'],
            'Notes': ['Test notes'],
            'URL': ['https://mountainproject.com/route/123'],
            'Pitches': [1],
            'Location': ['Test Crag'],
            'Style': ['Lead'],
            'Lead Style': ['Redpoint'],
            'Route Type': ['Sport'],
            'Length': [30],
            'Rating Code': [18],
            'Avg Stars': [3.5],
            'Your Stars': [4.0],
            'location_raw': ['Test Crag, Test Area'],
            'send_bool': [True],
            'discipline': ['sport'],
            'binned_grade': ['5.10a']
        })

        mocker.patch(
            'app.services.logbook.gateways.mp_csv_client.MountainProjectCSVClient.fetch_user_ticks',
            return_value=mock_df
        )

        # Mock the _build_entities method
        async def mock_build_entities(*args, **kwargs):
            tick = {
                'user_id': test_user.id,
                'route_name': 'Test Route',
                'tick_date': date(2024, 2, 23),
                'route_grade': '5.10a',
                'binned_grade': '5.10a',
                'binned_code': 18,
                'length': 30,
                'pitches': 1,
                'location': 'Test Crag',
                'location_raw': 'Test Crag, Test Area',
                'lead_style': 'Redpoint',
                'discipline': ClimbingDiscipline.SPORT,
                'send_bool': True,
                'route_url': 'https://mountainproject.com/route/123',
                'notes': 'Test notes',
                'route_quality': 3.5,
                'user_quality': 4.0,
                'logbook_type': LogbookType.MOUNTAIN_PROJECT
            }
            
            pyramid = {
                'user_id': test_user.id,
                'tick_id': 1,
                'send_date': date(2024, 2, 23),
                'location': 'Test Crag',
                'binned_code': 18,
                'num_attempts': 1,
                'num_sends': 1,
                'description': 'Test Route - 5.10a'
            }
            
            return [tick], [pyramid], []  # Empty list for tags

        mocker.patch(
            'app.services.logbook.orchestrator.LogbookOrchestrator._build_entities',
            side_effect=mock_build_entities
        )

        # Update profile data
        profile_data = {
            "email": "updated@example.com",
            "mountain_project_url": "https://www.mountainproject.com/user/123/tick-export"
        }

        # Make request to update profile
        response = await client.patch("/api/v1/users/me", json=profile_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        assert data["mountain_project_url"] == "https://www.mountainproject.com/user/123/tick-export"
        
    async def test_update_profile_duplicate_email(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test email uniqueness validation."""
        user1 = await create_test_user(db_session, test_user_data)
        user2 = await create_test_user(
            db_session,
            {**test_user_data, "email": "other@example.com", "username": "other"}
        )
        headers = await get_token_headers(user2, db_session)
        
        response = await client.patch(
            "/api/v1/users/me",
            headers=headers,
            json={"email": user1.email}
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

class TestMessageCounting:
    """Test message counting and limits."""
    
    async def test_get_message_count_free_tier(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test GET /users/me/message-count for free tier."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        response = await client.get("/api/v1/users/me/message-count", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["daily_message_count"] == 0
        assert data["max_daily_messages"] == 10  # Free tier limit
        assert data["remaining_messages"] == 10
        
    async def test_get_message_count_premium(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_premium_user_data: dict
    ):
        """Test GET /users/me/message-count for premium tier."""
        user = await create_test_user(db_session, test_premium_user_data)
        user.tier = UserTier.PREMIUM
        await db_session.commit()
        
        headers = await get_token_headers(user, db_session)
        response = await client.get("/api/v1/users/me/message-count", headers=headers)
        data = response.json()
        
        assert data["daily_message_count"] == 0
        assert data["remaining_messages"] is None  # Unlimited for premium

class TestAccountManagement:
    """Test account deactivation and reactivation."""
    
    async def test_deactivate_account(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test POST /users/me/deactivate."""
        # Create test user and get auth token
        user = await create_test_user(db_session, test_user_data)
        user_id = user.id  # Store the ID for later lookup
        token = await create_access_token(
            subject=str(user.id),
            scopes=["user"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {token}"}
        
        # Deactivate account
        response = await client.post("/api/v1/users/me/deactivate", headers=headers)
        assert response.status_code == 200
        
        # Get fresh user instance from database
        result = await db_session.execute(select(User).filter(User.id == user_id))
        updated_user = result.scalar_one()
        
        # Verify user state
        assert updated_user.is_active is False
        assert updated_user.tier == UserTier.FREE
        
        # Verify token is revoked by trying to use it
        me_response = await client.get("/api/v1/users/me", headers=headers)
        assert me_response.status_code == 403
        assert "Token has been revoked" in me_response.json()["detail"]
        
    async def test_reactivate_account(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test account reactivation via login."""
        user = await create_test_user(db_session, test_user_data)
        user_id = user.id  # Store the user ID
        user.is_active = False
        await db_session.commit()

        # Try to reactivate via login
        login_data = {
            "username": test_user_data["email"],
            "password": test_user_data["password"],
            "grant_type": "password",
            "scope": "user"
        }
        response = await client.post("/api/v1/auth/token", data=login_data)
        assert response.status_code == 200

        # Get fresh user instance and verify it is now active
        result = await db_session.execute(select(User).filter(User.id == user_id))
        updated_user = result.scalar_one()
        assert updated_user.is_active is True
        assert updated_user.tier == UserTier.FREE
        
    async def test_reactivate_already_active(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test logging in with an already active account."""
        user = await create_test_user(db_session, test_user_data)
        user_id = user.id  # Store the user ID

        # Try to login with active account
        login_data = {
            "username": test_user_data["email"],
            "password": test_user_data["password"],
            "grant_type": "password",
            "scope": "user"
        }
        response = await client.post("/api/v1/auth/token", data=login_data)
        assert response.status_code == 200

        # Get fresh user instance and verify it remains active
        result = await db_session.execute(select(User).filter(User.id == user_id))
        updated_user = result.scalar_one()
        assert updated_user.is_active is True

class TestAdminAccess:
    """Test admin-only endpoints."""
    
    async def test_get_user_profile_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser_data: dict,
        test_user_data: dict
    ):
        """Test GET /users/{user_id} as admin."""
        admin = await create_test_user(db_session, test_superuser_data)
        admin.is_superuser = True
        user = await create_test_user(db_session, test_user_data)
        await db_session.commit()
        
        admin_token = await create_access_token(
            subject=str(admin.id),
            scopes=["user", "admin"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = await client.get(f"/api/v1/users/{user.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email
        
    async def test_get_user_profile_non_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test GET /users/{user_id} as non-admin."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        response = await client.get(f"/api/v1/users/{user.id}", headers=headers)
        assert response.status_code == 403  # Forbidden

class TestInputValidation:
    """Test input validation and error responses."""
    
    async def test_invalid_email_format(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test updating profile with invalid email."""
        user = await create_test_user(db_session, test_user_data)
        token = await create_access_token(
            subject=str(user.id),
            scopes=["user"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.patch(
            "/api/v1/users/me",
            headers=headers,
            json={"email": "not-an-email"}
        )
        assert response.status_code == 422  # Validation error
        
    async def test_invalid_mountain_project_url(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test updating profile with invalid Mountain Project URL."""
        user = await create_test_user(db_session, test_user_data)
        token = await create_access_token(
            subject=str(user.id),
            scopes=["user"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.patch(
            "/api/v1/users/me",
            headers=headers,
            json={"mountain_project_url": "not-a-url"}
        )
        assert response.status_code == 422
        
    async def test_invalid_user_id(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser_data: dict
    ):
        """Test admin endpoint with invalid user ID."""
        admin = await create_test_user(db_session, test_superuser_data)
        admin.is_superuser = True
        await db_session.commit()
        
        token = await create_access_token(
            subject=str(admin.id),
            scopes=["user", "admin"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.get(
            "/api/v1/users/invalid-uuid",
            headers=headers
        )
        assert response.status_code == 422  # Invalid UUID format

class TestErrorResponses:
    """Test error response handling."""
    
    async def test_not_found_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser_data: dict
    ):
        """Test getting non-existent user profile."""
        admin = await create_test_user(db_session, test_superuser_data)
        admin.is_superuser = True
        await db_session.commit()
        
        token = await create_access_token(
            subject=str(admin.id),
            scopes=["user", "admin"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {token}"}
        
        fake_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/users/{fake_id}",
            headers=headers
        )
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
        
    async def test_database_error(
        self,
        client: AsyncClient,
        app: FastAPI,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test handling database errors."""
        # Create initial user with real session
        user = await create_test_user(db_session, test_user_data)
        token = await create_access_token(
            subject=str(user.id),
            scopes=["user"],
            jti=str(uuid4()),
            db=db_session
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Create a mock session that raises an error
        mock_session = AsyncMock()
        mock_session.commit.side_effect = DatabaseError("Database error")
        mock_session.scalar.return_value = None  # For email uniqueness check
        mock_session.add.return_value = None
        mock_session.refresh.return_value = None
        
        # Mock execute to return a result with scalar_one_or_none
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = lambda: user
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Create an async generator that yields our mock session
        async def override_get_db():
            try:
                yield mock_session
            finally:
                pass

        # Override the get_db dependency in the test app
        app.dependency_overrides[get_db] = override_get_db

        # Mock token verification to return valid token data
        mock_token_data = TokenData(
            user_id=user.id,
            scopes=["user"],
            type="access",
            jti=str(uuid4())
        )
        mocker.patch("app.core.auth.verify_token", new_callable=AsyncMock, return_value=mock_token_data)

        # Also mock the redis client to avoid cache issues
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = True
        mocker.patch("app.api.v1.endpoints.user.get_redis", return_value=mock_redis)

        try:
            response = await client.patch(
                "/api/v1/users/me",
                headers=headers,
                json={"email": "new@example.com"}
            )

            assert response.status_code == 500
            assert response.json()["detail"] == "Could not update profile"
            mock_session.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

class TestCaching:
    """Test Redis caching functionality."""
    
    async def test_profile_cache_hit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_user_data: dict
    ):
        """Test profile retrieval from cache."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # First request should cache
        response1 = await client.get("/api/v1/users/me", headers=headers)
        assert response1.status_code == 200
        
        # Manually verify cache exists
        cache_key = f"user_profile:{user.id}"
        cached_data = await redis_client.get(cache_key)
        assert cached_data is not None
        
        # Second request should hit cache
        response2 = await client.get("/api/v1/users/me", headers=headers)
        assert response2.status_code == 200
        assert response2.json() == response1.json()
        
    async def test_cache_invalidation_on_update(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_user_data: dict
    ):
        """Test cache invalidation after profile update."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Cache the initial profile
        await client.get("/api/v1/users/me", headers=headers)
        
        # Update profile
        new_email = "updated@example.com"
        response = await client.patch(
            "/api/v1/users/me",
            headers=headers,
            json={"email": new_email}
        )
        assert response.status_code == 200
        
        # Verify cache was invalidated
        cache_key = f"user_profile:{user.id}"
        cached_data = await redis_client.get(cache_key)
        assert cached_data is None
        
        # New request should cache new data
        response = await client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == new_email

class TestSubscriptionManagement:
    """Test subscription management functionality."""
    
    async def test_immediate_tier_update(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test immediate tier update on subscription initiation."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Mock Stripe checkout session creation
        mock_session = mocker.Mock(
            id="cs_test_123",
            payment_status="unpaid",
            status="open"
        )
        mocker.patch("stripe.checkout.Session.create", return_value=mock_session)
        
        response = await client.post(
            "/api/v1/users/me/subscribe",
            headers=headers,
            json={"desired_tier": UserTier.PREMIUM.value}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending_confirmation"
        
        # Verify immediate tier update
        await db_session.refresh(user)
        assert user.tier == UserTier.PREMIUM
        assert user.payment_status == PaymentStatus.PENDING
        assert user.last_payment_check is not None
        
    async def test_stripe_error_handling(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test handling of Stripe API errors."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Mock Stripe error
        mocker.patch(
            "stripe.checkout.Session.create",
            side_effect=stripe.error.StripeError("Stripe API error")
        )
        
        response = await client.post(
            "/api/v1/users/me/subscribe",
            headers=headers,
            json={"desired_tier": "premium"}
        )
        assert response.status_code == 502
        assert "Could not create subscription" in response.json()["detail"]

    async def test_subscription_webhook_confirmation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test subscription confirmation via webhook."""
        user = await create_test_user(db_session, test_user_data)
        user.tier = UserTier.PREMIUM
        user.payment_status = PaymentStatus.PENDING
        await db_session.commit()
        
        # Mock Stripe webhook event
        event_data = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "customer": user.stripe_customer_id,
                    "payment_status": "paid",
                    "status": "complete"
                }
            }
        }
        
        response = await client.post(
            "/api/v1/webhooks/stripe",
            json=event_data,
            headers={"Stripe-Signature": "test_sig"}
        )
        assert response.status_code == 200
        
        # Verify subscription confirmed
        await db_session.refresh(user)
        assert user.payment_status == PaymentStatus.ACTIVE

    async def test_subscription_cancellation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test subscription cancellation."""
        user = await create_test_user(db_session, test_user_data)
        user.stripe_subscription_id = "sub_123"
        user.tier = UserTier.PREMIUM
        user.payment_status = PaymentStatus.ACTIVE
        await db_session.commit()
        
        headers = await get_token_headers(user, db_session)
        
        # Mock Stripe subscription deletion
        mocker.patch("stripe.Subscription.delete")
        
        response = await client.post(
            "/api/v1/users/me/cancel-subscription",
            headers=headers
        )
        assert response.status_code == 200
        
        # Verify subscription cancelled
        await db_session.refresh(user)
        assert user.stripe_subscription_id is None
        assert user.tier == UserTier.FREE
        assert user.payment_status == PaymentStatus.CANCELLED

    async def test_subscription_status_sync(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test subscription status synchronization."""
        user = await create_test_user(db_session, test_user_data)
        user.stripe_subscription_id = "sub_123"
        user.tier = UserTier.PREMIUM
        user.payment_status = PaymentStatus.ACTIVE
        await db_session.commit()
        
        headers = await get_token_headers(user, db_session)
        
        # Mock Stripe subscription retrieval with inactive status
        mock_subscription = mocker.Mock(
            status="canceled",
            current_period_end=int(datetime.now(timezone.utc).timestamp())
        )
        mocker.patch("stripe.Subscription.retrieve", return_value=mock_subscription)
        
        response = await client.get(
            "/api/v1/users/me/subscription",
            headers=headers
        )
        assert response.status_code == 200
        
        # Verify subscription status synced
        await db_session.refresh(user)
        assert user.tier == UserTier.FREE
        assert user.payment_status == PaymentStatus.INACTIVE

    async def test_subscription_rate_limiting(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_user_data: dict
    ):
        """Test subscription request rate limiting."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Set rate limit key
        rate_key = f"subscription_attempts:{user.id}"
        await redis_client.setex(rate_key, 60, "5")  # 5 attempts in last minute
        
        response = await client.post(
            "/api/v1/users/me/subscribe",
            headers=headers,
            json={"desired_tier": "premium"}
        )
        assert response.status_code == 429
        assert "Too many attempts" in response.json()["detail"]

    async def test_subscription_webhook_signature_verification(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict
    ):
        """Test Stripe webhook signature verification."""
        # Send webhook without proper signature
        response = await client.post(
            "/api/v1/webhooks/stripe",
            json={"type": "checkout.session.completed"},
            headers={"Stripe-Signature": "invalid_sig"}
        )
        assert response.status_code == 400
        assert "Invalid signature" in response.json()["detail"]

    async def test_subscription_idempotency(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test subscription creation idempotency."""
        user = await create_test_user(db_session, test_user_data)
        user.stripe_subscription_id = "sub_123"
        user.payment_status = PaymentStatus.ACTIVE
        await db_session.commit()
        
        headers = await get_token_headers(user, db_session)
        
        response = await client.post(
            "/api/v1/users/me/subscribe",
            headers=headers,
            json={"desired_tier": "premium"}
        )
        assert response.status_code == 400
        assert "Active subscription exists" in response.json()["detail"]

class TestBackgroundTasks:
    """Test background task execution."""
    
    async def test_mountain_project_sync(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test Mountain Project data sync on URL update."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Mock LogbookOrchestrator
        mock_process = mocker.patch(
            "app.services.logbook.orchestrator.LogbookOrchestrator.process_mountain_project_data"
        )
        
        # Update Mountain Project URL
        new_url = "https://mountainproject.com/user/123"
        response = await client.patch(
            "/api/v1/users/me",
            headers=headers,
            json={"mountain_project_url": new_url}
        )
        assert response.status_code == 200
        
        # Verify background task was called
        mock_process.assert_called_once_with(user.id, new_url)
        
    async def test_eight_a_nu_sync(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_data: dict,
        mocker
    ):
        """Test 8a.nu data sync on URL update."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Mock LogbookOrchestrator
        mock_process = mocker.patch(
            "app.services.logbook.orchestrator.LogbookOrchestrator.process_eight_a_nu_data"
        )
        
        # Update 8a.nu URL
        new_url = "https://8a.nu/user/123"
        response = await client.patch(
            "/api/v1/users/me",
            headers=headers,
            json={"eight_a_nu_url": new_url}
        )
        assert response.status_code == 200
        
        # Verify background task was called
        mock_process.assert_called_once_with(user.id, new_url)

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    async def test_password_change_rate_limit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_user_data: dict
    ):
        """Test password change rate limiting."""
        user = await create_test_user(db_session, test_user_data)
        headers = await get_token_headers(user, db_session)
        
        # Make 6 password change attempts
        for i in range(6):
            response = await client.post(
                "/api/v1/users/me/change-password",
                headers=headers,
                json={
                    "old_password": "old_password",
                    "new_password": "New_password123!",
                    "confirmation": "New_password123!"
                }
            )
            if i < 5:
                assert response.status_code in [200, 400]  # Success or validation error
            else:
                assert response.status_code == 429  # Too many requests
                assert "Too many attempts" in response.json()["detail"]