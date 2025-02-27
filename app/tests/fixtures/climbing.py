"""
Climbing-specific fixtures for tests.

This module contains fixtures for climbing-related tests,
including grade conversions, route data, and user ticks.
"""

import pytest
import pytest_asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import random
import uuid
import json
from pathlib import Path

# Import only ClimbingDiscipline from enums
from app.models.enums import ClimbingDiscipline

from app.tests.config import test_settings
from app.tests.fixtures.test_data import load_fixture
from app.tests.factories import ClimbingServiceFactory, GradeServiceFactory


@pytest.fixture
def climbing_disciplines():
    """Return a list of valid climbing disciplines."""
    return [d.value for d in ClimbingDiscipline]


@pytest.fixture
def send_statuses():
    """Return a list of valid send status values (boolean representation)."""
    return [True, False]  # True = sent, False = not sent


@pytest.fixture
def sample_grade_mappings():
    """
    Return a sample of grade mappings for different grading systems.
    
    This provides a consistent set of grade mappings for tests
    that need to verify grade conversion functionality.
    """
    return {
        "yds_to_french": {
            "5.10a": "6a",
            "5.10b": "6a+",
            "5.10c": "6b",
            "5.10d": "6b+",
            "5.11a": "6c",
            "5.11b": "6c+",
            "5.11c": "7a",
            "5.11d": "7a+",
            "5.12a": "7a+",
            "5.12b": "7b",
            "5.12c": "7b+",
            "5.12d": "7c"
        },
        "v_scale_to_font": {
            "V0": "4",
            "V1": "5",
            "V2": "5+",
            "V3": "6A/6A+",
            "V4": "6B/6B+",
            "V5": "6C/6C+",
            "V6": "7A",
            "V7": "7A+",
            "V8": "7B",
            "V9": "7B+",
            "V10": "7C",
            "V11": "7C+"
        }
    }


@pytest.fixture
def sample_climbing_areas():
    """Return a sample list of climbing areas for tests."""
    return [
        {"id": "rr", "name": "Red River Gorge", "location": "Kentucky, USA"},
        {"id": "yos", "name": "Yosemite", "location": "California, USA"},
        {"id": "bishop", "name": "Bishop", "location": "California, USA"},
        {"id": "font", "name": "Fontainebleau", "location": "France"},
        {"id": "smith", "name": "Smith Rock", "location": "Oregon, USA"}
    ]


@pytest.fixture
def sample_routes():
    """Return a sample list of routes for tests."""
    return [
        {
            "id": "r1",
            "name": "Moonlight Buttress",
            "grade": "5.12d",
            "discipline": "Trad",
            "area_id": "yos",
            "length": 1200,
            "pitches": 10
        },
        {
            "id": "r2",
            "name": "Golden Harvest",
            "grade": "5.11c",
            "discipline": "Sport",
            "area_id": "rr",
            "length": 80,
            "pitches": 1
        },
        {
            "id": "r3",
            "name": "Midnight Lightning",
            "grade": "V8",
            "discipline": "Boulder",
            "area_id": "yos",
            "length": 15,
            "pitches": 1
        },
        {
            "id": "r4",
            "name": "Birthday Direct",
            "grade": "V4",
            "discipline": "Boulder",
            "area_id": "bishop",
            "length": 12,
            "pitches": 1
        },
        {
            "id": "r5",
            "name": "Chain Reaction",
            "grade": "5.12c",
            "discipline": "Sport",
            "area_id": "smith",
            "length": 70,
            "pitches": 1
        }
    ]


@pytest.fixture
def sample_user_ticks():
    """Return a sample list of user ticks for tests."""
    return [
        {
            "id": str(uuid.uuid4()),
            "user_id": "user1",
            "route_id": "r1",
            "date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "send_bool": False,  # Not sent (project)
            "attempts": 3,
            "notes": "Getting closer on the crux. Need more finger strength.",
            "tags": ["trad", "multi-pitch", "endurance"]
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": "user1",
            "route_id": "r2",
            "date": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
            "send_bool": True,  # Sent
            "attempts": 2,
            "notes": "Clean send on second attempt. Crux move is the reach at the third bolt.",
            "tags": ["sport", "crimpy", "technical"]
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": "user1",
            "route_id": "r4",
            "date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "send_bool": True,  # Sent
            "attempts": 5,
            "notes": "Finally figured out the heel hook beta.",
            "tags": ["boulder", "power", "outdoor"]
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": "user2",
            "route_id": "r5",
            "date": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "send_bool": False,  # Not sent (attempt)
            "attempts": 1,
            "notes": "Couldn't make it past the roof.",
            "tags": ["sport", "overhang"]
        }
    ]


@pytest.fixture
def load_climbing_data():
    """
    Load climbing-specific test data from fixtures.
    
    Returns a function that can load routes, areas, or ticks from JSON or YAML fixtures.
    """
    def _load_data(data_type: str = "routes", fixture_name: Optional[str] = None, format: str = "json") -> List[Dict[str, Any]]:
        """
        Load climbing data fixtures.
        
        Args:
            data_type: Type of data to load ('routes', 'areas', 'ticks')
            fixture_name: Optional specific fixture name
            format: File format ('json' or 'yaml')
            
        Returns:
            List of data items
        """
        if fixture_name is None:
            fixture_name = data_type

        try:
            return load_fixture(fixture_name, format)
        except FileNotFoundError:
            # If fixture not found, return empty list 
            # This makes tests more resilient to missing fixtures
            return []
    
    return _load_data


@pytest_asyncio.fixture
async def mock_climbing_service(sample_user_ticks, sample_routes):
    """
    Create a mocked climbing service for tests.
    
    Returns a pre-configured climbing service with mock responses
    based on the sample_user_ticks and sample_routes fixtures.
    """
    service = await ClimbingServiceFactory.create_service(
        test_climbs=sample_user_ticks,
        test_routes=sample_routes
    )
    
    return service


@pytest_asyncio.fixture
async def mock_grade_service(sample_grade_mappings):
    """
    Create a mocked grade service for tests.
    
    Returns a pre-configured grade service with mock responses
    based on the sample_grade_mappings fixture.
    """
    # Create custom grade conversion map from the sample mappings
    custom_mappings = {}
    
    # Process YDS to French mappings
    yds_to_french = sample_grade_mappings.get("yds_to_french", {})
    if yds_to_french:
        if "yds" not in custom_mappings:
            custom_mappings["yds"] = {}
        if "french" not in custom_mappings:
            custom_mappings["french"] = {}
            
        for code_id, (yds, french) in enumerate(yds_to_french.items()):
            code_key = f"code_{code_id + 1}"
            custom_mappings["yds"][code_key] = yds
            custom_mappings["french"][code_key] = french
    
    # Process V-scale to Font mappings
    v_to_font = sample_grade_mappings.get("v_scale_to_font", {})
    if v_to_font:
        if "v_scale" not in custom_mappings:
            custom_mappings["v_scale"] = {}
        if "font" not in custom_mappings:
            custom_mappings["font"] = {}
            
        for code_id, (v_grade, font) in enumerate(v_to_font.items()):
            code_key = f"code_{code_id + 101}"  # Offset to avoid collisions
            custom_mappings["v_scale"][code_key] = v_grade
            custom_mappings["font"][code_key] = font
    
    service = GradeServiceFactory.create_service(
        mock_cache=True,
        grade_conversion_map=custom_mappings
    )
    
    return service 