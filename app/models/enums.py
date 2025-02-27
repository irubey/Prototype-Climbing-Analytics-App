"""
Enumeration classes for Send Sage application.

This module defines strongly-typed enums for:
- Session and activity metrics
- Climbing disciplines and styles
- Performance and quality indicators
- User tiers and payment states
"""

from enum import Enum
from typing import List, Dict, Any

class SessionLength(str, Enum):
    """Duration categories for climbing sessions."""
    
    LESS_THAN_1_HOUR = "Less than 1 hour"
    ONE_TO_TWO_HOURS = "1-2 hours"
    TWO_TO_THREE_HOURS = "2-3 hours"
    THREE_TO_FOUR_HOURS = "3-4 hours"
    FOUR_PLUS_HOURS = "4+ hours"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class SleepScore(str, Enum):
    """Quality indicators for sleep tracking."""
    
    POOR = "Poor"
    FAIR = "Fair"
    GOOD = "Good"
    EXCELLENT = "Excellent"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class NutritionScore(str, Enum):
    """Quality indicators for nutrition tracking."""
    
    POOR = "Poor"
    FAIR = "Fair"
    GOOD = "Good"
    EXCELLENT = "Excellent"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class ClimbingDiscipline(str, Enum):
    """Categories of climbing styles and disciplines."""
    
    TR = "tr"
    BOULDER = "boulder"
    SPORT = "sport"
    TRAD = "trad"
    MIXED = "mixed"
    WINTER_ICE = "winter_ice"
    AID = "aid"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class CruxAngle(str, Enum):
    """Wall angle categories for climbing routes."""
    
    SLAB = "Slab"
    VERTICAL = "Vertical"
    OVERHANG = "Overhang"
    ROOF = "Roof"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class CruxEnergyType(str, Enum):
    """Energy system categories for crux sequences."""
    
    POWER = "Power"
    POWER_ENDURANCE = "Power Endurance"
    ENDURANCE = "Endurance"
    TECHNICAL = "Technical"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class HoldType(str, Enum):
    """Categories of climbing holds."""
    
    CRIMPS = "Crimps"
    SLOPERS = "Slopers"
    POCKETS = "Pockets"
    PINCHES = "Pinches"
    CRACKS = "Cracks"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class LogbookType(str, Enum):
    """Sources of climbing logbook data."""
    
    MOUNTAIN_PROJECT = "Mountain Project"
    EIGHT_A_NU = "8a.nu"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class UserTier(str, Enum):
    """User subscription tiers with access levels."""
    
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ADMIN = "admin"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

    @classmethod
    def get_permissions(cls) -> Dict[str, Dict[str, Any]]:
        """Return permission settings for each tier."""
        return {
            cls.FREE.value: {
                "can_chat": True,
                "daily_messages": 10,
                "can_export": False
            },
            cls.BASIC.value: {
                "can_chat": True,
                "daily_messages": 50,
                "can_export": True
            },
            cls.PREMIUM.value: {
                "can_chat": True,
                "daily_messages": float('inf'),
                "can_export": True
            },
            cls.ADMIN.value: {
                "can_chat": True,
                "daily_messages": float('inf'),
                "can_export": True,
                "is_admin": True
            }
        }

class PaymentStatus(str, Enum):
    """Payment status indicators for subscription management."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

    @classmethod
    def is_valid_transition(cls, current: str, next: str) -> bool:
        """Check if status transition is valid.
        
        Args:
            current: Current payment status
            next: Proposed next status
            
        Returns:
            bool: True if transition is valid
        """
        valid_transitions = {
            cls.PENDING.value: [cls.ACTIVE.value, cls.FAILED.value],
            cls.ACTIVE.value: [cls.INACTIVE.value, cls.CANCELLED.value],
            cls.INACTIVE.value: [cls.ACTIVE.value, cls.CANCELLED.value],
            cls.CANCELLED.value: [cls.ACTIVE.value],
            cls.FAILED.value: [cls.PENDING.value]
        }
        return next in valid_transitions.get(current, [])
    
class ConnectionStatus(str, Enum):
    """Status of an external logbook connection."""
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    EXPIRED = "expired"
    REVOKED = "revoked"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class SyncFrequency(str, Enum):
    """Frequency of data synchronization."""
    MANUAL = "manual"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @classmethod
    def get_values(cls) -> List[str]:
        """Return list of enum values."""
        return [e.value for e in cls]

class GradingSystem(str, Enum):
    """Supported climbing grade systems."""
    YDS = "yds"  # Yosemite Decimal System
    FRENCH = "french"  # French Sport
    V_SCALE = "v_scale"  # Hueco/V Scale
    FONT = "font"  # Fontainebleau

    @property
    def display_name(self) -> str:
        """Get human-readable name of grading system."""
        return {
            self.YDS: "Yosemite Decimal System",
            self.FRENCH: "French Sport",
            self.V_SCALE: "Hueco/V Scale",
            self.FONT: "Fontainebleau"
        }[self]


