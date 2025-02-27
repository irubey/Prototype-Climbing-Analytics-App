"""
Schemas for logbook operations.

These schemas are ONLY used in tests and are not application models.
They provide simplified mock objects for testing logbook functionality.
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any
from enum import Enum, auto
from pydantic import BaseModel, Field

from app.models.enums import ClimbingDiscipline, CruxAngle
from app.services.utils.grade_service import GradingSystem


# --------------------------------------------------------------
# Mock classes for testing - these are NOT application models
# --------------------------------------------------------------

class ClimbingRoute(BaseModel):
    """Mock version of a climbing route for tests."""
    name: str
    grade: str
    grade_system: GradingSystem
    discipline: ClimbingDiscipline
    location: Optional[str] = None


class ClimbingLog(BaseModel):
    """Mock version of a climbing log for tests."""
    id: str
    user_id: str
    route: ClimbingRoute
    status: str  # "sent", "attempted", "project" 
    attempts: int
    date: datetime
    notes: Optional[str] = None
    
    @property
    def sent(self) -> bool:
        """Return whether the route was sent."""
        return self.status == "sent"


class ClimbingStats(BaseModel):
    """Mock version of climbing statistics for tests."""
    user_id: str
    total_climbs: int
    sent_climbs: int
    project_climbs: int
    attempted_climbs: int
    discipline_counts: Dict[ClimbingDiscipline, int]
    hardest_sent_grade: Dict[str, str]
    date_range: Dict[str, datetime] 