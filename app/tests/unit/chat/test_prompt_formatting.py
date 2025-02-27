"""
Tests for the chat prompt formatting functionality.

This module tests how prompts are structured and formatted for AI models,
including context integration and specialized formatting.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.services.chat.context.unified_formatter import UnifiedFormatter

@pytest.mark.unit
@pytest_asyncio.fixture
async def formatter():
    """Create a UnifiedFormatter instance for testing."""
    return UnifiedFormatter()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_format_context_empty(formatter):
    """Test formatting with empty context."""
    context = {}
    query = "How can I improve my climbing?"
    
    result = formatter.format_context(context, query)
    
    # Should be a dictionary with expected structure
    assert isinstance(result, dict)
    assert "summary" in result
    assert "profile" in result
    assert "performance" in result
    assert "training" in result
    assert "health" in result
    assert "goals" in result
    assert "recent_activity" in result
    assert result["context_version"] == formatter.context_version

@pytest.mark.unit
@pytest.mark.asyncio
async def test_format_context_complete(formatter):
    """Test formatting with complete context data."""
    context = {
        "climber_context": {
            "years_climbing": 3,
            "highest_boulder_grade": "V5",
            "preferred_styles": ["Overhang", "Dynamic"],
            "training_frequency": "3-4 times per week",
            "strengths": ["Power", "Dynamic movement"],
            "weaknesses": ["Finger strength", "Endurance"],
            "training_focus": "Power endurance"
        },
        "trends": {
            "grade_progression": {"recent": 0.5, "all_time": 0.2},
            "training_consistency": 0.8,
            "activity_levels": {"recent": "high", "average": "medium"}
        },
        "goals": {
            "target_grade": "V7",
            "progress": {"progress": 0.3, "status": "on_track", "time_remaining": "3 months"}
        },
        "recent_ticks": [
            {"route": "Test Route 1", "grade": "V5", "date": "2023-05-15"},
            {"route": "Test Route 2", "grade": "V4", "date": "2023-05-20"}
        ]
    }
    query = "What training should I do for my project?"
    
    result = formatter.format_context(context, query)
    
    # Check that all sections are included with correct structure
    assert isinstance(result, dict)
    assert "summary" in result
    assert result["profile"]["experience_level"] == "intermediate"
    assert result["profile"]["years_climbing"] == 3
    assert "Overhang" in result["profile"]["preferred_styles"]
    assert result["performance"]["grade_progression"]["recent"] == 0.5
    assert result["training"]["frequency"] == "3-4 times per week"
    assert "Power" in result["training"]["strengths"]
    assert result["goals"]["target_grade"] == "V7"
    assert len(result["recent_activity"]["ticks"]) == 2
    assert result["recent_activity"]["ticks"][0]["route"] == "Test Route 1"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_format_context_partial(formatter):
    """Test formatting with partial context data."""
    context = {
        "climber_context": {
            "years_climbing": 1,
            "highest_boulder_grade": "V2"
        },
        "recent_ticks": [
            {"route": "Beginner Route", "grade": "V2", "date": "2023-05-22"}
        ]
    }
    query = "How do I get better at climbing?"
    
    result = formatter.format_context(context, query)
    
    # Check that the formatter handles partial data gracefully
    assert isinstance(result, dict)
    assert "summary" in result
    assert result["profile"]["experience_level"] == "beginner"
    assert result["profile"]["years_climbing"] == 1
    assert len(result["recent_activity"]["ticks"]) == 1
    assert result["recent_activity"]["ticks"][0]["route"] == "Beginner Route"
    assert result["performance"] != {}  # Should still have structure even if empty
    assert result["training"] != {}
    assert result["health"] != {}
    assert result["goals"] == {}  # No goals provided

@pytest.mark.unit
@pytest.mark.asyncio
async def test_format_context_with_relevance(formatter):
    """Test formatting with relevance scores."""
    context = {
        "climber_context": {
            "years_climbing": 3,
            "highest_boulder_grade": "V5"
        },
        "recent_ticks": [
            {"route": "Test Boulder", "grade": "V4", "date": "2023-05-18"}
        ],
        "relevance": {
            "strength": 0.9,
            "bouldering": 0.8,
            "technique": 0.4
        }
    }
    query = "How can I improve my strength for bouldering?"
    
    result = formatter.format_context(context, query)
    
    # Check that relevance scores are included
    assert "relevance" in result
    assert result["relevance"]["strength"] == 0.9
    assert result["relevance"]["bouldering"] == 0.8
    assert result["relevance"]["technique"] == 0.4

@pytest.mark.unit
@pytest.mark.asyncio
async def test_to_json(formatter):
    """Test converting the formatted context to JSON."""
    context = {
        "climber_context": {
            "years_climbing": 3,
            "highest_boulder_grade": "V5"
        }
    }
    
    # First format the context
    formatted = formatter.format_context(context)
    
    # Convert to JSON
    json_str = formatter.to_json(formatted)
    
    # Should be valid JSON
    assert isinstance(json_str, str)
    parsed_back = json.loads(json_str)
    assert isinstance(parsed_back, dict)
    assert parsed_back["profile"]["years_climbing"] == 3
    assert parsed_back["context_version"] == formatter.context_version

@pytest.mark.unit
@pytest.mark.asyncio
async def test_determine_experience_level(formatter):
    """Test experience level determination."""
    # Beginner context
    beginner_context = {
        "climber_context": {
            "years_climbing": 1,
            "highest_boulder_grade": "V2"
        }
    }
    assert formatter.determine_experience_level(beginner_context) == "beginner"
    
    # Intermediate context based on grade
    intermediate_by_grade = {
        "climber_context": {
            "years_climbing": 1,  # Not enough years
            "highest_boulder_grade": "V5"  # But grade matches intermediate
        }
    }
    assert formatter.determine_experience_level(intermediate_by_grade) == "intermediate"
    
    # Intermediate context based on years
    intermediate_by_years = {
        "climber_context": {
            "years_climbing": 3,  # Enough years
            "highest_boulder_grade": "V3"  # Not high enough grade
        }
    }
    assert formatter.determine_experience_level(intermediate_by_years) == "intermediate"
    
    # Advanced context based on grade
    advanced = {
        "climber_context": {
            "years_climbing": 2,
            "highest_boulder_grade": "V8"
        }
    }
    assert formatter.determine_experience_level(advanced) == "advanced"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_summary(formatter):
    """Test summary generation."""
    context = {
        "climber_context": {
            "years_climbing": 4,
            "highest_boulder_grade": "V6",
            "goal_grade": "V8"
        },
        "trends": {
            "grade_progression": {"recent": 0.7},
            "training_consistency": 0.9
        },
        "goals": {
            "progress": {"progress": 0.5, "status": "on_track", "time_remaining": "6 months"}
        }
    }
    experience_level = "intermediate"
    
    summary = formatter.generate_summary(context, experience_level)
    
    # Check summary content
    assert isinstance(summary, str)
    assert "experienced" in summary  # 4 years > 3 years threshold
    assert "intermediate climber" in summary
    assert "4 years of experience" in summary
    assert "V6" in summary  # highest grade
    assert "positive grade progression" in summary
    assert "very consistent training" in summary
    assert "V8" in summary  # goal grade
    assert "6 months" in summary  # time remaining 