"""Tests for the Logbook Orchestrator service."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, Mock, patch
import pandas as pd
from uuid import UUID, uuid4
from datetime import datetime, timezone
from io import StringIO
import logging

from app.core.logging import logger
from app.services.logbook.orchestrator import LogbookOrchestrator
from app.services.logbook.gateways.mp_csv_client import MountainProjectCSVClient
from app.services.logbook.gateways.eight_a_nu_scraper import EightANuClient
from app.models.enums import LogbookType, ClimbingDiscipline
from app.core.exceptions import DataSourceError, ScrapingError
from app.models.climbing import UserTicks, PerformancePyramid, Tag
from app.models import User
from app.core.exceptions import DatabaseError

# Sample test data
SAMPLE_MP_CSV = '''Date,Route,Rating,Notes,URL,Pitches,Location,Avg Stars,Your Stars,Style,Lead Style,Route Type,Your Rating,Length,Rating Code
3/23/2024,Balkan Dirt Diving,5.12a,"Awesome climb, not over after crux beginning.",https://www.mountainproject.com/route/105749977/balkan-dirt-diving,2,Colorado > Golden > Clear Creek Canyon > The Sports Wall,3.5,3,Lead,Onsight,Sport,,80,6600
3/23/2024,Generation Gap,5.11a,"Great climb, wet crux tho ",https://www.mountainproject.com/route/105749971/generation-gap,2,Colorado > Golden > Clear Creek Canyon > The Sports Wall,2.3,2,Lead,Fell/Hung,Sport,,70,4600
2/6/2024,Weapons Of Mass Arousal,5.12b/c,"Checked beta at end of long day. Start matched in lieback, at end of first boulder really think of rocking over left foot to bump left hand. Also don't slap for finish jug, my right hand looks like I spanked a porcupine lol",https://www.mountainproject.com/route/107901794/weapons-of-mass-arousal,1,Colorado > Canon City > Shelf Road > Spiney Ridge,3.4,4,TR,,Sport,,,7100'''

# Sample 8a.nu ascent data matching actual API response
SAMPLE_EIGHT_A_ASCENTS = {
    "ascents": [
        {
            "ascentId": 9605213,
            "platform": "eight_a",
            "userAvatar": "https://d1ffqbcmevre4q.cloudfront.net/avatar_default.png",
            "userName": "sam rocks",
            "userSlug": "sam-rocks",
            "date": "2025-02-15T12:00:00+00:00",
            "difficulty": "6C",
            "comment": "test",
            "userPrivate": False,
            "countrySlug": "united-states",
            "countryName": "United States",
            "areaSlug": "boulder-co",
            "areaName": "Boulder/CO",
            "sectorSlug": "satellites",
            "sectorName": "Satellites",
            "traditional": False,
            "firstAscent": False,
            "chipped": False,
            "withKneepad": False,
            "badAnchor": False,
            "badBolts": False,
            "highFirstBolt": False,
            "looseRock": False,
            "badClippingPosition": False,
            "isHard": False,
            "isSoft": False,
            "isBoltedByMe": False,
            "isOverhang": False,
            "isVertical": False,
            "isSlab": False,
            "isRoof": False,
            "isAthletic": False,
            "isEndurance": False,
            "isCrimpy": False,
            "isCruxy": False,
            "isSloper": False,
            "isTechnical": False,
            "type": "rp",
            "repeat": False,
            "project": False,
            "rating": 4,
            "category": 0,
            "recommended": True,
            "secondGo": False,
            "duplicate": False,
            "isDanger": False,
            "zlagGradeIndex": 21,
            "zlaggableName": "Zero G",
            "zlaggableSlug": "zero-g-5d29a",
            "cragSlug": "flatirons",
            "cragName": "Flatirons"
        },
        {
            "ascentId": 9605212,
            "platform": "eight_a",
            "userAvatar": "https://d1ffqbcmevre4q.cloudfront.net/avatar_default.png",
            "userName": "sam rocks",
            "userSlug": "sam-rocks",
            "date": "2025-02-18T12:00:00+00:00",
            "difficulty": "6B+",
            "comment": "test",
            "userPrivate": False,
            "countrySlug": "united-states",
            "countryName": "United States",
            "areaSlug": "boulder-co",
            "areaName": "Boulder/CO",
            "sectorSlug": "satellites",
            "sectorName": "Satellites",
            "traditional": False,
            "firstAscent": True,
            "chipped": True,
            "withKneepad": True,
            "badAnchor": False,
            "badBolts": False,
            "highFirstBolt": False,
            "looseRock": True,
            "badClippingPosition": False,
            "isHard": False,
            "isSoft": True,
            "isBoltedByMe": False,
            "isOverhang": True,
            "isVertical": True,
            "isSlab": True,
            "isRoof": True,
            "isAthletic": True,
            "isEndurance": True,
            "isCrimpy": True,
            "isCruxy": True,
            "isSloper": True,
            "isTechnical": True,
            "type": "os",
            "repeat": False,
            "project": False,
            "rating": 3,
            "category": 1,
            "recommended": True,
            "secondGo": False,
            "duplicate": False,
            "isDanger": False,
            "zlagGradeIndex": 19,
            "zlaggableName": "Original Grapple",
            "zlaggableSlug": "original-grapple-dba9b",
            "cragSlug": "flatirons",
            "cragName": "Flatirons"
        }
    ],
    "totalItems": 2,
    "pageIndex": 0
}

@pytest_asyncio.fixture
async def mock_mp_client() -> AsyncGenerator[AsyncMock, None]:
    """Create a mock Mountain Project client."""
    with patch('app.services.logbook.gateways.mp_csv_client.MountainProjectCSVClient') as mock:
        client = AsyncMock(spec=MountainProjectCSVClient)
        mock.return_value.__aenter__.return_value = client
        
        # Setup sample dataframe
        df = pd.read_csv(StringIO(SAMPLE_MP_CSV))
        client.fetch_user_ticks.return_value = df
        
        yield client

@pytest_asyncio.fixture
async def mock_eight_a_client() -> AsyncGenerator[AsyncMock, None]:
    """Create a mock 8a.nu client."""
    with patch('app.services.logbook.gateways.eight_a_nu_scraper.EightANuClient') as mock:
        client = AsyncMock(spec=EightANuClient)
        mock.return_value.__aenter__.return_value = client
        
        # Setup mock authentication
        client.authenticate = AsyncMock()  # Will return None successfully
        
        # Setup sample response with full ascent data
        client.get_ascents.return_value = SAMPLE_EIGHT_A_ASCENTS
        
        yield client

@pytest_asyncio.fixture
async def mock_db_service() -> AsyncGenerator[AsyncMock, None]:
    """Create a mock database service that accurately reflects the real DatabaseService."""
    with patch('app.services.logbook.database_service.DatabaseService') as mock:
        service = AsyncMock()
        mock.return_value = service
        
        # Mock UserTicks objects with tag relationship
        mock_ticks = [
            Mock(
                spec=UserTicks,
                id=uuid4(),
                user_id=None,  # Will be set when save_user_ticks is called
                route_name="Test Route",
                route_grade="5.12a",
                tick_date=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                style="Lead",
                route_type="Sport",
                tags=[]  # Initialize empty tags list
            )
        ]
        
        # Mock PerformancePyramid objects
        mock_pyramids = [
            Mock(
                spec=PerformancePyramid,
                id=uuid4(),
                user_id=None,
                discipline=ClimbingDiscipline.SPORT,
                grade_range="5.12",
                required_ticks=10,
                current_ticks=5
            )
        ]
        
        # Mock Tag objects with tick relationship
        mock_tags = [
            Mock(
                spec=Tag,
                id=uuid4(),
                name="Crimpy",
                ticks=[]  # Initialize empty ticks list
            ),
            Mock(
                spec=Tag,
                id=uuid4(),
                name="Project",
                ticks=[]
            ),
            Mock(
                spec=Tag,
                id=uuid4(),
                name="Steep",
                ticks=[]
            )
        ]
        
        # Set up relationships
        mock_ticks[0].tags = mock_tags
        for tag in mock_tags:
            tag.ticks = mock_ticks
        
        # Setup mock returns for database operations
        service.save_user_ticks.return_value = mock_ticks
        service.save_performance_pyramid.return_value = mock_pyramids
        service.save_tags.return_value = mock_tags
        service.get_user_ticks.return_value = mock_ticks
        service.get_performance_pyramid.return_value = mock_pyramids
        
        # Mock error cases
        async def save_user_ticks_with_error_handling(ticks_data, user_id):
            if not ticks_data:
                raise DatabaseError("No tick data provided")
            # Add missing fields to the mock ticks
            for tick in ticks_data:
                tick['user_id'] = user_id
            return ticks_data
        
        async def save_performance_pyramid_with_error_handling(pyramid_data, user_id):
            if not pyramid_data:
                # Return empty list instead of raising error
                return []
            return mock_pyramids
        
        async def save_tags_with_error_handling(tag_names, tick_ids):
            if not tag_names or not tick_ids:
                raise DatabaseError("Missing tag names or tick IDs")
            # Filter mock tags based on provided names
            return [tag for tag in mock_tags if tag.name in tag_names]
        
        async def update_sync_timestamp_with_error_handling(user_id, logbook_type):
            if not user_id:
                raise DatabaseError("User ID not provided")
            return None
        
        # Assign error handling mocks
        service.save_user_ticks.side_effect = save_user_ticks_with_error_handling
        service.save_performance_pyramid.side_effect = save_performance_pyramid_with_error_handling
        service.save_tags.side_effect = save_tags_with_error_handling
        service.update_sync_timestamp.side_effect = update_sync_timestamp_with_error_handling
        
        # Mock cleanup method
        service.cleanup = AsyncMock()
        
        # Mock class method get_instance
        mock.get_instance = AsyncMock()
        mock.get_instance.return_value = service
        
        yield service

@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    """Create a test user for the tests."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        hashed_password="testpassword",
        is_active=True,
        is_superuser=False,
        mtn_project_last_sync=None,
        eight_a_last_sync=None
    )
    
    # Save user to database
    db_session.add(user)
    await db_session.flush()
    
    return user

