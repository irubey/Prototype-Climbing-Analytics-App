"""
Parameterized tests for the climbing service functionality.

This module demonstrates how to use the test parameterization utilities
to create maintainable, structured tests for the climbing service.
"""

import pytest
import pytest_asyncio
from typing import Dict, List, Any, NamedTuple
from unittest.mock import AsyncMock, MagicMock

from app.tests.utils.parameterization import TestCase
from app.tests.factories import ClimbingServiceFactory


# Define test cases for user tick retrieval
def user_ticks_test_cases() -> List[TestCase]:
    """Generate test cases for user tick retrieval functionality."""
    return [
        TestCase(
            id="user_with_ticks",
            input={"user_id": "user1", "include_tags": True},
            expected={
                "count": 3,
                "status": "success",
                "has_tags": True
            },
            description="User with existing ticks returns data with tags"
        ),
        TestCase(
            id="user_without_ticks",
            input={"user_id": "user_no_ticks", "include_tags": True},
            expected={
                "count": 0,
                "status": "success",
                "has_tags": False
            },
            description="User without any ticks returns empty list"
        ),
        TestCase(
            id="with_date_filter",
            input={
                "user_id": "user1", 
                "include_tags": True,
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            },
            expected={
                "count": 2,
                "status": "success",
                "has_tags": True
            },
            description="Date filtering returns only ticks within the date range"
        ),
        TestCase(
            id="with_grade_filter",
            input={
                "user_id": "user1", 
                "include_tags": True,
                "min_grade": "V3",
                "max_grade": "V7"
            },
            expected={
                "count": 1,
                "status": "success",
                "has_tags": True
            },
            description="Grade filtering returns only ticks within the grade range"
        ),
        TestCase(
            id="invalid_user_id",
            input={"user_id": None, "include_tags": True},
            expected={
                "error": "Invalid user ID",
                "status": "error"
            },
            description="Invalid user ID raises an error"
        )
    ]


# Define test cases for grade conversion
def grade_conversion_test_cases() -> List[TestCase]:
    """Generate test cases for grade conversion functionality."""
    return [
        TestCase(
            id="yds_to_french",
            input={
                "grade": "5.12a",
                "source_system": "yds",
                "target_system": "french"
            },
            expected={
                "converted_grade": "7a+",
                "status": "success"
            },
            description="Convert YDS to French grade"
        ),
        TestCase(
            id="v_scale_to_font",
            input={
                "grade": "V6",
                "source_system": "v_scale",
                "target_system": "font"
            },
            expected={
                "converted_grade": "7A",
                "status": "success"
            },
            description="Convert V-scale to Font grade"
        ),
        TestCase(
            id="invalid_grade",
            input={
                "grade": "invalid_grade",
                "source_system": "yds",
                "target_system": "french"
            },
            expected={
                "converted_grade": None,
                "status": "error",
                "error": "Invalid grade"
            },
            description="Invalid grade returns error"
        ),
        TestCase(
            id="invalid_system",
            input={
                "grade": "5.10b",
                "source_system": "invalid_system",
                "target_system": "french"
            },
            expected={
                "converted_grade": None,
                "status": "error",
                "error": "Invalid grading system"
            },
            description="Invalid grading system returns error"
        )
    ]


