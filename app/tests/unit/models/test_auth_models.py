"""
Unit tests for authentication models in the Send Sage application.

This module tests the SQLAlchemy models related to authentication including:
- User model
- KeyHistory model
- RevokedToken model
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, and_, func

from app.models.auth import User, KeyHistory, RevokedToken


@pytest.mark.unit
class TestUserModel:
    """Tests for User model."""
    
    def test_user_creation(self):
        """Test user model instance creation."""
        # Create a user with all fields
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
            hashed_password="hashedpassword",
            is_active=True,
            experience_level="intermediate",
            preferences={"theme": "dark", "grade_display": "yds"},
            created_at=now,
            updated_at=now
        )
        
        # Verify field values
        assert user.id == user_id
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashedpassword"
        assert user.is_active is True
        assert user.experience_level == "intermediate"
        assert user.preferences == {"theme": "dark", "grade_display": "yds"}
        assert user.created_at == now
        assert user.updated_at == now
    
    def test_user_representation(self):
        """Test user string representation."""
        # Create a simple user
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com"
        )
        
        # Verify string representation
        assert str(user) == f"User(id={user.id}, username=testuser, email=test@example.com)"
        
        # Verify repr representation
        assert "User" in repr(user)
        assert "testuser" in repr(user)
        assert "test@example.com" in repr(user)
    
    @pytest.mark.asyncio
    async def test_user_queries(self, tmp_path):
        """Test user model querying with SQLAlchemy."""
        # Import SQLAlchemy components
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker, declarative_base
        
        # Create a temporary SQLite database
        db_path = tmp_path / "test.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        
        # Create tables
        from app.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create test users
        user1 = User(
            id=uuid4(),
            username="user1",
            email="user1@example.com",
            hashed_password="hashedpassword1",
            is_active=True
        )
        
        user2 = User(
            id=uuid4(),
            username="user2",
            email="user2@example.com",
            hashed_password="hashedpassword2",
            is_active=False
        )
        
        # Insert users
        async with async_session() as session:
            session.add_all([user1, user2])
            await session.commit()
        
        # Query users
        async with async_session() as session:
            # Find all users
            result = await session.execute(select(User))
            users = result.scalars().all()
            assert len(users) == 2
            
            # Find by email
            result = await session.execute(
                select(User).where(User.email == "user1@example.com")
            )
            found_user = result.scalar_one()
            assert found_user.username == "user1"
            
            # Find active users
            result = await session.execute(
                select(User).where(User.is_active == True)
            )
            active_users = result.scalars().all()
            assert len(active_users) == 1
            assert active_users[0].username == "user1"
        
        # Clean up
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.unit
class TestKeyHistoryModel:
    """Tests for KeyHistory model."""
    
    def test_key_history_creation(self):
        """Test key history model instance creation."""
        # Create a key history record with all fields
        key_id = str(uuid4())
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)
        
        key_history = KeyHistory(
            id=key_id,
            private_key="encrypted_private_key",
            public_key="public_key_pem",
            created_at=now,
            expires_at=expires,
            revoked_at=None
        )
        
        # Verify field values
        assert key_history.id == key_id
        assert key_history.private_key == "encrypted_private_key"
        assert key_history.public_key == "public_key_pem"
        assert key_history.created_at == now
        assert key_history.expires_at == expires
        assert key_history.revoked_at is None
    
    def test_key_history_properties(self):
        """Test key history model property methods."""
        # Create a key history record with different states
        
        # Active key
        now = datetime.now(timezone.utc)
        active_key = KeyHistory(
            id=str(uuid4()),
            private_key="encrypted_private_key",
            public_key="public_key_pem",
            created_at=now,
            expires_at=now + timedelta(days=30),
            revoked_at=None
        )
        
        # Expired key
        expired_key = KeyHistory(
            id=str(uuid4()),
            private_key="encrypted_private_key",
            public_key="public_key_pem",
            created_at=now - timedelta(days=60),
            expires_at=now - timedelta(days=30),
            revoked_at=None
        )
        
        # Revoked key
        revoked_key = KeyHistory(
            id=str(uuid4()),
            private_key="encrypted_private_key",
            public_key="public_key_pem",
            created_at=now - timedelta(days=15),
            expires_at=now + timedelta(days=15),
            revoked_at=now - timedelta(days=1)
        )
        
        # Test is_active property
        assert active_key.is_active is True
        assert expired_key.is_active is False
        assert revoked_key.is_active is False
        
        # Test is_expired property
        assert active_key.is_expired is False
        assert expired_key.is_expired is True
        assert revoked_key.is_expired is False
        
        # Test is_revoked property
        assert active_key.is_revoked is False
        assert expired_key.is_revoked is False
        assert revoked_key.is_revoked is True
    
    @pytest.mark.asyncio
    async def test_key_history_queries(self, tmp_path):
        """Test key history model querying with SQLAlchemy."""
        # Import SQLAlchemy components
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Create a temporary SQLite database
        db_path = tmp_path / "test.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        
        # Create tables
        from app.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create test key records
        now = datetime.now(timezone.utc)
        
        # Active key
        active_key = KeyHistory(
            id=str(uuid4()),
            private_key="encrypted_active_key",
            public_key="public_active_key",
            created_at=now,
            expires_at=now + timedelta(days=30)
        )
        
        # Expired key
        expired_key = KeyHistory(
            id=str(uuid4()),
            private_key="encrypted_expired_key",
            public_key="public_expired_key",
            created_at=now - timedelta(days=60),
            expires_at=now - timedelta(days=30)
        )
        
        # Revoked key
        revoked_key = KeyHistory(
            id=str(uuid4()),
            private_key="encrypted_revoked_key",
            public_key="public_revoked_key",
            created_at=now - timedelta(days=15),
            expires_at=now + timedelta(days=15),
            revoked_at=now - timedelta(days=1)
        )
        
        # Insert keys
        async with async_session() as session:
            session.add_all([active_key, expired_key, revoked_key])
            await session.commit()
        
        # Query keys
        async with async_session() as session:
            # Find all keys
            result = await session.execute(select(KeyHistory))
            keys = result.scalars().all()
            assert len(keys) == 3
            
            # Find active keys
            result = await session.execute(
                select(KeyHistory).where(
                    and_(
                        KeyHistory.expires_at > now,
                        KeyHistory.revoked_at.is_(None)
                    )
                )
            )
            active_keys = result.scalars().all()
            assert len(active_keys) == 1
            assert "active_key" in active_keys[0].private_key
            
            # Find expired keys
            result = await session.execute(
                select(KeyHistory).where(KeyHistory.expires_at <= now)
            )
            expired_keys = result.scalars().all()
            assert len(expired_keys) == 1
            assert "expired_key" in expired_keys[0].private_key
            
            # Find revoked keys
            result = await session.execute(
                select(KeyHistory).where(KeyHistory.revoked_at.is_not(None))
            )
            revoked_keys = result.scalars().all()
            assert len(revoked_keys) == 1
            assert "revoked_key" in revoked_keys[0].private_key
            
            # Find latest active key
            result = await session.execute(
                select(KeyHistory)
                .where(
                    and_(
                        KeyHistory.expires_at > now,
                        KeyHistory.revoked_at.is_(None)
                    )
                )
                .order_by(KeyHistory.created_at.desc())
                .limit(1)
            )
            latest_key = result.scalar_one_or_none()
            assert latest_key is not None
            assert latest_key.id == active_key.id
        
        # Clean up
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.unit
class TestRevokedTokenModel:
    """Tests for RevokedToken model."""
    
    def test_revoked_token_creation(self):
        """Test revoked token model instance creation."""
        # Create a revoked token record with all fields
        token_jti = str(uuid4())
        now = datetime.now(timezone.utc)
        
        revoked_token = RevokedToken(
            jti=token_jti,
            revoked_at=now
        )
        
        # Verify field values
        assert revoked_token.jti == token_jti
        assert revoked_token.revoked_at == now
    
    @pytest.mark.asyncio
    async def test_revoked_token_queries(self, tmp_path):
        """Test revoked token model querying with SQLAlchemy."""
        # Import SQLAlchemy components
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Create a temporary SQLite database
        db_path = tmp_path / "test.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        
        # Create tables
        from app.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create test revoked tokens
        now = datetime.now(timezone.utc)
        
        # Recent token
        recent_token = RevokedToken(
            jti=str(uuid4()),
            revoked_at=now
        )
        
        # Old token
        old_token = RevokedToken(
            jti=str(uuid4()),
            revoked_at=now - timedelta(days=90)
        )
        
        # Insert tokens
        async with async_session() as session:
            session.add_all([recent_token, old_token])
            await session.commit()
        
        # Query tokens
        async with async_session() as session:
            # Find all tokens
            result = await session.execute(select(RevokedToken))
            tokens = result.scalars().all()
            assert len(tokens) == 2
            
            # Find specific token
            result = await session.execute(
                select(RevokedToken).where(RevokedToken.jti == recent_token.jti)
            )
            found_token = result.scalar_one()
            assert found_token.jti == recent_token.jti
            
            # Find tokens older than 30 days
            thirty_days_ago = now - timedelta(days=30)
            result = await session.execute(
                select(RevokedToken).where(RevokedToken.revoked_at < thirty_days_ago)
            )
            old_tokens = result.scalars().all()
            assert len(old_tokens) == 1
            assert old_tokens[0].jti == old_token.jti
        
        # Clean up
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all) 