@pytest.mark.asyncio
@patch('app.services.logbook.orchestrator.DatabaseService')
async def test_process_mountain_project_data(
    mock_db_class,
    db_session,
    mock_mp_client: AsyncMock,
    mock_db_service: AsyncMock,
    test_user: User
) -> None:
    """Test processing Mountain Project logbook data."""
    # Setup database service mock
    mock_db_class.return_value = mock_db_service
    mock_db_class.get_instance.return_value = mock_db_service
    
    # Create orchestrator with mocked services
    orchestrator = LogbookOrchestrator(db_session)
    
    # Patch Mountain Project client
    with patch('app.services.logbook.orchestrator.MountainProjectCSVClient') as mock_client_class:
        # Setup the mock to return our mock client
        mock_client_class.return_value.__aenter__.return_value = mock_mp_client
        
        # Test successful processing
        ticks, pyramids, tags = await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType.MOUNTAIN_PROJECT,
            profile_url="https://www.mountainproject.com/user/test"
        )
        
        # Verify client calls
        mock_mp_client.fetch_user_ticks.assert_awaited_once()
        
        # Verify database operations with user context
        mock_db_service.save_user_ticks.assert_awaited_once()
        mock_db_service.save_performance_pyramid.assert_awaited_once()
        mock_db_service.update_sync_timestamp.assert_awaited_once_with(
            test_user.id,
            LogbookType.MOUNTAIN_PROJECT
        )
        
        # Verify returned data structure
        assert len(ticks) > 0
        assert len(pyramids) > 0
        
        # Verify required fields from processor
        first_tick = ticks[0]
        processor_fields = {
            'route_name', 'route_grade', 'tick_date', 'length', 'pitches',
            'route_url', 'notes', 'location', 'location_raw', 'lead_style',
            'route_quality', 'user_quality', 'logbook_type'
        }
        logger.debug("First tick fields", extra={"fields": list(first_tick.keys())})
        logger.debug("Missing fields", extra={"fields": [field for field in processor_fields if field not in first_tick]})
        assert all(field in first_tick for field in processor_fields)
        
        # Verify fields added by orchestrator
        orchestrator_fields = {
            'discipline', 'send_bool', 'length_category', 'season_category',
            'binned_grade', 'binned_code', 'difficulty_category',
            'cur_max_rp_sport', 'cur_max_rp_trad', 'cur_max_boulder'
        }
        assert all(field in first_tick for field in orchestrator_fields)
        
        # Verify data types
        assert isinstance(first_tick['route_name'], str)
        assert isinstance(first_tick['route_grade'], str)
        assert isinstance(first_tick['tick_date'], (str, pd.Timestamp))
        assert isinstance(first_tick['send_bool'], bool)
        assert isinstance(first_tick['length'], int)
        assert isinstance(first_tick['pitches'], int)
        
        # Verify user association
        for tick in mock_db_service.save_user_ticks.call_args[0][0]:
            assert tick.get('user_id') == test_user.id
            
        # Test malformed data handling
        mock_mp_client.fetch_user_ticks.reset_mock()
        mock_mp_client.fetch_user_ticks.return_value = pd.DataFrame({
            'date': ['2024-03-23'],
            'route': ['Test Route'],
            'rating': ['Invalid Grade'],  # Test invalid grade handling
            'notes': ['Test notes'],
            'url': ['https://www.mountainproject.com/route/test'],
            'pitches': [1],
            'location': ['Area > Region > Crag'],
            'avg_stars': [3.5],  # Will be normalized to 0.875 (3.5/4)
            'your_stars': [4.0],  # Will be normalized to 1.0 (4/4)
            'style': ['Lead'],
            'lead_style': ['Onsight'],
            'route_type': ['Sport'],
            'your_rating': [''],  # Empty string for no rating
            'length': [30],
            'rating_code': ['1234']  # Added missing rating code
        })
        
        # Should still process without error, invalid grade will be handled
        ticks, pyramids, tags = await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType.MOUNTAIN_PROJECT,
            profile_url="test"
        )
        assert len(ticks) > 0
        
        # Test empty data handling
        mock_mp_client.fetch_user_ticks.reset_mock()
        mock_mp_client.fetch_user_ticks.return_value = pd.DataFrame()

        with pytest.raises(DataSourceError) as exc_info:
            await orchestrator.process_logbook_data(
                user_id=test_user.id,
                logbook_type=LogbookType.MOUNTAIN_PROJECT,
                profile_url="test"
            )
        assert "No data found in Mountain Project CSV" in str(exc_info.value)
        
        # Test 8a.nu location handling
        mock_mp_client.fetch_user_ticks.reset_mock()
        mock_mp_client.fetch_user_ticks.side_effect = None
        mock_mp_client.fetch_user_ticks.return_value = pd.DataFrame({
            'route': ['Test Route'],
            'rating': ['5.12a'],
            'date': ['2024-03-23'],
            'style': ['Lead'],
            'route_type': ['Sport'],
            'length': [30],
            'pitches': [1],
            'location': ['Invalid Location'],  # Location without '>' separator
            'avg_stars': [3.5],
            'your_stars': [4.0],
            'lead_style': ['Onsight'],
            'notes': ['Test notes'],
            'url': ['https://www.mountainproject.com/route/test']
        })
        
        # Should process without error, location should be used as-is
        ticks, pyramids, tags = await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType.MOUNTAIN_PROJECT,
            profile_url="test"
        )
        
        # Verify location processing
        assert len(ticks) > 0
        assert ticks[0]['location'] == 'Invalid Location'
        assert ticks[0]['location_raw'] is None

        # Test client connection error
        mock_mp_client.fetch_user_ticks.reset_mock()
        mock_mp_client.fetch_user_ticks.side_effect = ConnectionError("Failed to connect to Mountain Project")

        with pytest.raises(DataSourceError) as exc_info:
            await orchestrator.process_logbook_data(
                user_id=test_user.id,
                logbook_type=LogbookType.MOUNTAIN_PROJECT,
                profile_url="test"
            )
        assert "Failed to connect to Mountain Project" in str(exc_info.value)