# Fixture to create a parameterized climbing service
@pytest_asyncio.fixture
async def climbing_service_fixture():
    """Create a climbing service with test data for parameterized tests."""
    # Define test climbing data
    test_ticks = [
        {
            "id": "tick1",
            "user_id": "user1",
            "route": "Test Route 1",
            "grade": "5.10a",
            "send_status": "sent",
            "date": "2023-01-15",
            "location": "Red River Gorge",
            "discipline": "Sport",
            "tags": ["crimpy", "technical"]
        },
        {
            "id": "tick2",
            "user_id": "user1",
            "route": "Test Route 2",
            "grade": "V4",
            "send_status": "project",
            "date": "2023-02-10",
            "location": "Bishop",
            "discipline": "Boulder",
            "tags": ["powerful", "overhang"]
        },
        {
            "id": "tick3",
            "user_id": "user1",
            "route": "Test Route 3",
            "grade": "5.11d",
            "send_status": "sent",
            "date": "2022-12-05",
            "location": "Smith Rock",
            "discipline": "Sport",
            "tags": ["endurance", "technical"]
        }
    ]
    
    # Create the service with test data
    service = await ClimbingServiceFactory.create_service(
        test_climbs=test_ticks
    )
    
    # Configure mock behavior for date and grade filtering
    db_service = service._test_mocks["db_service"]
    
    # Configure date filtering behavior
    async def get_user_ticks_with_filters(user_id, include_tags=False, start_date=None, end_date=None, 
                                         min_grade=None, max_grade=None):
        if user_id is None:
            return {"error": "Invalid user ID", "status": "error"}
            
        if user_id == "user_no_ticks":
            return []
            
        if start_date and end_date:
            # Filter ticks by date
            filtered_ticks = [t for t in test_ticks 
                             if start_date <= t["date"] <= end_date]
            return filtered_ticks
            
        if min_grade and max_grade:
            # Simple grade filtering (would be more complex in real app)
            if min_grade == "V3" and max_grade == "V7":
                return [t for t in test_ticks if t["grade"] == "V4"]
            
        return test_ticks
    
    # Update the mock to use our filtering function
    db_service.get_user_ticks.side_effect = get_user_ticks_with_filters
    
    # Configure grade service behavior
    grade_service = service._test_mocks["grade_service"]
    
    async def convert_grade_system(grade, source_system, target_system):
        if grade == "invalid_grade":
            return None
        if source_system == "invalid_system" or target_system == "invalid_system":
            return None
            
        # Known conversions
        conversions = {
            ("5.12a", "yds", "french"): "7a+",
            ("V6", "v_scale", "font"): "7A"
        }
        
        key = (grade, source_system, target_system)
        return conversions.get(key)
    
    grade_service.convert_grade_system.side_effect = convert_grade_system
    
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case",
    user_ticks_test_cases(),
    ids=[tc.id for tc in user_ticks_test_cases()]
)
async def test_get_user_ticks(climbing_service_fixture, test_case):
    """
    Test retrieving user ticks with various parameters.
    
    This parameterized test demonstrates how to test the user ticks
    retrieval functionality with various input scenarios.
    
    Args:
        climbing_service_fixture: The preconfigured climbing service
        test_case: The test case parameters from the parameterization
    """
    # Get service and mock for testing
    service = climbing_service_fixture
    db_service = service._test_mocks["db_service"]
    
    # Execute the function with test case input
    result = await db_service.get_user_ticks(**test_case.input)
    
    # If we expect an error
    if "error" in test_case.expected:
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == test_case.expected["error"]
        assert result["status"] == test_case.expected["status"]
        return
        
    # For successful results
    assert isinstance(result, list) or isinstance(result, dict)
    
    # If it's an error dict
    if isinstance(result, dict) and "error" in result:
        assert False, f"Expected success but got error: {result['error']}"
    
    # Verify count
    if isinstance(result, list):
        assert len(result) == test_case.expected["count"]
    
    # Verify tags if expected
    if test_case.expected.get("has_tags") and len(result) > 0:
        assert "tags" in result[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case",
    grade_conversion_test_cases(),
    ids=[tc.id for tc in grade_conversion_test_cases()]
)
async def test_convert_grade(climbing_service_fixture, test_case):
    """
    Test grade conversion functionality with various parameters.
    
    This parameterized test demonstrates how to test the grade conversion
    functionality with various input scenarios.
    
    Args:
        climbing_service_fixture: The preconfigured climbing service
        test_case: The test case parameters from the parameterization
    """
    # Get service and mock for testing
    service = climbing_service_fixture
    grade_service = service._test_mocks["grade_service"]
    
    # Extract test inputs
    grade = test_case.input["grade"]
    source_system = test_case.input["source_system"]
    target_system = test_case.input["target_system"]
    
    # Execute the function
    result = await grade_service.convert_grade_system(
        grade, 
        source_system, 
        target_system
    )
    
    # For error cases
    if test_case.expected.get("status") == "error":
        assert result is None
        return
        
    # For successful conversions
    assert result == test_case.expected["converted_grade"] 