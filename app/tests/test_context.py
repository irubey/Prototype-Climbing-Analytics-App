import pytest
import pytest_asyncio
from datetime import datetime, timedelta
import pandas as pd
import json
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from uuid import UUID, uuid4
from httpx import AsyncClient

from app.services.chat.context.data_aggregator import DataAggregator
from app.services.chat.context.context_enhancer import ContextEnhancer
from app.services.chat.context.unified_formatter import UnifiedFormatter
from app.services.chat.context.cache_manager import CacheManager
from app.services.chat.context.orchestrator import ContextOrchestrator
from app.models.enums import HoldType

# ============================================================================
# Shared Fixtures
# ============================================================================

@pytest.fixture
def sample_climber_data():
    """Base climber data for testing."""
    now = datetime.now()
    return {
        'user_id': 1,
        'years_climbing': 3,
        'highest_boulder_grade': 'V5',
        'goal_grade': 'V7',
        'goal_deadline': now + timedelta(days=180),
        'training_frequency': '3x_week',
        'preferred_styles': ['overhang', 'crimps'],
        'strengths': ['power', 'flexibility'],
        'weaknesses': ['endurance'],
        'training_focus': 'power_endurance',
        'injury_status': None,
        'energy_levels': 'high',
        'sleep_quality': 'good'
    }

@pytest.fixture
def sample_ticks():
    """Sample climbing tick data for testing."""
    now = datetime.now()
    return [
        {
            'date': now - timedelta(days=5),
            'route': 'Route1',
            'grade': 'V4',
            'send_status': 'sent'
        },
        {
            'date': now - timedelta(days=15),
            'route': 'Route2',
            'grade': 'V5',
            'send_status': 'sent'
        },
        {
            'date': now - timedelta(days=25),
            'route': 'Route3',
            'grade': 'V6',
            'send_status': 'sent'
        }
    ]

@pytest.fixture
def sample_enhanced_context(sample_climber_data, sample_ticks):
    """Enhanced context data for testing."""
    return {
        'climber_context': sample_climber_data,
        'trends': {
            'grade_progression': {
                'all_time': 0.5,
                'recent': 0.8
            },
            'training_consistency': 0.85,
            'activity_levels': {
                'weekly': 3,
                'monthly': 12
            }
        },
        'goals': {
            'progress': 0.6,
            'status': 'on_track',
            'time_remaining': '90 days'
        },
        'relevance': {
            'training': 0.8,
            'performance': 0.6,
            'health': 0.3
        },
        'recent_ticks': sample_ticks,
        'performance_metrics': {
            'grade_progression': 0.5
        }
    }

@pytest.fixture
def sample_user_id():
    """Generate a sample UUID for testing."""
    return uuid4()