@pytest.mark.asyncio
async def test_process_eight_a_nu_data(
    db_session,
    mock_eight_a_client: AsyncMock,
    mock_db_service: AsyncMock,
    test_user: User
) -> None:
    """Test processing 8a.nu logbook data with comprehensive validation."""
    # Setup orchestrator with mocked services
    orchestrator = LogbookOrchestrator(db_session, db_service=mock_db_service)
    
    # Define sample ascent data matching actual API response
    SAMPLE_ASCENTS = [
        {
            # Sport redpoint with full features
            "ascentId": 9605224,
            "platform": "eight_a",
            "userAvatar": "https://d1ffqbcmevre4q.cloudfront.net/avatar_default.png",
            "userName": "test user",
            "userSlug": "test-user",
            "date": "2024-03-23T12:00:00+00:00",
            "difficulty": "7a+",
            "comment": "Perfect conditions, stuck the crux first try!",
            "userPrivate": False,
            "countrySlug": "united-states",
            "countryName": "United States",
            "areaSlug": "test-area",
            "areaName": "Test Area",
            "sectorSlug": "test-sector",
            "sectorName": "Test Sector",
            "traditional": False,
            "firstAscent": False,
            "type": "rp",
            "repeat": False,
            "project": False,
            "rating": 4,
            "category": 0,  # Sport
            "recommended": True,
            "zlagGradeIndex": 24,
            "zlaggableName": "Test Route",
            "zlaggableSlug": "test-route",
            "cragSlug": "test-crag",
            "cragName": "Test Crag",
            "isOverhang": True,
            "isCrimpy": True,
            "isEndurance": True
        },
        {
            # Boulder project with different characteristics
            "ascentId": 9605225,
            "platform": "eight_a",
            "userAvatar": "https://d1ffqbcmevre4q.cloudfront.net/avatar_default.png",
            "userName": "test user",
            "userSlug": "test-user",
            "date": "2024-03-24T12:00:00+00:00",
            "difficulty": "7C",
            "comment": "Close! Just need to dial in the heel hook beta",
            "userPrivate": False,
            "countrySlug": "united-states",
            "countryName": "United States",
            "areaSlug": "boulder-area",
            "areaName": "Boulder Area",
            "sectorSlug": "boulder-sector",
            "sectorName": "Boulder Sector",
            "traditional": False,
            "firstAscent": False,
            "type": "attempt",
            "repeat": False,
            "project": True,
            "rating": 5,
            "category": 1,  # Boulder
            "recommended": True,
            "zlagGradeIndex": 28,
            "zlaggableName": "Project Boulder",
            "zlaggableSlug": "project-boulder",
            "cragSlug": "boulder-crag",
            "cragName": "Boulder Crag",
            "isRoof": True,
            "isAthletic": True,
            "withKneepad": True
        },
        {
            # Traditional onsight with warnings
            "ascentId": 9605226,
            "platform": "eight_a",
            "userAvatar": "https://d1ffqbcmevre4q.cloudfront.net/avatar_default.png",
            "userName": "test user",
            "userSlug": "test-user",
            "date": "2024-03-25T12:00:00+00:00",
            "difficulty": "6c",
            "comment": "Classic line but watch out for loose blocks",
            "userPrivate": False,
            "countrySlug": "united-states",
            "countryName": "United States",
            "areaSlug": "trad-area",
            "areaName": "Trad Area",
            "sectorSlug": "trad-sector",
            "sectorName": "Trad Sector",
            "traditional": True,
            "firstAscent": False,
            "type": "os",
            "repeat": False,
            "project": False,
            "rating": 3,
            "category": 0,  # Sport (but marked as traditional)
            "recommended": False,
            "zlagGradeIndex": 22,
            "zlaggableName": "Trad Classic",
            "zlaggableSlug": "trad-classic",
            "cragSlug": "trad-crag",
            "cragName": "Trad Crag",
            "isTechnical": True,
            "looseRock": True,
            "highFirstBolt": True
        }
    ]
    
    # Test successful processing
    with patch('app.services.logbook.orchestrator.EightANuClient') as mock_client_class:
        # Setup the mock to return our mock client
        mock_client_class.return_value.__aenter__.return_value = mock_eight_a_client
        
        # Setup mock response with sample ascents
        mock_eight_a_client.get_ascents.return_value = {
            "ascents": SAMPLE_ASCENTS,
            "totalItems": 3,
            "pageIndex": 0
        }
        
        # Process logbook data
        ticks, pyramids, tags = await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType.EIGHT_A_NU,
            username="test_user",
            password="test_pass"
        )
        
        # Verify normalized data structure before final processing
        # Get the normalized data from the mock_db_service save call
        normalized_ticks = mock_db_service.save_user_ticks.call_args[0][0]
        
        # Expected normalized structures for each tick type
        expected_sport_tick = {
            'user_id': test_user.id,
            'route_name': "Test Route",
            'route_grade': "5.12a",  # Converted from French 7a+
            'tick_date': pd.Timestamp("2024-03-23T12:00:00+00:00"),
            'notes': "Perfect conditions, stuck the crux first try! | #recommended #overhang #crimpy #endurance",
            'lead_style': "Redpoint",
            'send_bool': True,
            'location': "Test Crag, Test Area",
            'location_raw': None,  # 8a.nu doesn't provide detailed location hierarchy
            'route_quality': 0.8,  # 4/5 normalized
            'user_quality': 0.8,  # 4/5 normalized
            'logbook_type': LogbookType.EIGHT_A_NU,
            'length': 0,  # 8a.nu doesn't provide length
            'pitches': 1,  # Default for 8a.nu
            'discipline': ClimbingDiscipline.SPORT,
            'binned_code': 17,  # Code for 5.12a
            'binned_grade': "5.12-",  # Plus/minus version of 5.12a
            'cur_max_rp_sport': 17,  # Max sport grade is 5.12a (code 17)
            'cur_max_rp_trad': 0,  # No trad sends yet at this point
            'cur_max_boulder': 0,  # No boulder sends yet at this point
            'difficulty_category': 'Project',  # Set by the classifier
            'length_category': 'Unknown',  # 8a.nu doesn't provide length information
            'season_category': 'Spring, 2024',  # Set by the classifier based on date
        }
        
        expected_boulder_tick = {
            'user_id': test_user.id,
            'route_name': "Project Boulder",
            'route_grade': "V9",  # Converted from Font 7C
            'tick_date': pd.Timestamp("2024-03-24T12:00:00+00:00"),
            'notes': "Close! Just need to dial in the heel hook beta | #recommended #roof #athletic #kneebar",
            'lead_style': "Project",
            'send_bool': False,
            'location': "Boulder Crag, Boulder Area",
            'location_raw': None,  # 8a.nu doesn't provide detailed location hierarchy
            'route_quality': 1.0,  # 5/5 normalized
            'user_quality': 1.0,  # 5/5 normalized
            'logbook_type': LogbookType.EIGHT_A_NU,
            'length': 0,
            'pitches': 1,
            'discipline': ClimbingDiscipline.BOULDER,
            'binned_code': 111,  # Code for V9
            'binned_grade': "V9",  # Plus/minus version of V9
            'cur_max_rp_sport': 17,  # Inherited from previous sport send
            'cur_max_rp_trad': 0,  # No trad sends yet at this point
            'cur_max_boulder': 0,  # Not a send, so doesn't count for max
            'difficulty_category': 'Project',  # Set by the classifier
            'length_category': 'Unknown',  # 8a.nu doesn't provide length information
            'season_category': 'Spring, 2024',  # Set by the classifier based on date
        }
        
        expected_trad_tick = {
            'user_id': test_user.id,
            'route_name': "Trad Classic",
            'route_grade': "5.11a",  # Converted from French 6c
            'tick_date': pd.Timestamp("2024-03-25T12:00:00+00:00"),
            'notes': "Classic line but watch out for loose blocks | #trad #technical #looserock #highfirstbolt",
            'lead_style': "Onsight Trad",
            'send_bool': True,
            'location': "Trad Crag, Trad Area",
            'location_raw': None,  # 8a.nu doesn't provide detailed location hierarchy
            'route_quality': 0.6,  # 3/5 normalized
            'user_quality': 0.6,  # 3/5 normalized
            'logbook_type': LogbookType.EIGHT_A_NU,
            'length': 0,
            'pitches': 1,
            'discipline': ClimbingDiscipline.TRAD,  # Now correctly set to TRAD
            'binned_code': 14,  # Code for 5.11a
            'binned_grade': "5.11-",  # Plus/minus version of 5.11a
            'cur_max_rp_sport': 17,  # Inherited from previous sport send
            'cur_max_rp_trad': 14,  # Max trad grade is 5.11a (code 14)
            'cur_max_boulder': 0,  # No boulder sends
            'difficulty_category': 'Project',  # Now matches our consistent categorization logic
            'length_category': 'Unknown',  # 8a.nu doesn't provide length information
            'season_category': 'Spring, 2024',  # Set by the classifier based on date
        }
        
        # Find each normalized tick in the saved data
        sport_tick = next(t for t in normalized_ticks if t['route_name'] == "Test Route")
        boulder_tick = next(t for t in normalized_ticks if t['route_name'] == "Project Boulder")
        trad_tick = next(t for t in normalized_ticks if t['route_name'] == "Trad Classic")
        
        # Verify each field matches expected structure, handling notes separately
        for field, value in expected_sport_tick.items():
            if field == 'notes':
                # Split the comment and hashtags
                expected_comment, expected_tags = value.split('|')
                actual_comment, actual_tags = sport_tick[field].split('|')
                # Verify comment matches exactly
                assert expected_comment.strip() == actual_comment.strip(), f"Sport tick comment mismatch: expected {expected_comment}, got {actual_comment}"
                # Verify all expected hashtags are present, regardless of order
                expected_tag_set = set(expected_tags.strip().split())
                actual_tag_set = set(actual_tags.strip().split())
                assert expected_tag_set == actual_tag_set, f"Sport tick hashtags mismatch: expected {expected_tag_set}, got {actual_tag_set}"
            else:
                assert sport_tick[field] == value, f"Sport tick {field} mismatch: expected {value}, got {sport_tick[field]}"
        
        for field, value in expected_boulder_tick.items():
            if field == 'notes':
                expected_comment, expected_tags = value.split('|')
                actual_comment, actual_tags = boulder_tick[field].split('|')
                assert expected_comment.strip() == actual_comment.strip(), f"Boulder tick comment mismatch: expected {expected_comment}, got {actual_comment}"
                expected_tag_set = set(expected_tags.strip().split())
                actual_tag_set = set(actual_tags.strip().split())
                assert expected_tag_set == actual_tag_set, f"Boulder tick hashtags mismatch: expected {expected_tag_set}, got {actual_tag_set}"
            else:
                assert boulder_tick[field] == value, f"Boulder tick {field} mismatch: expected {value}, got {boulder_tick[field]}"
        
        for field, value in expected_trad_tick.items():
            if field == 'notes':
                expected_comment, expected_tags = value.split('|')
                actual_comment, actual_tags = trad_tick[field].split('|')
                assert expected_comment.strip() == actual_comment.strip(), f"Trad tick comment mismatch: expected {expected_comment}, got {actual_comment}"
                expected_tag_set = set(expected_tags.strip().split())
                actual_tag_set = set(actual_tags.strip().split())
                assert expected_tag_set == actual_tag_set, f"Trad tick hashtags mismatch: expected {expected_tag_set}, got {actual_tag_set}"
            else:
                assert trad_tick[field] == value, f"Trad tick {field} mismatch: expected {value}, got {trad_tick[field]}"
        
        # Verify authentication and data fetching
        mock_eight_a_client.authenticate.assert_awaited_once_with("test_user", "test_pass")
        mock_eight_a_client.get_ascents.assert_awaited_once()
        
        # Verify database operations
        mock_db_service.save_user_ticks.assert_awaited_once()
        mock_db_service.save_performance_pyramid.assert_awaited_once()
        mock_db_service.update_sync_timestamp.assert_awaited_once_with(
            test_user.id,
            LogbookType.EIGHT_A_NU
        )
        
        # Verify data structure
        assert len(ticks) == 3
        assert len(pyramids) > 0
        
        # Verify sport redpoint
        sport_tick = next(t for t in ticks if t['route_name'] == "Test Route")
        assert sport_tick['route_grade'] == "5.12a"
        assert sport_tick['lead_style'] == "Redpoint"
        assert sport_tick['send_bool'] is True
        assert sport_tick['discipline'] == ClimbingDiscipline.SPORT
        assert '#recommended' in sport_tick['notes']
        assert '#overhang' in sport_tick['notes']
        assert '#crimpy' in sport_tick['notes']
        assert '#endurance' in sport_tick['notes']
        
        # Verify boulder project
        boulder_tick = next(t for t in ticks if t['route_name'] == "Project Boulder")
        assert boulder_tick['route_grade'] == "V9"
        assert boulder_tick['lead_style'] == "Project"
        assert boulder_tick['send_bool'] is False
        assert boulder_tick['discipline'] == ClimbingDiscipline.BOULDER
        assert '#recommended' in boulder_tick['notes']
        assert '#roof' in boulder_tick['notes']
        assert '#athletic' in boulder_tick['notes']
        assert '#kneebar' in boulder_tick['notes']
        
        # Verify trad onsight
        trad_tick = next(t for t in ticks if t['route_name'] == "Trad Classic")
        assert trad_tick['route_grade'] == "5.11a"
        assert trad_tick['lead_style'] == "Onsight Trad"
        assert trad_tick['send_bool'] is True
        assert trad_tick['discipline'] == ClimbingDiscipline.TRAD
        assert '#trad' in trad_tick['notes']
        assert '#technical' in trad_tick['notes']
        assert '#looserock' in trad_tick['notes']
        assert '#highfirstbolt' in trad_tick['notes']
        
        # Verify discipline mapping (sport from category 0)
        assert sport_tick['discipline'] == ClimbingDiscipline.SPORT
        assert boulder_tick['discipline'] == ClimbingDiscipline.BOULDER
        assert trad_tick['discipline'] == ClimbingDiscipline.TRAD
        
        # Verify send classification (not a project)
        assert sport_tick['send_bool'] is True
        assert boulder_tick['send_bool'] is False
        assert trad_tick['send_bool'] is True
        
        # Test authentication failure
        mock_eight_a_client.authenticate.reset_mock()
        mock_eight_a_client.authenticate.side_effect = ScrapingError("Invalid credentials")
        
        with pytest.raises(DataSourceError) as exc_info:
            await orchestrator.process_logbook_data(
                user_id=test_user.id,
                logbook_type=LogbookType.EIGHT_A_NU,
                username="bad_user",
                password="bad_pass"
            )
        assert "Invalid credentials" in str(exc_info.value)
        
        # Test empty ascents handling
        mock_eight_a_client.authenticate.reset_mock()
        mock_eight_a_client.authenticate.side_effect = None
        mock_eight_a_client.get_ascents.return_value = {"ascents": [], "totalItems": 0}

        with pytest.raises(DataSourceError) as exc_info:
            await orchestrator.process_logbook_data(
                user_id=test_user.id,
                logbook_type=LogbookType.EIGHT_A_NU,
                username="test_user",
                password="test_pass"
            )
        assert "No data found in 8a.nu response" in str(exc_info.value)

        # Test malformed ascent data handling
        mock_eight_a_client.get_ascents.return_value = {
            "ascents": [{
                **SAMPLE_ASCENTS[0],
                "difficulty": "Invalid Grade",  # Invalid grade
                "zlagGradeIndex": None         # Missing grade index
            }],
            "totalItems": 1
        }
        
        # Should process without error, invalid grade will be handled
        ticks, pyramids, tags = await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType.EIGHT_A_NU,
            username="test_user",
            password="test_pass"
        )
        
        assert len(ticks) > 0
        assert 'binned_grade' in ticks[0]  # Grade processing should still occur
        
        # Test API error handling
        mock_eight_a_client.get_ascents.side_effect = ScrapingError("API error")
        
        with pytest.raises(DataSourceError) as exc_info:
            await orchestrator.process_logbook_data(
                user_id=test_user.id,
                logbook_type=LogbookType.EIGHT_A_NU,
                username="test_user",
                password="test_pass"
            )
        assert "API error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_process_data_with_classifications(
    db_session,
    mock_mp_client: AsyncMock,
    mock_db_service: AsyncMock,
    test_user: User
) -> None:
    """Test data processing with comprehensive classification validation."""
    # Setup database service mock
    orchestrator = LogbookOrchestrator(db_session, db_service=mock_db_service)

    # Create test DataFrame with diverse classification scenarios
    test_df = pd.DataFrame({
        'route_name': [
            'Sport Lead',           # Clear sport lead
            'Trad Adventure',       # Clear trad
            'Boulder Problem',      # Clear boulder
            'Mixed Route',          # Sport/Trad mix
            'TR Practice',          # Clear TR
            'Multi Sport/TR'        # Sport with TR
        ],
        'route_grade': [
            '5.12a',               # Sport grade
            '5.10c',               # Trad grade
            'V5',                  # Boulder grade
            '5.11d',               # Mixed grade
            '5.9',                 # TR grade
            '5.11a'                # Sport/TR grade
        ],
        'style': [
            'Lead',                # Lead style
            'Lead, Trad',          # Trad style
            'Boulder',             # Boulder style
            'Lead, Trad, Sport',   # Mixed style
            'TR',                  # TR style
            'Lead, TR'             # Mixed style
        ],
        'route_type': [
            'Sport',               # Sport type
            'Trad',                # Trad type
            'Boulder',             # Boulder type
            'Sport, Trad',         # Mixed type
            'TR',                  # TR type
            'Sport, TR'            # Mixed type
        ],
        'lead_style': [
            'Onsight',             # Clear send
            'Redpoint',            # Clear send
            'Send',                # Boulder send
            'Fell/Hung',           # Not a send
            '',                    # Empty for TR
            'Flash'                # Clear send
        ],
        'notes': [
            'Clean onsight!',                          # Positive notes
            'Classic line with gear beta',             # Trad indicators
            'Stuck the crux dyno!',                    # Boulder send indicators
            'Fell at the crux, need to work the moves', # Project indicators
            'Good practice route',                      # TR indicators
            'Solid flash on the sharp end'              # Lead indicators
        ],
        'tick_date': [
            '2024-03-23',          # Spring
            '2024-06-15',          # Summer
            '2024-09-10',          # Fall
            '2024-12-25',          # Winter
            '2024-03-24',          # Spring
            '2024-03-25'           # Spring
        ],
        'length': [
            30,                    # Short
            120,                   # Long
            15,                    # Boulder
            80,                    # Medium
            40,                    # Short
            70                     # Medium
        ],
        'pitches': [
            1,                     # Single pitch
            2,                     # Multi pitch
            1,                     # Boulder
            1,                     # Single pitch
            1,                     # Single pitch
            1                      # Single pitch
        ]
    })

    # Patch Mountain Project client
    with patch('app.services.logbook.orchestrator.MountainProjectCSVClient') as mock_client_class:
        # Setup the mock to return our mock client
        mock_client_class.return_value.__aenter__.return_value = mock_mp_client
        
        # Configure mock to return test data
        mock_mp_client.fetch_user_ticks.return_value = test_df

        # Process the data
        ticks, pyramids, tags = await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType.MOUNTAIN_PROJECT,
            profile_url="https://www.mountainproject.com/user/test"
        )

        # Verify client calls
        mock_mp_client.fetch_user_ticks.assert_awaited_once()
        
        # Verify classifications were applied correctly
        assert len(ticks) == 6
        
        # Extract processed ticks for easier assertions
        sport_tick = next(t for t in ticks if t['route_name'] == 'Sport Lead')
        trad_tick = next(t for t in ticks if t['route_name'] == 'Trad Adventure')
        boulder_tick = next(t for t in ticks if t['route_name'] == 'Boulder Problem')
        mixed_tick = next(t for t in ticks if t['route_name'] == 'Mixed Route')
        tr_tick = next(t for t in ticks if t['route_name'] == 'TR Practice')
        sport_tr_tick = next(t for t in ticks if t['route_name'] == 'Multi Sport/TR')
        
        # Verify discipline classification
        assert sport_tick['discipline'] == ClimbingDiscipline.SPORT
        assert trad_tick['discipline'] == ClimbingDiscipline.TRAD
        assert boulder_tick['discipline'] == ClimbingDiscipline.BOULDER
        assert mixed_tick['discipline'] == ClimbingDiscipline.SPORT  # Should default to Sport with gear beta
        assert tr_tick['discipline'] == ClimbingDiscipline.TR
        assert sport_tr_tick['discipline'] == ClimbingDiscipline.SPORT  # Should be Sport due to Flash
        
        # Verify send classification
        assert sport_tick['send_bool'] is True  # Onsight is a send
        assert trad_tick['send_bool'] is True   # Redpoint is a send
        assert boulder_tick['send_bool'] is True  # "Send" is a send
        assert mixed_tick['send_bool'] is False  # Fell/Hung is not a send
        assert tr_tick['send_bool'] is False    # Empty lead_style without send indicators
        assert sport_tr_tick['send_bool'] is True  # Flash is a send
        
        # Verify length classification
        assert sport_tick['length_category'] == 'short'
        assert trad_tick['length_category'] == 'long'
        assert boulder_tick['length_category'] == 'short'
        assert mixed_tick['length_category'] == 'medium'
        assert tr_tick['length_category'] == 'short'
        assert sport_tr_tick['length_category'] == 'medium'
        
        # Verify season classification
        assert 'Spring' in sport_tick['season_category']
        assert 'Summer' in trad_tick['season_category']
        assert 'Fall' in boulder_tick['season_category']
        assert 'Winter' in mixed_tick['season_category']
        
        # Verify grade binning
        assert sport_tick['binned_code'] == 17  # 5.12a
        assert trad_tick['binned_code'] == 12   # 5.10c
        assert boulder_tick['binned_code'] == 107  # V5
        assert mixed_tick['binned_code'] == 16   # 5.11d
        assert tr_tick['binned_code'] == 9       # 5.9
        assert sport_tr_tick['binned_code'] == 14  # 5.11a
        
        # Verify database operations
        mock_db_service.save_user_ticks.assert_awaited_once()
        mock_db_service.save_performance_pyramid.assert_awaited_once()
        mock_db_service.update_sync_timestamp.assert_awaited_once_with(
            test_user.id,
            LogbookType.MOUNTAIN_PROJECT
        )
        
        # Verify pyramids were generated
        assert len(pyramids) > 0
        sport_pyramids = [p for p in pyramids if p['discipline'] == ClimbingDiscipline.SPORT]
        trad_pyramids = [p for p in pyramids if p['discipline'] == ClimbingDiscipline.TRAD]
        boulder_pyramids = [p for p in pyramids if p['discipline'] == ClimbingDiscipline.BOULDER]
        
        assert len(sport_pyramids) > 0
        assert len(trad_pyramids) > 0
        assert len(boulder_pyramids) > 0
        
        # Verify max grades were tracked correctly
        sport_max = max(p['grade_range'] for p in sport_pyramids)
        trad_max = max(p['grade_range'] for p in trad_pyramids)
        boulder_max = max(p['grade_range'] for p in boulder_pyramids)
        
        assert sport_max == '5.12-'  # From sport_tick
        assert trad_max == '5.10'    # From trad_tick
        assert boulder_max == 'V5'    # From boulder_tick

