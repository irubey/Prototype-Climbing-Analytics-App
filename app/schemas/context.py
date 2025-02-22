from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ContextQueryParams(BaseModel):
    """Query parameters for context retrieval."""
    query: Optional[str] = Field(
        None,
        description="Optional query to customize context relevance"
    )
    force_refresh: bool = Field(
        False,
        description="Force context refresh instead of using cache"
    )

class ContextUpdatePayload(BaseModel):
    """Payload for context updates."""
    updates: Dict[str, Any] = Field(
        ...,
        description="Dictionary of context sections to update"
    )
    replace: bool = Field(
        False,
        description="Replace sections entirely instead of merging"
    )

class ContextResponse(BaseModel):
    """Response model for context data."""
    context_version: str = Field(
        ...,
        description="Version of the context format"
    )
    summary: str = Field(
        ...,
        description="Human-readable context summary"
    )
    profile: Dict[str, Any] = Field(
        ...,
        description="Climber profile data"
    )
    performance: Dict[str, Any] = Field(
        ...,
        description="Performance metrics and data"
    )
    trends: Dict[str, Any] = Field(
        ...,
        description="Trend analysis data"
    )
    relevance: Dict[str, Any] = Field(
        ...,
        description="Relevance scores for context sections"
    )
    goals: Dict[str, Any] = Field(
        ...,
        description="Climbing goals and progress"
    )
    uploads: list[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of processed uploads"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "context_version": "1.0",
                "summary": "You've climbed for 3 years, focusing on bouldering. Your highest send is V5. Goal: V8 by December.",
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
        } 