@pytest_asyncio.fixture
async def mock_auth_user(db_session: AsyncSession):
    """Create a mock authenticated user for testing."""
    from app.models import User
    from app.core.auth import get_password_hash

    user = User(
        id=uuid4(),
        email='test@example.com',
        username='testuser',
        hashed_password=get_password_hash('TestPassword123!'),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.commit()
    return user

# ============================================================================
# DataAggregator Tests
# ============================================================================

@pytest_asyncio.fixture
async def data_aggregator(db_session):
    """Create a DataAggregator instance with a real DB session."""
    return DataAggregator(db_session)

@pytest.fixture
def sample_upload_csv():
    """Sample CSV upload content for testing."""
    return """date,route,grade,send_status
2024-02-20,Test Route,V5,sent
2024-02-19,Another Route,V4,attempted"""

class TestDataAggregator:
    @pytest.mark.asyncio
    async def test_fetch_climber_context(self, data_aggregator, db_session, sample_climber_data, sample_user_id):
        """Test fetching climber context from database."""
        async with db_session.begin():
            # First create the user
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    stripe_customer_id,
                    stripe_subscription_id,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    mountain_project_url,
                    eight_a_nu_url,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    null,
                    null,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    null,
                    null,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': sample_user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

            # Then insert the climber context
            await db_session.execute(
                text("""
                INSERT INTO climber_context (
                    id,
                    user_id, 
                    years_climbing, 
                    highest_boulder_grade_tried,
                    highest_grade_boulder_sent_clean,
                    current_training_frequency,
                    favorite_hold_types,
                    access_to_commercial_gym
                ) VALUES (
                    gen_random_uuid(),
                    :user_id,
                    :years,
                    :grade_tried,
                    :grade_sent,
                    :frequency,
                    :hold_types,
                    :access_to_commercial_gym
                )
                """),
                {
                    'user_id': sample_user_id,
                    'years': sample_climber_data['years_climbing'],
                    'grade_tried': sample_climber_data['highest_boulder_grade'],
                    'grade_sent': sample_climber_data['highest_boulder_grade'],
                    'frequency': sample_climber_data['training_frequency'],
                    'hold_types': "CRIMPS",  # Using the uppercase enum value
                    'access_to_commercial_gym': False  # Adding the required field with default value
                }
            )
        
            # Fetch result within the same transaction
            result = await data_aggregator.fetch_climber_context(sample_user_id)
        
            assert result['years_climbing'] == sample_climber_data['years_climbing']
            assert result['highest_boulder_grade_tried'] == sample_climber_data['highest_boulder_grade']
            assert result['current_training_frequency'] == sample_climber_data['training_frequency']

    @pytest.mark.asyncio
    async def test_fetch_climber_context_not_found(self, data_aggregator):
        """Test fetching non-existent climber context."""
        result = await data_aggregator.fetch_climber_context(user_id=999)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_recent_ticks(self, data_aggregator, db_session, sample_ticks, sample_user_id):
        """Test fetching recent climbing ticks."""
        async with db_session.begin():
            # First create the user
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': sample_user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

            # Then insert the tick
            await db_session.execute(
                text("""
                INSERT INTO user_ticks (
                    user_id,
                    tick_date,
                    route_name,
                    route_grade,
                    send_bool,
                    created_at
                ) VALUES (
                    :user_id,
                    :tick_date,
                    :route_name,
                    :route_grade,
                    :send_bool,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': sample_user_id,
                    'tick_date': sample_ticks[0]['date'],
                    'route_name': sample_ticks[0]['route'],
                    'route_grade': sample_ticks[0]['grade'],
                    'send_bool': sample_ticks[0]['send_status'] == 'sent'
                }
            )
        
        result = await data_aggregator.fetch_recent_ticks(user_id=sample_user_id)
        
        assert len(result) == 1
        assert result[0]['route_name'] == sample_ticks[0]['route']
        assert result[0]['route_grade'] == sample_ticks[0]['grade']

    @pytest.mark.asyncio
    async def test_fetch_recent_ticks_empty(self, data_aggregator):
        """Test fetching ticks for user with no data."""
        result = await data_aggregator.fetch_recent_ticks(user_id=999)
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_recent_ticks_custom_timeframe(self, data_aggregator, db_session, sample_ticks):
        """Test fetching ticks with custom timeframe."""
        # Insert tick from 10 days ago
        async with db_session.begin():
            # First create the user
            user_id = uuid4()
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

            await db_session.execute(
                text("""
                INSERT INTO user_ticks (
                    user_id,
                    tick_date,
                    route_name,
                    route_grade,
                    send_bool,
                    created_at
                ) VALUES (
                    :user_id,
                    :tick_date,
                    :route_name,
                    :route_grade,
                    :send_bool,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': user_id,
                    'tick_date': datetime.now() - timedelta(days=10),
                    'route_name': 'Recent Route',
                    'route_grade': 'V5',
                    'send_bool': True
                }
            )
        
        # Should not appear in 7-day results
        result = await data_aggregator.fetch_recent_ticks(user_id=user_id, days=7)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_fetch_performance_metrics(self, data_aggregator, db_session, sample_climber_data):
        """Test fetching performance metrics."""
        # First create a user tick since tick_id is required
        user_id = uuid4()
        async with db_session.begin():
            # Create user first
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

            # Insert climber context
            await db_session.execute(
                text("""
                INSERT INTO climber_context (
                    id,
                    user_id,
                    years_climbing,
                    highest_boulder_grade_tried,
                    highest_grade_boulder_sent_clean,
                    current_training_frequency,
                    favorite_hold_types,
                    access_to_commercial_gym
                ) VALUES (
                    gen_random_uuid(),
                    :user_id,
                    :years,
                    :grade_tried,
                    :grade_sent,
                    :frequency,
                    :hold_types,
                    :access_to_commercial_gym
                )
                """),
                {
                    'user_id': user_id,
                    'years': sample_climber_data['years_climbing'],
                    'grade_tried': sample_climber_data['highest_boulder_grade'],
                    'grade_sent': sample_climber_data['highest_boulder_grade'],
                    'frequency': sample_climber_data['training_frequency'],
                    'hold_types': "CRIMPS",
                    'access_to_commercial_gym': False
                }
            )
            
            # Insert a tick first
            tick_result = await db_session.execute(
                text("""
                INSERT INTO user_ticks (
                    id,
                    user_id,
                    tick_date,
                    route_name,
                    route_grade,
                    send_bool,
                    created_at
                ) VALUES (
                    DEFAULT,
                    :user_id,
                    CURRENT_DATE,
                    'Test Route',
                    'V5',
                    true,
                    CURRENT_TIMESTAMP
                ) RETURNING id
                """),
                {'user_id': user_id}
            )
            tick_id = tick_result.scalar_one()

            # Then insert performance metrics using the tick_id
            await db_session.execute(
                text("""
                INSERT INTO performance_pyramid (
                    user_id,
                    tick_id,
                    send_date,
                    location,
                    crux_angle,
                    crux_energy,
                    binned_code,
                    num_attempts,
                    days_attempts,
                    num_sends,
                    description
                ) VALUES (
                    :user_id,
                    :tick_id,
                    CURRENT_DATE,
                    :location,
                    :crux_angle,
                    :crux_energy,
                    :binned_code,
                    :num_attempts,
                    :days_attempts,
                    :num_sends,
                    :description
                )
                """),
                {
                    'user_id': user_id,
                    'tick_id': tick_id,
                    'location': 'Test Gym',
                    'crux_angle': 'VERTICAL',
                    'crux_energy': 'POWER',
                    'binned_code': 5,
                    'num_attempts': 3,
                    'days_attempts': 2,
                    'num_sends': 1,
                    'description': 'Test description'
                }
            )
        
        result = await data_aggregator.fetch_performance_metrics(user_id=user_id)
        
        assert result['binned_code'] == 5
        assert result['num_attempts'] == 3
        assert result['days_attempts'] == 2
        assert result['num_sends'] == 1
        assert result['location'] == 'Test Gym'

    @pytest.mark.asyncio
    async def test_fetch_performance_metrics_not_found(self, data_aggregator):
        """Test fetching non-existent performance metrics."""
        result = await data_aggregator.fetch_performance_metrics(user_id=999)
        assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_chat_history(self, data_aggregator, db_session):
        """Test fetching chat history."""
        now = datetime.now()
        user_id = uuid4()
        
        # Create test messages
        messages = [
            {
                'user_id': user_id,  # Use the same user_id for both messages
                'conversation_id': '1',
                'role': 'user',
                'message': 'Test message 1',
                'created_at': now - timedelta(minutes=30)
            },
            {
                'user_id': user_id,  # Use the same user_id for both messages
                'conversation_id': '1',
                'role': 'assistant',
                'message': 'Test message 2',
                'created_at': now - timedelta(minutes=20)
            }
        ]
        
        async with db_session.begin():
            # First create the user
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

            # Then insert chat history records
            for msg in messages:
                await db_session.execute(
                    text("""
                    INSERT INTO chat_history (
                        id,
                        user_id,
                        conversation_id,
                        role,
                        message,
                        created_at
                    ) VALUES (
                        gen_random_uuid(),
                        :user_id,
                        :conv_id,
                        :role,
                        :message,
                        :created_at
                    )
                    """),
                    {
                        'user_id': msg['user_id'],
                        'conv_id': msg['conversation_id'],
                        'role': msg['role'],
                        'message': msg['message'],
                        'created_at': msg['created_at']
                    }
                )
        
        result = await data_aggregator.fetch_chat_history(
            user_id=user_id,
            conversation_id=1,
            limit=10
        )
        
        assert len(result) == 2
        assert result[0]['message'] == 'Test message 2'  # Most recent first
        assert result[1]['message'] == 'Test message 1'

    @pytest.mark.asyncio
    async def test_fetch_chat_history_with_limit(self, data_aggregator, db_session):
        """Test chat history with custom limit."""
        now = datetime.now()
        
        # Create a single user first
        user_id = uuid4()
        async with db_session.begin():
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

        # Create messages using the same user_id
        messages = [
            {
                'user_id': user_id,  # Use the same user_id for all messages
                'conversation_id': '1',
                'role': 'user',
                'message': f'Message {i}',
                'created_at': now - timedelta(minutes=i)
            }
            for i in range(5)
        ]
        
        async with db_session.begin():
            for msg in messages:
                await db_session.execute(
                    text("""
                    INSERT INTO chat_history (
                        id,
                        user_id,
                        conversation_id,
                        role,
                        message,
                        created_at
                    ) VALUES (
                        gen_random_uuid(),
                        :user_id,
                        :conv_id,
                        :role,
                        :message,
                        :created_at
                    )
                    """),
                    {
                        'user_id': msg['user_id'],
                        'conv_id': msg['conversation_id'],
                        'role': msg['role'],
                        'message': msg['message'],
                        'created_at': msg['created_at']
                    }
                )
        
        result = await data_aggregator.fetch_chat_history(user_id=user_id, limit=3)
        assert len(result) == 3

    def test_parse_upload_csv(self, data_aggregator, sample_upload_csv):
        """Test parsing CSV upload data."""
        result = data_aggregator.parse_upload(sample_upload_csv, 'csv')
        
        assert len(result) == 2
        assert result[0]['grade'] == 'V5'
        assert result[1]['grade'] == 'V4'
        assert result[0]['send_status'] == 'sent'

    def test_parse_upload_json(self, data_aggregator):
        """Test parsing JSON upload data."""
        json_data = '''[
            {"date": "2024-02-20", "route": "Test Route", "grade": "V5", "send_status": "sent"},
            {"date": "2024-02-19", "route": "Another Route", "grade": "V4", "send_status": "attempted"}
        ]'''
        
        result = data_aggregator.parse_upload(json_data, 'json')
        
        assert len(result) == 2
        assert result[0]['grade'] == 'V5'
        assert result[1]['grade'] == 'V4'

    def test_parse_upload_txt(self, data_aggregator):
        """Test parsing TXT upload data."""
        txt_data = """date\troute\tgrade\tsend_status
2024-02-20\tTest Route\tV5\tsent
2024-02-19\tAnother Route\tV4\tattempted"""
        
        result = data_aggregator.parse_upload(txt_data, 'txt')
        
        assert len(result) == 2
        assert result[0]['grade'] == 'V5'
        assert result[1]['grade'] == 'V4'

    def test_parse_upload_invalid_format(self, data_aggregator):
        """Test handling invalid file format."""
        with pytest.raises(ValueError) as exc_info:
            data_aggregator.parse_upload("data", 'invalid')
        assert "Unsupported file format" in str(exc_info.value)

    def test_parse_upload_invalid_csv_columns(self, data_aggregator):
        """Test handling CSV with missing required columns."""
        invalid_csv = """route,send_status
Test Route,sent"""
        
        with pytest.raises(ValueError) as exc_info:
            data_aggregator.parse_upload(invalid_csv, 'csv')
        assert "Missing required columns" in str(exc_info.value)

    def test_parse_upload_malformed_json(self, data_aggregator):
        """Test handling malformed JSON data."""
        invalid_json = "{invalid json"
        
        with pytest.raises(ValueError) as exc_info:
            data_aggregator.parse_upload(invalid_json, 'json')
        assert "Error parsing json file" in str(exc_info.value)

    def test_deduplicate_entries(self, data_aggregator, sample_ticks):
        """Test deduplication of climbing entries."""
        new_data = [
            {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'route': 'Route1',  # Duplicate route
                'grade': 'V4',
                'send_status': 'sent'
            },
            {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'route': 'Route4',  # New route
                'grade': 'V6',
                'send_status': 'sent'
            }
        ]
        
        result = data_aggregator.deduplicate_entries(sample_ticks, new_data)
        
        assert len(result) == 4  # Original unique + new unique
        route1_entry = next(r for r in result if r['route'] == 'Route1')
        assert route1_entry['date'] == datetime.now().strftime('%Y-%m-%d')

    def test_deduplicate_entries_empty_data(self, data_aggregator):
        """Test deduplication with empty data."""
        result = data_aggregator.deduplicate_entries([], [])

    def test_deduplicate_entries_custom_timestamp(self, data_aggregator):
        """Test deduplication with custom timestamp field."""
        existing = [{'timestamp': '2024-01-01', 'route': 'Route1', 'grade': 'V4'}]
        new = [{'timestamp': '2024-01-02', 'route': 'Route1', 'grade': 'V5'}]
        
        result = data_aggregator.deduplicate_entries(
            existing,
            new,
            timestamp_field='timestamp'
        )
        
        assert len(result) == 1
        assert result[0]['grade'] == 'V5'  # Should keep newer entry

    @pytest.mark.asyncio
    async def test_aggregate_all_data(self, data_aggregator, db_session, sample_climber_data, sample_ticks):
        """Test aggregating all climber data."""
        # Setup test data
        async with db_session.begin():
            # First create the user
            user_id = uuid4()
            await db_session.execute(
                text("""
                INSERT INTO users (
                    id,
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_superuser,
                    tier,
                    payment_status,
                    stripe_webhook_verified,
                    daily_message_count,
                    created_at
                ) VALUES (
                    :user_id,
                    :username,
                    :email,
                    :password,
                    true,
                    false,
                    'FREE',
                    'INACTIVE',
                    false,
                    0,
                    CURRENT_TIMESTAMP
                )
                """),
                {
                    'user_id': user_id,
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'hashed_password_here'
                }
            )

            # Insert climber context
            await db_session.execute(
                text("""
                INSERT INTO climber_context (
                    id,
                    user_id,
                    years_climbing,
                    highest_boulder_grade_tried,
                    highest_grade_boulder_sent_clean,
                    current_training_frequency,
                    favorite_hold_types,
                    access_to_commercial_gym
                ) VALUES (
                    gen_random_uuid(),
                    :user_id,
                    :years,
                    :grade_tried,
                    :grade_sent,
                    :frequency,
                    :hold_types,
                    :access_to_commercial_gym
                )
                """),
                {
                    'user_id': user_id,
                    'years': sample_climber_data['years_climbing'],
                    'grade_tried': sample_climber_data['highest_boulder_grade'],
                    'grade_sent': sample_climber_data['highest_boulder_grade'],
                    'frequency': sample_climber_data['training_frequency'],
                    'hold_types': "CRIMPS",
                    'access_to_commercial_gym': False
                }
            )
            
            # Insert a tick first
            tick_result = await db_session.execute(
                text("""
                INSERT INTO user_ticks (
                    id,
                    user_id,
                    tick_date,
                    route_name,
                    route_grade,
                    send_bool,
                    created_at
                ) VALUES (
                    DEFAULT,
                    :user_id,
                    CURRENT_DATE,
                    'Test Route',
                    'V5',
                    true,
                    CURRENT_TIMESTAMP
                ) RETURNING id
                """),
                {'user_id': user_id}
            )
            tick_id = tick_result.scalar_one()

            # Then insert performance metrics using the tick_id
            await db_session.execute(
                text("""
                INSERT INTO performance_pyramid (
                    user_id,
                    tick_id,
                    send_date,
                    location,
                    crux_angle,
                    crux_energy,
                    binned_code,
                    num_attempts,
                    days_attempts,
                    num_sends,
                    description
                ) VALUES (
                    :user_id,
                    :tick_id,
                    CURRENT_DATE,
                    :location,
                    :crux_angle,
                    :crux_energy,
                    :binned_code,
                    :num_attempts,
                    :days_attempts,
                    :num_sends,
                    :description
                )
                """),
                {
                    'user_id': user_id,
                    'tick_id': tick_id,
                    'location': 'Test Gym',
                    'crux_angle': 'VERTICAL',
                    'crux_energy': 'POWER',
                    'binned_code': 5,
                    'num_attempts': 3,
                    'days_attempts': 2,
                    'num_sends': 1,
                    'description': 'Test description'
                }
            )
        
        result = await data_aggregator.aggregate_all_data(user_id=user_id)
        
        assert 'climber_context' in result
        assert 'recent_ticks' in result
        assert 'performance_metrics' in result
        assert 'chat_history' in result
        assert 'uploads' in result
        assert result['climber_context']['years_climbing'] == sample_climber_data['years_climbing']
        assert len(result['recent_ticks']) == 1
        assert result['performance_metrics']['binned_code'] == 5
        assert result['performance_metrics']['num_attempts'] == 3
        assert result['performance_metrics']['days_attempts'] == 2
        assert result['performance_metrics']['num_sends'] == 1

    @pytest.mark.asyncio
    async def test_aggregate_all_data_empty(self, data_aggregator):
        """Test aggregating data for user with no data."""
        result = await data_aggregator.aggregate_all_data(user_id=999)
        
        assert result['climber_context'] == {}
        assert result['recent_ticks'] == []
        assert result['performance_metrics'] == {}
        assert result['chat_history'] == []
        assert result['uploads'] == []

# ============================================================================
# ContextEnhancer Tests
# ============================================================================

@pytest.fixture
def context_enhancer():
    """Create a ContextEnhancer instance."""
    return ContextEnhancer()

class TestContextEnhancer:
    @pytest.mark.asyncio
    async def test_calculate_grade_progression(self, context_enhancer, sample_ticks):
        """Test grade progression calculation."""
        progression = await context_enhancer.calculate_grade_progression(sample_ticks, 180)
        
        assert 'all_time' in progression
        assert 'recent' in progression
        assert progression['all_time'] > 0
        assert progression['recent'] > 0

    @pytest.mark.asyncio
    async def test_calculate_grade_progression_empty(self, context_enhancer):
        """Test grade progression calculation with empty data."""
        progression = await context_enhancer.calculate_grade_progression([])
        
        assert progression['all_time'] == 0.0
        assert progression['recent'] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_grade_progression_single_tick(self, context_enhancer):
        """Test grade progression calculation with single tick."""
        single_tick = [{
            'date': datetime.now(),
            'route': 'Route1',
            'grade': 'V4',
            'send_status': 'sent'
        }]
        
        progression = await context_enhancer.calculate_grade_progression(single_tick)
        
        assert progression['all_time'] == 0.0
        assert progression['recent'] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_goal_progress(self, context_enhancer):
        """Test goal progress calculation."""
        deadline = datetime.now() + timedelta(days=180)
        
        progress = await context_enhancer.calculate_goal_progress('V5', 'V7', deadline)
        assert 0 <= progress['progress'] <= 1
        assert progress['status'] in ['on_track', 'behind', 'achieved', 'overdue']
        
        achieved = await context_enhancer.calculate_goal_progress('V5', 'V4', deadline)
        assert achieved['progress'] == 1.0
        assert achieved['status'] == 'achieved'

    @pytest.mark.asyncio
    async def test_calculate_goal_progress_overdue(self, context_enhancer):
        """Test goal progress with overdue deadline."""
        overdue_deadline = datetime.now() - timedelta(days=1)
        progress = await context_enhancer.calculate_goal_progress('V5', 'V7', overdue_deadline)
        
        assert progress['status'] == 'overdue'

    @pytest.mark.asyncio
    async def test_calculate_goal_progress_no_deadline(self, context_enhancer):
        """Test goal progress without deadline."""
        progress = await context_enhancer.calculate_goal_progress('V5', 'V7')
        
        assert 0 <= progress['progress'] <= 1
        assert progress['status'] == 'on_track'

    @pytest.mark.asyncio
    async def test_calculate_goal_progress_sport_grades(self, context_enhancer):
        """Test goal progress calculation with sport climbing grades."""
        deadline = datetime.now() + timedelta(days=180)
        
        progress = await context_enhancer.calculate_goal_progress('5.11a', '5.12a', deadline)
        assert 0 <= progress['progress'] <= 1
        assert progress['status'] in ['on_track', 'behind', 'achieved', 'overdue']

    def test_calculate_training_consistency(self, context_enhancer, sample_ticks):
        """Test training consistency calculation."""
        consistency = context_enhancer.calculate_training_consistency(sample_ticks)
        
        assert 0 <= consistency <= 1
        assert isinstance(consistency, float)

    @pytest.mark.asyncio
    async def test_enhance_context(self, context_enhancer, sample_enhanced_context):
        """Test full context enhancement."""
        enhanced = await context_enhancer.enhance_context(sample_enhanced_context)
        
        assert 'trends' in enhanced
        assert 'grade_progression' in enhanced['trends']
        assert 'training_consistency' in enhanced['trends']
        assert 'activity_levels' in enhanced['trends']
        assert 'goals' in enhanced
        assert 'relevance' not in enhanced

    @pytest.mark.asyncio
    async def test_enhance_context_with_query(self, context_enhancer, sample_enhanced_context):
        """Test context enhancement with query."""
        enhanced = await context_enhancer.enhance_context(
            sample_enhanced_context,
            query="How can I improve my training?"
        )
        
        assert 'trends' in enhanced
        assert 'relevance' in enhanced
        assert enhanced['relevance']['training'] > 0

    @pytest.mark.asyncio
    async def test_enhance_context_empty_data(self, context_enhancer):
        """Test context enhancement with empty data."""
        empty_data = {
            'climber_context': {},
            'recent_ticks': [],
            'performance_metrics': {}
        }
        
        enhanced = await context_enhancer.enhance_context(empty_data)
        
        assert 'trends' in enhanced
        assert enhanced['trends']['grade_progression']['all_time'] == 0.0
        assert enhanced['trends']['training_consistency'] == 0.0
        assert enhanced['trends']['activity_levels']['weekly'] == 0

# ============================================================================
# UnifiedFormatter Tests
# ============================================================================

@pytest.fixture
def unified_formatter():
    """Create a UnifiedFormatter instance."""
    return UnifiedFormatter()

class TestUnifiedFormatter:
    def test_determine_experience_level(self, unified_formatter):
        """Test experience level determination."""
        advanced = {'climber_context': {'years_climbing': 5, 'highest_boulder_grade': 'V8'}}
        assert unified_formatter.determine_experience_level(advanced) == 'advanced'
        
        intermediate = {'climber_context': {'years_climbing': 2, 'highest_boulder_grade': 'V5'}}
        assert unified_formatter.determine_experience_level(intermediate) == 'intermediate'
        
        beginner = {'climber_context': {'years_climbing': 1, 'highest_boulder_grade': 'V2'}}
        assert unified_formatter.determine_experience_level(beginner) == 'beginner'

    def test_determine_experience_level_edge_cases(self, unified_formatter):
        """Test experience level determination with edge cases."""
        # Empty context
        empty = {}
        assert unified_formatter.determine_experience_level(empty) == 'beginner'
        
        # Invalid grade format
        invalid_grade = {'climber_context': {'years_climbing': 1, 'highest_boulder_grade': 'invalid'}}
        assert unified_formatter.determine_experience_level(invalid_grade) == 'beginner'
        
        # High years but low grade
        mixed1 = {'climber_context': {'years_climbing': 5, 'highest_boulder_grade': 'V2'}}
        assert unified_formatter.determine_experience_level(mixed1) == 'advanced'
        
        # Low years but high grade
        mixed2 = {'climber_context': {'years_climbing': 1, 'highest_boulder_grade': 'V8'}}
        assert unified_formatter.determine_experience_level(mixed2) == 'advanced'

    def test_generate_summary(self, unified_formatter, sample_enhanced_context):
        """Test summary generation."""
        summary = unified_formatter.generate_summary(sample_enhanced_context, 'intermediate')
        
        assert isinstance(summary, str)
        assert 'intermediate climber' in summary
        assert '3 years of experience' in summary
        assert 'V5' in summary
        assert 'maintaining very consistent training' in summary

    def test_generate_summary_with_injury(self, unified_formatter, sample_enhanced_context):
        """Test summary generation with injury status."""
        sample_enhanced_context['climber_context']['injury_status'] = 'finger'
        summary = unified_formatter.generate_summary(sample_enhanced_context, 'intermediate')
        
        assert 'managing a finger injury' in summary

    def test_generate_summary_with_goals(self, unified_formatter, sample_enhanced_context):
        """Test summary generation with different goal statuses."""
        # On track
        sample_enhanced_context['goals']['status'] = 'on_track'
        summary1 = unified_formatter.generate_summary(sample_enhanced_context, 'intermediate')
        assert 'working towards V7' in summary1
        
        # Behind
        sample_enhanced_context['goals']['status'] = 'behind'
        summary2 = unified_formatter.generate_summary(sample_enhanced_context, 'intermediate')
        assert 'get back on track' in summary2

    def test_generate_summary_with_progression(self, unified_formatter, sample_enhanced_context):
        """Test summary generation with different progression scenarios."""
        # Positive progression
        sample_enhanced_context['trends']['grade_progression']['recent'] = 0.5
        summary1 = unified_formatter.generate_summary(sample_enhanced_context, 'intermediate')
        assert 'positive grade progression' in summary1
        
        # No progression
        sample_enhanced_context['trends']['grade_progression']['recent'] = 0
        summary2 = unified_formatter.generate_summary(sample_enhanced_context, 'intermediate')
        assert 'positive grade progression' not in summary2

    def test_format_performance_data(self, unified_formatter, sample_enhanced_context):
        """Test performance data formatting."""
        performance = unified_formatter.format_performance_data(sample_enhanced_context)
        
        assert 'grade_progression' in performance
        assert 'training_consistency' in performance
        assert 'activity_levels' in performance
        assert performance['grade_progression'] == sample_enhanced_context['trends']['grade_progression']
        assert performance['training_consistency'] == sample_enhanced_context['trends']['training_consistency']

    def test_format_performance_data_empty(self, unified_formatter):
        """Test performance data formatting with empty data."""
        performance = unified_formatter.format_performance_data({})
        
        assert 'grade_progression' in performance
        assert 'training_consistency' in performance
        assert 'activity_levels' in performance
        assert performance['training_consistency'] == 0

    def test_format_training_data(self, unified_formatter, sample_enhanced_context):
        """Test training data formatting."""
        training = unified_formatter.format_training_data(sample_enhanced_context)
        
        assert training['frequency'] == sample_enhanced_context['climber_context']['training_frequency']
        assert training['preferred_styles'] == sample_enhanced_context['climber_context']['preferred_styles']
        assert training['strengths'] == sample_enhanced_context['climber_context']['strengths']
        assert training['weaknesses'] == sample_enhanced_context['climber_context']['weaknesses']
        assert training['recent_focus'] == sample_enhanced_context['climber_context']['training_focus']

    def test_format_training_data_empty(self, unified_formatter):
        """Test training data formatting with empty data."""
        training = unified_formatter.format_training_data({})
        
        assert training['frequency'] == 'unknown'
        assert training['preferred_styles'] == []
        assert training['strengths'] == []
        assert training['weaknesses'] == []
        assert training['recent_focus'] == 'general'

    def test_format_health_data(self, unified_formatter, sample_enhanced_context):
        """Test health data formatting."""
        health = unified_formatter.format_health_data(sample_enhanced_context)
        
        assert health['injury_status'] == sample_enhanced_context['climber_context']['injury_status']
        assert health['energy_levels'] == sample_enhanced_context['climber_context']['energy_levels']
        assert health['sleep_quality'] == sample_enhanced_context['climber_context']['sleep_quality']

    def test_format_health_data_empty(self, unified_formatter):
        """Test health data formatting with empty data."""
        health = unified_formatter.format_health_data({})
        
        assert health['injury_status'] is None
        assert health['energy_levels'] == 'normal'
        assert health['sleep_quality'] == 'normal'

    def test_format_context(self, unified_formatter, sample_enhanced_context):
        """Test full context formatting."""
        formatted = unified_formatter.format_context(
            sample_enhanced_context,
            query="How should I improve my training?"
        )
        
        assert formatted['context_version'] == "1.0"
        assert isinstance(formatted['summary'], str)
        assert formatted['profile']['experience_level'] in ['beginner', 'intermediate', 'advanced']
        assert 'performance' in formatted
        assert 'training' in formatted
        assert 'health' in formatted
        assert 'goals' in formatted
        assert 'relevance' in formatted
        assert len(formatted['recent_activity']['ticks']) <= 10

    def test_format_context_without_query(self, unified_formatter, sample_enhanced_context):
        """Test context formatting without query."""
        formatted = unified_formatter.format_context(sample_enhanced_context)
        
        assert 'relevance' not in formatted
        assert formatted['context_version'] == "1.0"
        assert isinstance(formatted['summary'], str)

    def test_format_context_empty_data(self, unified_formatter):
        """Test context formatting with empty data."""
        formatted = unified_formatter.format_context({})
        
        assert formatted['context_version'] == "1.0"
        assert isinstance(formatted['summary'], str)
        assert formatted['profile']['experience_level'] == 'beginner'
        assert formatted['profile']['years_climbing'] == 0
        assert formatted['profile']['preferred_styles'] == []

    def test_to_json(self, unified_formatter, sample_enhanced_context):
        """Test JSON conversion."""
        formatted = unified_formatter.format_context(sample_enhanced_context)
        json_str = unified_formatter.to_json(formatted)
        
        assert isinstance(json_str, str)
        # Verify it's valid JSON by parsing it back
        parsed = json.loads(json_str)
        assert parsed['context_version'] == "1.0"
        assert isinstance(parsed['summary'], str)

    def test_to_json_with_datetime(self, unified_formatter):
        """Test JSON conversion with datetime objects."""
        data = {
            'timestamp': datetime.now(),
            'nested': {'date': datetime.now()}
        }
        json_str = unified_formatter.to_json(data)
        
        assert isinstance(json_str, str)
        # Verify it's valid JSON by parsing it back
        parsed = json.loads(json_str)
        assert 'timestamp' in parsed
        assert 'nested' in parsed
        assert 'date' in parsed['nested']

# ============================================================================
# CacheManager Tests
# ============================================================================

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.get = MagicMock()
    redis_mock.setex = MagicMock()
    redis_mock.delete = MagicMock()
    redis_mock.exists = MagicMock()
    redis_mock.expire = MagicMock()
    redis_mock.keys = MagicMock()
    return redis_mock

@pytest.fixture
def cache_manager(mock_redis):
    """Create a CacheManager instance with mock Redis."""
    return CacheManager(redis_client=mock_redis)

class TestCacheManager:
    @pytest.mark.asyncio
    async def test_get_context_success(self, cache_manager, mock_redis, sample_enhanced_context):
        """Test successful context retrieval from cache."""
        serialized_data = json.dumps(sample_enhanced_context, default=str)
        mock_redis.get.return_value = serialized_data
        
        result = await cache_manager.get_context(user_id=1, conversation_id=1)
        
        assert result is not None
        assert result['climber_context']['years_climbing'] == sample_enhanced_context['climber_context']['years_climbing']
        mock_redis.get.assert_called_once_with('context:1:1')

    @pytest.mark.asyncio
    async def test_get_context_not_found(self, cache_manager, mock_redis):
        """Test behavior when context is not found in cache."""
        mock_redis.get.return_value = None
        
        result = await cache_manager.get_context(user_id=1)
        
        assert result is None
        mock_redis.get.assert_called_once_with('context:1')

    @pytest.mark.asyncio
    async def test_get_context_redis_error(self, cache_manager, mock_redis):
        """Test error handling during context retrieval."""
        mock_redis.get.side_effect = RedisError("Connection error")
        
        result = await cache_manager.get_context(user_id=1)
        
        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_context_success(self, cache_manager, mock_redis, sample_enhanced_context):
        """Test successful context storage in cache."""
        mock_redis.setex.return_value = True
        
        result = await cache_manager.set_context(
            user_id=1,
            context_data=sample_enhanced_context,
            conversation_id=1
        )
        
        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_context_redis_error(self, cache_manager, mock_redis, sample_enhanced_context):
        """Test error handling during context storage."""
        mock_redis.setex.side_effect = RedisError("Connection error")
        
        result = await cache_manager.set_context(
            user_id=1,
            context_data=sample_enhanced_context
        )
        
        assert result is False
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_context_specific(self, cache_manager, mock_redis):
        """Test invalidation of specific context."""
        mock_redis.delete.return_value = 1
        
        result = await cache_manager.invalidate_context(user_id=1, conversation_id=1)
        
        assert result is True
        mock_redis.delete.assert_called_once_with('context:1:1')

    @pytest.mark.asyncio
    async def test_invalidate_context_all(self, cache_manager, mock_redis):
        """Test invalidation of all user contexts."""
        mock_redis.keys.return_value = ['context:1:1', 'context:1:2']
        mock_redis.delete.return_value = 2
        
        result = await cache_manager.invalidate_context(user_id=1)
        
        assert result is True
        mock_redis.keys.assert_called_once_with('context:1:*')
        mock_redis.delete.assert_called_once_with('context:1:1', 'context:1:2')

    @pytest.mark.asyncio
    async def test_refresh_ttl_success(self, cache_manager, mock_redis):
        """Test successful TTL refresh."""
        mock_redis.exists.return_value = True
        mock_redis.expire.return_value = True
        
        result = await cache_manager.refresh_ttl(user_id=1, conversation_id=1)
        
        assert result is True
        mock_redis.exists.assert_called_once_with('context:1:1')
        mock_redis.expire.assert_called_once_with('context:1:1', 3600)

    @pytest.mark.asyncio
    async def test_refresh_ttl_not_found(self, cache_manager, mock_redis):
        """Test TTL refresh when key doesn't exist."""
        mock_redis.exists.return_value = False
        
        result = await cache_manager.refresh_ttl(user_id=1)
        
        assert result is False
        mock_redis.exists.assert_called_once_with('context:1')
        mock_redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_context_from_cache(self, cache_manager, mock_redis, sample_enhanced_context):
        """Test retrieving context from cache without calling generator."""
        serialized_data = json.dumps(sample_enhanced_context, default=str)
        mock_redis.get.return_value = serialized_data
        context_generator = AsyncMock()
        
        result = await cache_manager.get_or_set_context(1, 1, context_generator)
        
        # Convert both to JSON strings for comparison to handle datetime serialization
        expected_json = json.dumps(sample_enhanced_context, default=str, sort_keys=True)
        result_json = json.dumps(result, default=str, sort_keys=True)
        assert result_json == expected_json
        context_generator.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_context_generate_new(self, cache_manager, mock_redis, sample_enhanced_context):
        """Test generating new context when not in cache."""
        mock_redis.get.return_value = None
        context_generator = AsyncMock(return_value=sample_enhanced_context)
        
        result = await cache_manager.get_or_set_context(1, 1, context_generator)
        
        assert result == sample_enhanced_context
        context_generator.assert_called_once()
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_context_merge(self, cache_manager, mock_redis):
        """Test merging of updated context data."""
        existing_data = {
            'profile': {'experience_level': 'intermediate'},
            'performance': {'grade': 'V5'}
        }
        update_data = {
            'profile': {'years_climbing': 3},
            'new_field': 'value'
        }
        serialized_existing = json.dumps(existing_data)
        mock_redis.get.return_value = serialized_existing
        mock_redis.setex.return_value = True
        
        result = await cache_manager.update_context(
            user_id=1,
            update_data=update_data,
            merge=True
        )
        
        assert result is True
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[1]
        updated_data = json.loads(call_args['value'])
        assert updated_data['profile']['experience_level'] == 'intermediate'
        assert updated_data['profile']['years_climbing'] == 3
        assert updated_data['performance']['grade'] == 'V5'
        assert updated_data['new_field'] == 'value'

    @pytest.mark.asyncio
    async def test_update_context_replace(self, cache_manager, mock_redis, sample_enhanced_context):
        """Test replacing entire context data."""
        result = await cache_manager.update_context(
            user_id=1,
            update_data=sample_enhanced_context,
            merge=False
        )
        
        assert result is True
        mock_redis.setex.assert_called_once()

    def test_deep_merge(self, cache_manager):
        """Test deep merging of dictionaries."""
        dict1 = {
            'a': 1,
            'b': {'x': 1, 'y': 2},
            'c': [1, 2, 3]
        }
        dict2 = {
            'b': {'y': 3, 'z': 4},
            'd': 4
        }
        
        result = cache_manager._deep_merge(dict1, dict2)
        
        assert result['a'] == 1
        assert result['b']['x'] == 1
        assert result['b']['y'] == 3
        assert result['b']['z'] == 4
        assert result['c'] == [1, 2, 3]
        assert result['d'] == 4

# ============================================================================
# Orchestrator Tests
# ============================================================================

@pytest.fixture
def mock_components():
    """Create mock components for the orchestrator."""
    return {
        'data_aggregator': AsyncMock(spec=DataAggregator),
        'context_enhancer': MagicMock(spec=ContextEnhancer),
        'formatter': MagicMock(spec=UnifiedFormatter),
        'cache_manager': AsyncMock(spec=CacheManager)
    }

@pytest_asyncio.fixture
async def orchestrator(db_session, redis_client, mock_components):
    """Create a test orchestrator with mocked components and real DB/Redis connections."""
    with patch('app.services.chat.context.orchestrator.DataAggregator', return_value=mock_components['data_aggregator']), \
         patch('app.services.chat.context.orchestrator.ContextEnhancer', return_value=mock_components['context_enhancer']), \
         patch('app.services.chat.context.orchestrator.UnifiedFormatter', return_value=mock_components['formatter']), \
         patch('app.services.chat.context.orchestrator.CacheManager', return_value=mock_components['cache_manager']):
        
        orchestrator = ContextOrchestrator(db_session, redis_client)
        yield orchestrator

class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_get_context_from_cache(self, orchestrator, mock_components, sample_enhanced_context):
        """Test retrieving context from cache."""
        mock_components['cache_manager'].get_or_set_context.return_value = sample_enhanced_context
        
        result = await orchestrator.get_context(user_id=1)
        
        assert result == sample_enhanced_context
        mock_components['cache_manager'].get_or_set_context.assert_called_once()
        mock_components['cache_manager'].invalidate_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_context_force_refresh(self, orchestrator, mock_components, sample_enhanced_context):
        """Test forcing context refresh."""
        mock_components['cache_manager'].get_or_set_context.return_value = sample_enhanced_context
        
        result = await orchestrator.get_context(user_id=1, force_refresh=True)
        
        assert result == sample_enhanced_context
        mock_components['cache_manager'].invalidate_context.assert_called_once_with(1, None)
        mock_components['cache_manager'].get_or_set_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context_with_query(self, orchestrator, mock_components, sample_enhanced_context):
        """Test context retrieval with query for relevance scoring."""
        context_without_relevance = {**sample_enhanced_context}
        del context_without_relevance['relevance']
        mock_components['cache_manager'].get_or_set_context.return_value = context_without_relevance
        mock_components['context_enhancer'].enhance_context.return_value = sample_enhanced_context
        mock_components['formatter'].format_context.return_value = sample_enhanced_context
        
        result = await orchestrator.get_context(user_id=1, query="How to improve?")
        
        assert result == sample_enhanced_context
        mock_components['context_enhancer'].enhance_context.assert_called_once()
        mock_components['formatter'].format_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_context(self, orchestrator, mock_components, sample_enhanced_context):
        """Test context generation process."""
        raw_data = {'some': 'data'}
        mock_components['data_aggregator'].aggregate_all_data.return_value = raw_data
        mock_components['context_enhancer'].enhance_context = AsyncMock(return_value=sample_enhanced_context)
        mock_components['formatter'].format_context = MagicMock(return_value=sample_enhanced_context)

        result = await orchestrator._generate_context(user_id=1, query="test query")

        assert result == sample_enhanced_context
        mock_components['data_aggregator'].aggregate_all_data.assert_called_once_with(1)
        mock_components['context_enhancer'].enhance_context.assert_called_once_with(raw_data, "test query")
        mock_components['formatter'].format_context.assert_called_once_with(mock_components['context_enhancer'].enhance_context.return_value, "test query")

    @pytest.mark.asyncio
    async def test_update_relevance(self, orchestrator, mock_components, sample_enhanced_context):
        """Test updating context relevance scores."""
        mock_components['context_enhancer'].enhance_context.return_value = sample_enhanced_context
        mock_components['formatter'].format_context.return_value = sample_enhanced_context
        mock_components['cache_manager'].update_context.return_value = True
        
        result = await orchestrator._update_relevance(
            context=sample_enhanced_context,
            query="test query",
            user_id=1,
            conversation_id=1
        )
        
        assert result == sample_enhanced_context
        mock_components['context_enhancer'].enhance_context.assert_called_once_with(
            sample_enhanced_context, 
            "test query"
        )
        mock_components['cache_manager'].update_context.assert_called_once_with(
            1, 
            sample_enhanced_context, 
            1, 
            merge=True
        )

    @pytest.mark.asyncio
    async def test_handle_data_update(self, orchestrator, mock_components):
        """Test handling data updates and cache invalidation."""
        update_data = {'new_field': 'value'}
        mock_components['cache_manager'].set_context.return_value = True
        
        result = await orchestrator.handle_data_update(
            user_id=1,
            update_type='climber_context',
            update_data=update_data
        )
        
        assert result is True
        mock_components['cache_manager'].invalidate_context.assert_called_once_with(1, None)
        mock_components['cache_manager'].set_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_data_update_error(self, orchestrator, mock_components):
        """Test error handling during data update."""
        mock_components['cache_manager'].invalidate_context.side_effect = Exception("Test error")
        
        result = await orchestrator.handle_data_update(
            user_id=1,
            update_type='climber_context',
            update_data={}
        )
        
        assert result is False
        mock_components['cache_manager'].invalidate_context.assert_called_once()
        mock_components['cache_manager'].set_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_context(self, orchestrator, mock_components, sample_enhanced_context):
        """Test context refresh functionality."""
        mock_components['data_aggregator'].aggregate_all_data.return_value = {'raw': 'data'}
        mock_components['context_enhancer'].enhance_context.return_value = sample_enhanced_context
        mock_components['formatter'].format_context.return_value = sample_enhanced_context
        mock_components['cache_manager'].set_context.return_value = True
        
        result = await orchestrator.refresh_context(user_id=1, conversation_id=1)
        
        assert result is True
        mock_components['data_aggregator'].aggregate_all_data.assert_called_once()
        mock_components['cache_manager'].set_context.assert_called_once_with(
            1,
            sample_enhanced_context,
            1
        )

    @pytest.mark.asyncio
    async def test_refresh_context_error(self, orchestrator, mock_components):
        """Test error handling during context refresh."""
        mock_components['data_aggregator'].aggregate_all_data.side_effect = Exception("Test error")
        
        result = await orchestrator.refresh_context(user_id=1)
        
        assert result is False
        mock_components['data_aggregator'].aggregate_all_data.assert_called_once()
        mock_components['cache_manager'].set_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_refresh_contexts(self, orchestrator, mock_components, sample_enhanced_context):
        """Test bulk context refresh functionality."""
        mock_components['data_aggregator'].aggregate_all_data.return_value = {'raw': 'data'}
        mock_components['context_enhancer'].enhance_context = AsyncMock(return_value=sample_enhanced_context)
        mock_components['formatter'].format_context = MagicMock(return_value=sample_enhanced_context)
        mock_components['cache_manager'].set_context.return_value = True
        
        results = await orchestrator.bulk_refresh_contexts([1, 2, 3], batch_size=2)
        
        assert len(results) == 3
        assert all(results.values())
        assert mock_components['data_aggregator'].aggregate_all_data.call_count == 3
        assert mock_components['cache_manager'].set_context.call_count == 3 

# ============================================================================
# API Endpoint Tests
# ============================================================================

@pytest.fixture
def sample_context_response():
    """Sample context response for testing."""
    return {
        "context_version": "1.0",
        "summary": "You've climbed for 3 years, focusing on bouldering. Your highest send is V5.",
        "profile": {
            "years_climbing": 3,
            "total_climbs": 200
        },
        "performance": {
            "highest_boulder_grade": "V5"
        },
        "trends": {
            "grade_progression_all_time": 0.5,
            "grade_progression_6mo": 0.8
        },
        "relevance": {
            "training": "goal-driven"
        },
        "goals": {
            "climbing_goals": "Send V8 by December"
        },
        "uploads": []
    }

@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, mock_auth_user, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated test client."""
    # Create access token for mock user
    from app.core.auth import create_access_token
    
    access_token = await create_access_token(
        subject=str(mock_auth_user.id),
        scopes=["user"],
        jti=str(uuid4()),
        db=db_session
    )
    
    # Create a new client with auth headers
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    yield client

@pytest.mark.asyncio
class TestContextEndpoints:
    async def test_get_context(self, auth_client, mock_auth_user, sample_context_response):
        """Test GET /{user_id} endpoint."""
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.get_context = AsyncMock(return_value=sample_context_response)
            
            response = await auth_client.get(
                f"/api/v1/context/{mock_auth_user.id}",
                params={"query": "training advice", "force_refresh": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["context_version"] == "1.0"
            assert "summary" in data
            assert "profile" in data
            assert "performance" in data
            
            mock_instance.get_context.assert_called_once_with(
                user_id=str(mock_auth_user.id),
                query="training advice",
                force_refresh=False
            )

    async def test_get_context_not_found(self, auth_client, mock_auth_user):
        """Test GET /{user_id} endpoint when context not found."""
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.get_context = AsyncMock(return_value=None)
            
            response = await auth_client.get(f"/api/v1/context/{mock_auth_user.id}")
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()

    async def test_refresh_context(self, auth_client, mock_auth_user):
        """Test POST /{user_id}/refresh endpoint."""
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.refresh_context = AsyncMock(return_value=True)
            
            response = await auth_client.post(f"/api/v1/context/{mock_auth_user.id}/refresh")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Context refresh initiated successfully"
            
            mock_instance.refresh_context.assert_called_once_with(
                user_id=str(mock_auth_user.id)
            )

    async def test_update_context(self, auth_client, mock_auth_user, sample_context_response):
        """Test PATCH /{user_id} endpoint."""
        update_payload = {
            "updates": {
                "profile": {"years_climbing": 4},
                "goals": {"new_goal": "V7 by June"}
            },
            "replace": False
        }
        
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.handle_data_update = AsyncMock(return_value=sample_context_response)
            
            response = await auth_client.patch(
                f"/api/v1/context/{mock_auth_user.id}",
                json=update_payload
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["context_version"] == "1.0"
            
            mock_instance.handle_data_update.assert_called_once_with(
                user_id=str(mock_auth_user.id),
                updates=update_payload["updates"],
                replace=update_payload["replace"]
            )

    async def test_update_context_not_found(self, auth_client, mock_auth_user):
        """Test PATCH /{user_id} endpoint when context not found."""
        update_payload = {
            "updates": {"profile": {"years_climbing": 4}},
            "replace": False
        }
        
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.handle_data_update = AsyncMock(return_value=None)
            
            response = await auth_client.patch(
                f"/api/v1/context/{mock_auth_user.id}",
                json=update_payload
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()

    async def test_bulk_refresh_contexts(self, auth_client, mock_auth_user):
        """Test POST /bulk-refresh endpoint."""
        user_ids = ["user1", "user2", "user3"]
        
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.bulk_refresh_contexts = AsyncMock(return_value=True)
            
            response = await auth_client.post(
                "/api/v1/context/bulk-refresh",
                params={"user_ids": user_ids}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Bulk context refresh initiated successfully"
            
            mock_instance.bulk_refresh_contexts.assert_called_once_with(
                user_ids=user_ids
            )

    async def test_bulk_refresh_contexts_no_ids(self, auth_client, mock_auth_user):
        """Test POST /bulk-refresh endpoint without user IDs."""
        with patch('app.api.v1.endpoints.context.ContextOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.bulk_refresh_contexts = AsyncMock(return_value=True)
            
            response = await auth_client.post("/api/v1/context/bulk-refresh")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Bulk context refresh initiated successfully"
            
            mock_instance.bulk_refresh_contexts.assert_called_once_with(
                user_ids=None
            )

    async def test_unauthorized_access(self, client):
        """Test endpoints without authentication."""
        # Test each endpoint
        endpoints = [
            ("GET", "/api/v1/context/123"),
            ("POST", "/api/v1/context/123/refresh"),
            ("PATCH", "/api/v1/context/123"),
            ("POST", "/api/v1/context/bulk-refresh")
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint)
            elif method == "PATCH":
                response = await client.patch(endpoint, json={"updates": {}})
            
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            assert "not authenticated" in data["detail"].lower()

    async def test_validation_errors(self, auth_client, mock_auth_user):
        """Test input validation for endpoints."""
        # Test invalid update payload
        invalid_payload = {
            "updates": "not_a_dict",  # Should be a dict
            "replace": "not_a_bool"   # Should be a boolean
        }
        
        response = await auth_client.patch(
            f"/api/v1/context/{mock_auth_user.id}",
            json=invalid_payload
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        
        # Test invalid query parameters
        response = await auth_client.get(
            f"/api/v1/context/{mock_auth_user.id}",
            params={"force_refresh": "not_a_bool"}  # Should be a boolean
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        
        # Test invalid update payload
        invalid_payload = {
            "updates": "not_a_dict",  # Should be a dict
            "replace": "not_a_bool"   # Should be a boolean
        }
        
        response = await auth_client.patch(
            f"/api/v1/context/{mock_auth_user.id}",
            json=invalid_payload
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        
        # Test invalid query parameters
        response = await auth_client.get(
            f"/api/v1/context/{mock_auth_user.id}",
            params={"force_refresh": "not_a_bool"}  # Should be a boolean
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data 