@pytest.mark.asyncio
async def test_error_handling_invalid_source(db_session, test_user: User) -> None:
    """Test error handling for invalid logbook source."""
    orchestrator = LogbookOrchestrator(db_session)
    
    with pytest.raises(ValueError) as exc_info:
        await orchestrator.process_logbook_data(
            user_id=test_user.id,
            logbook_type=LogbookType("invalid_source"),  # This will raise ValueError on enum creation
            profile_url="test"
        )
    assert "is not a valid LogbookType" in str(exc_info.value)

@pytest.mark.asyncio
async def test_error_handling_data_source_error(
    db_session,
    mock_mp_client: AsyncMock
) -> None:
    """Test error handling for data source errors."""
    orchestrator = LogbookOrchestrator(db_session)
    user_id = uuid4()
    
    # Simulate data source error
    mock_mp_client.fetch_user_ticks.side_effect = DataSourceError("Failed to fetch data")
    
    with pytest.raises(DataSourceError) as exc_info:
        await orchestrator.process_logbook_data(
            user_id=user_id,
            logbook_type=LogbookType.MOUNTAIN_PROJECT,
            profile_url="test"
        )
    assert "Failed to fetch data" in str(exc_info.value)

@pytest.mark.asyncio
async def test_empty_data_handling(
    db_session,
    mock_mp_client: AsyncMock,
    mock_db_service: AsyncMock
) -> None:
    """Test handling of empty data from source."""
    orchestrator = LogbookOrchestrator(db_session)
    user_id = uuid4()
    
    # Return empty DataFrame
    mock_mp_client.fetch_user_ticks.return_value = pd.DataFrame()
    
    ticks, pyramids, tags = await orchestrator.process_logbook_data(
        user_id=user_id,
        logbook_type=LogbookType.MOUNTAIN_PROJECT,
        profile_url="test"
    )
    
    assert len(ticks) == 0
    assert len(pyramids) == 0
    assert len(tags) == 0
    mock_db_service.update_sync_timestamp.assert_awaited_once()

@pytest.mark.asyncio
async def test_tag_processing(
    db_session,
    mock_mp_client: AsyncMock,
    mock_db_service: AsyncMock
) -> None:
    """Test processing and saving of tags."""
    orchestrator = LogbookOrchestrator(db_session)
    user_id = uuid4()
    
    # Create test DataFrame with tags
    test_df = pd.DataFrame({
        'route_name': ['Test Route'],
        'route_grade': ['5.12a'],
        'style': ['Lead'],
        'route_type': ['Sport'],
        'tag': ['Project, Crimpy, Steep'],
        'tick_date': ['2024-03-23']
    })
    mock_mp_client.fetch_user_ticks.return_value = test_df
    
    ticks, pyramids, tags = await orchestrator.process_logbook_data(
        user_id=user_id,
        logbook_type=LogbookType.MOUNTAIN_PROJECT,
        profile_url="test"
    )
    
    # Verify tag processing
    mock_db_service.save_tags.assert_awaited_once()
    assert len(tags) > 0
    assert isinstance(tags[0], Tag)  # Verify Tag object type
    assert hasattr(tags[0], 'ticks')  # Verify relationship exists
    assert len(tags[0].ticks) > 0  # Verify relationship is populated
    
    # Verify tag names
    tag_names = {tag.name for tag in tags}
    assert 'Project' in tag_names
    assert 'Crimpy' in tag_names
    assert 'Steep' in tag_names
    
    # Verify bidirectional relationship
    for tag in tags:
        assert any(tick.route_name == 'Test Route' for tick in tag.ticks)

@pytest.mark.asyncio
async def test_grade_processing(
    db_session,
    mock_mp_client: AsyncMock,
    mock_db_service: AsyncMock
) -> None:
    """Test grade processing and conversion."""
    orchestrator = LogbookOrchestrator(db_session)
    user_id = uuid4()
    
    # Create test DataFrame with various grades
    test_df = pd.DataFrame({
        'route_name': ['Route 1', 'Route 2'],
        'route_grade': ['5.12a', 'V5'],
        'style': ['Lead', 'Boulder'],
        'route_type': ['Sport', 'Boulder'],
        'tick_date': ['2024-03-23', '2024-03-23']
    })
    mock_mp_client.fetch_user_ticks.return_value = test_df
    
    ticks, pyramids, tags = await orchestrator.process_logbook_data(
        user_id=user_id,
        logbook_type=LogbookType.MOUNTAIN_PROJECT,
        profile_url="test"
    )
    
    # Verify grade processing
    assert all('binned_grade' in tick for tick in ticks)
    assert all('binned_code' in tick for tick in ticks)
    assert all('difficulty_category' in tick for tick in ticks) 